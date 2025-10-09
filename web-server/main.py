from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import logging
import uuid
from contextlib import asynccontextmanager
from bson import ObjectId

from config import config
from database import database
from models import (
    Meeting, MeetingCreate, MeetingUpdate, KeywordsUpdate,
    TranscriptionWebhookResult
)
from services import (
    MeetingService,
    TranscriptionWebhookService,
    AudioFileService,
    TranscriptionService,
    ConnectionManager
)

logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Global services - initialized in lifespan
manager: Optional[ConnectionManager] = None
audio_service: Optional[AudioFileService] = None
transcription_service: Optional[TranscriptionService] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager"""
    global manager, audio_service, transcription_service
    
    # Startup
    logger.info("Starting up application...")
    
    # Initialize database
    await database.connect()
    
    # Ensure shared audio directory exists
    os.makedirs(config.SHARED_AUDIO_PATH, exist_ok=True)
    
    # Initialize services
    manager = ConnectionManager()
    audio_service = AudioFileService(config.SHARED_AUDIO_PATH)
    transcription_service = TranscriptionService(
        config.TRANSCRIPTION_SERVICE_URL, 
        config.WEB_SERVER_URL
    )
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await database.close()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Meeting Transcription API", 
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# Meeting endpoints
@app.post("/meetings", response_model=Meeting)
async def create_meeting(meeting: MeetingCreate):
    """Create a new meeting"""
    return await MeetingService.create_meeting(meeting)

@app.get("/meetings", response_model=List[Meeting])
async def get_meetings():
    """Get all meetings for the current user"""
    return await MeetingService.get_meetings()

@app.get("/meetings/{meeting_id}", response_model=Meeting)
async def get_meeting(meeting_id: str):
    """Get a specific meeting by ID"""
    return await MeetingService.get_meeting(meeting_id)

@app.put("/meetings/{meeting_id}", response_model=Meeting)
async def update_meeting(meeting_id: str, meeting_update: MeetingUpdate):
    """Update a meeting"""
    return await MeetingService.update_meeting(meeting_id, meeting_update)

@app.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """Delete a meeting"""
    return await MeetingService.delete_meeting(meeting_id)

@app.put("/meetings/{meeting_id}/keywords", response_model=Meeting)
async def update_meeting_keywords(meeting_id: str, keywords_update: KeywordsUpdate):
    """Update keywords for a specific meeting"""
    return await MeetingService.update_keywords(meeting_id, keywords_update)

@app.post("/webhook/transcription-completed")
async def transcription_webhook(result: TranscriptionWebhookResult):
    """Receive transcription results from transcription service"""
    return await TranscriptionWebhookService.process_webhook(result, manager)

@app.websocket("/ws/meeting/{meeting_id}/audio")
async def websocket_audio_endpoint(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for audio streaming and real-time transcription"""
    # Generate unique session ID for this WebSocket connection
    session_id = str(uuid.uuid4())[:8]

    try:
        # Connect to the manager (may raise WebSocketException if limit reached)
        await manager.connect(websocket, meeting_id, session_id)
    except Exception as e:
        logger.error(f"Failed to connect WebSocket for meeting {meeting_id}: {e}")
        return

    try:
        # Validate meeting exists
        if not ObjectId.is_valid(meeting_id):
            await manager.send_to_connection(meeting_id, session_id, "Error: Invalid meeting ID")
            await websocket.close()
            return

        # Update meeting status only if this is the first connection
        if manager.get_connection_count(meeting_id) == 1:
            await MeetingService.update_status(meeting_id, "transcribing")

        await manager.send_notification(
            meeting_id,
            "transcription_status",
            "connected",
            f"Ready to receive audio chunks (session: {session_id})"
        )
        logger.info(f"WebSocket session {session_id} started for meeting {meeting_id}")

        while True:
            data = await websocket.receive_bytes()

            try:
                # Save audio chunk using audio service
                save_result = await audio_service.save_audio_chunk(meeting_id, session_id, data)

                chunk_number = save_result["chunk_number"]
                filename = save_result["filename"]
                file_size = save_result["file_size"]

                # Send acknowledgment to the specific connection that sent the audio
                await manager.send_to_connection(
                    meeting_id,
                    session_id,
                    f"Audio chunk {chunk_number} received: {file_size} bytes"
                )

                # Submit to transcription service
                job_id = await transcription_service.submit_transcription_job(meeting_id, filename)

                if job_id:
                    # Broadcast processing status to all connections for this meeting
                    await manager.send_notification(
                        meeting_id,
                        "transcription_status",
                        "processing",
                        f"Processing audio chunk {chunk_number} ({file_size} bytes)"
                    )
                    logger.info(f"Submitted job {job_id} for audio chunk {filename}")
                else:
                    # Broadcast error to all connections for this meeting
                    await manager.send_notification(
                        meeting_id,
                        "transcription_status",
                        "error",
                        f"Failed to submit transcription job for chunk {chunk_number}"
                    )
                    logger.error(f"Failed to submit job for audio chunk {filename}")

            except Exception as e:
                logger.error(f"Error processing audio chunk for meeting {meeting_id}: {e}")
                await manager.send_notification(
                    meeting_id,
                    "transcription_status",
                    "error",
                    f"Error processing audio: {str(e)}"
                )

    except WebSocketDisconnect:
        manager.disconnect(meeting_id, session_id)
        audio_service.cleanup_session(session_id)

        # Only update meeting status if this was the last connection
        if manager.get_connection_count(meeting_id) == 0:
            await MeetingService.update_status(meeting_id, "created")

        logger.info(f"WebSocket session {session_id} disconnected for meeting {meeting_id}")

    except Exception as e:
        logger.error(f"WebSocket error for meeting {meeting_id}: {e}")
        manager.disconnect(meeting_id, session_id)
        audio_service.cleanup_session(session_id)

        # Only update meeting status if this was the last connection
        if manager.get_connection_count(meeting_id) == 0:
            await MeetingService.update_status(meeting_id, "created")

        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except:
            pass