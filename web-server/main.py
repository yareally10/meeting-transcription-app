from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from bson import ObjectId
import logging
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting Transcription API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "meeting_db"
SHARED_AUDIO_PATH = "/app/shared_audio"
TRANSCRIPTION_SERVICE_URL = os.getenv("TRANSCRIPTION_SERVICE_URL", "http://localhost:8001")
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:8000")

client = AsyncIOMotorClient(MONGODB_URL)
db = client[DATABASE_NAME]

# Ensure shared audio directory exists
os.makedirs(SHARED_AUDIO_PATH, exist_ok=True)

async def save_audio_chunk(meeting_id: str, audio_data: bytes) -> str:
    """
    Save audio chunk to shared volume with meeting-specific folder and UTC timestamp filename
    Returns the saved file path
    """
    try:
        # Create meeting-specific directory with raw subfolder
        meeting_dir = Path(SHARED_AUDIO_PATH) / meeting_id
        raw_dir = meeting_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate UTC timestamp filename
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{timestamp}.webm"
        file_path = raw_dir / filename
        
        # Save audio chunk
        with open(file_path, "wb") as f:
            f.write(audio_data)
        
        logger.info(f"Saved audio chunk: {file_path} ({len(audio_data)} bytes)")
        return str(file_path)
        
    except Exception as e:
        logger.error(f"Error saving audio chunk for meeting {meeting_id}: {e}")
        raise

async def send_to_transcription_service(meeting_id: str, filename: str) -> Optional[str]:
    """
    Send audio file to transcription service for processing
    Returns job_id if successful, None if failed
    """
    try:
        webhook_url = f"{WEB_SERVER_URL}/webhook/transcription-completed"
        
        request_data = {
            "meeting_id": meeting_id,
            "filename": filename,
            "webhook_url": webhook_url
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TRANSCRIPTION_SERVICE_URL}/transcribe",
                json=request_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get("job_id")
                logger.info(f"Successfully queued transcription job {job_id} for meeting {meeting_id}, file {filename}")
                return job_id
            else:
                logger.error(f"Transcription service error: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Error sending to transcription service: {e}")
        return None

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, validation_info=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")
        return field_schema

class MeetingBase(BaseModel):
    title: str
    description: str = ""
    keywords: List[str] = []

class MeetingCreate(MeetingBase):
    pass

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None

class Meeting(MeetingBase):
    id: PyObjectId = None
    createdBy: str = Field("user123", alias="created_by")
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    status: str = "created"
    fullTranscription: Optional[str] = Field(None, alias="full_transcription")
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }

class KeywordsUpdate(BaseModel):
    keywords: List[str]

class TranscriptionWebhookResult(BaseModel):
    job_id: str
    meeting_id: str
    filename: str
    transcription_text: Optional[str] = None
    confidence: Optional[float] = None
    processing_time: float
    status: str  # "completed" or "failed"
    error_message: Optional[str] = None
    processed_at: str

@app.on_event("startup")
async def startup_db_client():
    logger.info("Starting up database connection...")
    try:
        await client.admin.command('ping')
        logger.info("Connected to MongoDB successfully")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down database connection...")
    client.close()

