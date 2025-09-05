from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from typing import List, Optional, Dict
import os
from datetime import datetime, timezone
from bson import ObjectId
import logging
import json
from audio_service import AudioFileService
from transcription_service import TranscriptionService
from websocket_manager import ConnectionManager

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

# Initialize WebSocket connection manager
manager = ConnectionManager()

# Initialize services
audio_service = AudioFileService(SHARED_AUDIO_PATH)
transcription_service = TranscriptionService(TRANSCRIPTION_SERVICE_URL, WEB_SERVER_URL)

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, validation_info=None):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid objectid")
            return v
        raise ValueError("Invalid objectid")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _source_type, _handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "description": "MongoDB ObjectId"}

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


@app.get("/transcription/health")
async def get_transcription_service_health():
    """Get health status of the transcription service"""
    try:
        health_status = await transcription_service.get_service_health()
        if health_status.get("healthy", False):
            return health_status
        else:
            raise HTTPException(status_code=503, detail=health_status)
    except Exception as e:
        logger.error(f"Error checking transcription service health: {e}")
        raise HTTPException(status_code=503, detail={"healthy": False, "error": str(e)})

@app.get("/transcription/job/{job_id}")
async def get_transcription_job_status(job_id: str):
    """Get status of a transcription job"""
    try:
        job_status = await transcription_service.get_job_status(job_id)
        if job_status:
            return job_status
        else:
            raise HTTPException(status_code=404, detail="Transcription job not found")
    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

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
                
                # Send success notification with full transcription text
                await manager.send_notification(
                    result.meeting_id, 
                    "transcription_status", 
                    "completed", 
                    f"Transcription completed for audio chunk ({result.filename})",
                    {
                        "text_snippet": result.transcription_text[:100] + "..." if len(result.transcription_text) > 100 else result.transcription_text,
                        "full_text": result.transcription_text
                    }
                )
            else:
                logger.warning(f"No transcription text received for file {result.filename}")
                await manager.send_notification(result.meeting_id, "transcription_status", "warning", f"No transcription text received for {result.filename}")
                
        elif result.status == "failed":
            logger.error(f"Transcription failed for meeting {result.meeting_id}, file {result.filename}: {result.error_message}")
            
            # Send error notification
            await manager.send_notification(
                result.meeting_id, 
                "transcription_status", 
                "failed", 
                f"Transcription failed for {result.filename}: {result.error_message or 'Unknown error'}"
            )
        
        return {"status": "success", "message": "Webhook processed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing transcription webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.websocket("/ws/meeting/{meeting_id}/audio")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for audio streaming and real-time transcription"""
    await manager.connect(websocket, meeting_id)
    
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
        
        # Reset audio processing position for new recording session
        audio_service.reset_processing_position(meeting_id)
        
        # Send initial connection notification
        await manager.send_notification(meeting_id, "transcription_status", "connected", "Connected: Ready to receive audio")
        
        while True:
            # Receive audio data from client
            data = await websocket.receive_bytes()
            
            # Log received audio chunk
            logger.info(f"Received audio chunk of {len(data)} bytes for meeting {meeting_id}")
            
            # Save audio chunk using audio service
            try:
                result = await audio_service.append_audio_chunk(meeting_id, data)
                await websocket.send_text(f"Audio chunk saved: {result['file_path']}")

                # chunk the raw audio file using position tracking
                chunk_result = await audio_service.slice_next_unprocessed_chunk(meeting_id)
                if chunk_result:
                    logger.info(f"Created audio chunk: {chunk_result['chunk_filename']} ({chunk_result['actual_duration_seconds']:.2f}s, {chunk_result['remaining_audio_seconds']:.2f}s remaining)")

                # send chunk to transcription service
                if chunk_result:
                    job_id = await transcription_service.submit_transcription_job(meeting_id, chunk_result['chunk_filename'])
                    if job_id:
                        logger.info(f"Submitted transcription job {job_id} for chunk {chunk_result['chunk_filename']}")
                        await manager.send_notification(meeting_id, "transcription_status", "processing", f"Transcription job {job_id} submitted for {chunk_result['chunk_filename']}")
                    else:
                        await manager.send_notification(meeting_id, "transcription_status", "error", f"Failed to submit transcription job for {chunk_result['chunk_filename']}")
                
                # Send notification about chunk being appended
                await manager.send_notification(
                    meeting_id, 
                    "transcription_status", 
                    "processing", 
                    f"Audio chunk {'added to new file' if result['is_first_chunk'] else 'appended'} ({result['chunk_size']} bytes, total: {result['total_file_size']} bytes)"
                )
                    
            except Exception as e:
                logger.error(f"Failed to save audio chunk: {e}")
                await manager.send_notification(meeting_id, "transcription_status", "error", f"Error processing audio chunk: {str(e)}")
            
    except WebSocketDisconnect:
        manager.disconnect(meeting_id)
        
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
        manager.disconnect(meeting_id)
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except:
            pass