@app.get("/")
async def root():
    return {"message": "Meeting Transcription API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc)}

@app.post("/meetings", response_model=Meeting)
async def create_meeting(meeting: MeetingCreate):
    """Create a new meeting"""
    logger.info(f"Received meeting creation request: {meeting.dict()}")
    try:
        meeting_dict = meeting.dict()
        meeting_dict.update({
            "created_by": "user123", # only has one user for now
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "created",
            "full_transcription": None
        })
        
        logger.info(f"Attempting to insert meeting into database: {meeting_dict}")
        result = await db.meetings.insert_one(meeting_dict)
        logger.info(f"Meeting inserted with ID: {result.inserted_id}")
        
        created_meeting = await db.meetings.find_one({"_id": result.inserted_id})
        
        if created_meeting:
            logger.info(f"Meeting retrieved from database: {created_meeting}")
            created_meeting["id"] = str(created_meeting["_id"])
            return Meeting(**created_meeting)
        else:
            logger.error("Failed to retrieve created meeting from database")
            raise HTTPException(status_code=500, detail="Failed to create meeting")
    except Exception as e:
        logger.error(f"Database error creating meeting: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/meetings", response_model=List[Meeting])
async def get_meetings():
    """Get all meetings for the current user"""
    try:
        meetings = []
        cursor = db.meetings.find({"created_by": "user123"}).sort("created_at", -1)
        
        async for meeting in cursor:
            meeting["id"] = str(meeting["_id"])
            meetings.append(Meeting(**meeting))
        
        logger.info(f"Returning {len(meetings)} meetings to frontend")
        if meetings:
            logger.info(f"Sample meeting data: {meetings[0].dict()}")
        return meetings
    except Exception as e:
        logger.error(f"Error fetching meetings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str):
    """Get a specific meeting by ID"""
    try:
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting["id"] = str(meeting["_id"])
        return Meeting(**meeting)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching meeting: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/meetings/{meeting_id}", response_model=Meeting)
async def update_meeting(meeting_id: str, meeting_update: MeetingUpdate):
    """Update a meeting"""
    try:
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        update_data = {k: v for k, v in meeting_update.dict().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid update data provided")
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        result = await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        updated_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_meeting["id"] = str(updated_meeting["_id"])
        return Meeting(**updated_meeting)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meeting: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting"""
    try:
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        result = await db.meetings.delete_one({"_id": ObjectId(meeting_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return {"message": "Meeting deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meeting: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/meetings/{meeting_id}/keywords", response_model=Meeting)
async def update_meeting_keywords(meeting_id: str, keywords_update: KeywordsUpdate):
    """Update keywords for a specific meeting"""
    try:
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        update_data = {
            "keywords": keywords_update.keywords,
            "updated_at": datetime.now(timezone.utc)
        }
        
        result = await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        updated_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_meeting["id"] = str(updated_meeting["_id"])
        return Meeting(**updated_meeting)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating meeting keywords: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/webhook/transcription-completed")
async def transcription_webhook(result: TranscriptionWebhookResult):
    """Receive transcription results from transcription service"""
    try:
        logger.info(f"Received transcription webhook for meeting {result.meeting_id}, file {result.filename}, status: {result.status}")
        
        if not ObjectId.is_valid(result.meeting_id):
            logger.error(f"Invalid meeting ID in webhook: {result.meeting_id}")
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        # Find the meeting
        meeting = await db.meetings.find_one({"_id": ObjectId(result.meeting_id)})
        if not meeting:
            logger.error(f"Meeting not found for webhook: {result.meeting_id}")
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if result.status == "completed":
            # Update meeting with transcription result
            current_transcription = meeting.get("full_transcription", "") or ""
            
            if result.transcription_text:
                # Append new transcription to existing one
                if current_transcription:
                    updated_transcription = current_transcription + " " + result.transcription_text
                else:
                    updated_transcription = result.transcription_text
                
                # Update meeting document
                update_data = {
                    "full_transcription": updated_transcription,
                    "updated_at": datetime.now(timezone.utc)
                }
                
                await db.meetings.update_one(
                    {"_id": ObjectId(result.meeting_id)},
                    {"$set": update_data}
                )
                
                logger.info(f"Updated meeting {result.meeting_id} with transcription from {result.filename}")
            else:
                logger.warning(f"No transcription text received for file {result.filename}")
                
        elif result.status == "failed":
            logger.error(f"Transcription failed for meeting {result.meeting_id}, file {result.filename}: {result.error_message}")
            
            # Optionally update meeting status or add error info
            # For now, we'll just log the error
        
        return {"status": "success", "message": "Webhook processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing transcription webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.websocket("/ws/meeting/{meeting_id}/audio")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for audio streaming and real-time transcription"""
    await websocket.accept()
    logger.info(f"WebSocket connection established for meeting {meeting_id}")
    
    try:
        # Validate meeting exists
        if not ObjectId.is_valid(meeting_id):
            await websocket.send_text("Error: Invalid meeting ID")
            await websocket.close()
            return
            
        meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        if not meeting:
            await websocket.send_text("Error: Meeting not found")
            await websocket.close()
            return
        
        # Update meeting status to transcribing
        await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {
                "status": "transcribing",
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        await websocket.send_text("Connected: Ready to receive audio")
        
        while True:
            # Receive audio data from client
            data = await websocket.receive_bytes()
            
            # Log received audio chunk
            logger.info(f"Received audio chunk of {len(data)} bytes for meeting {meeting_id}")
            
            # Save audio chunk to shared volume
            try:
                saved_file_path = await save_audio_chunk(meeting_id, data)
                filename = Path(saved_file_path).name
                await websocket.send_text(f"Audio chunk saved: {saved_file_path}")
                
                # Send to transcription service
                job_id = await send_to_transcription_service(meeting_id, filename)
                if job_id:
                    await websocket.send_text(f"Transcription queued with job ID: {job_id}")
                else:
                    await websocket.send_text("Warning: Failed to queue transcription")
                    
            except Exception as e:
                logger.error(f"Failed to save audio chunk: {e}")
                await websocket.send_text(f"Error saving audio chunk: {str(e)}")
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for meeting {meeting_id}")
        
        # Update meeting status back to created when disconnected
        try:
            await db.meetings.update_one(
                {"_id": ObjectId(meeting_id)},
                {"$set": {
                    "status": "created",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        except Exception as e:
            logger.error(f"Error updating meeting status on disconnect: {e}")
            
    except Exception as e:
        logger.error(f"WebSocket error for meeting {meeting_id}: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except:
            pass