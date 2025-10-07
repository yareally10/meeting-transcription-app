from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import os
import logging
from contextlib import asynccontextmanager
from bson import ObjectId

from config import config
from database import database
from models import (
    Meeting, MeetingCreate, MeetingUpdate, KeywordsUpdate, 
    TranscriptionWebhookResult
)
from services import MeetingService, TranscriptionWebhookService
from audio_service import AudioFileService
from transcription_service import TranscriptionService
from websocket_manager import ConnectionManager

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
    """WebSocket endpoint for audio streaming and real-time transcription (VAD mode)"""
    await manager.connect(websocket, meeting_id)

    chunk_counter = 0

    try:
        # Validate meeting exists
        if not ObjectId.is_valid(meeting_id):
            await websocket.send_text("Error: Invalid meeting ID")
            await websocket.close()
            return

        # Update meeting status
        await MeetingService.update_status(meeting_id, "transcribing")
        await manager.send_notification(meeting_id, "transcription_status", "connected", "Ready to receive VAD audio chunks")

        while True:
            data = await websocket.receive_bytes()

            try:
                # Save VAD chunk directly (frontend sends complete WebM files)
                from pathlib import Path
                from datetime import datetime, timezone

                # Create meeting directory structure
                meeting_dir = Path(config.SHARED_AUDIO_PATH) / meeting_id / "processed"
                meeting_dir.mkdir(parents=True, exist_ok=True)

                # Generate unique filename for this VAD chunk
                timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
                chunk_filename = f"vad_chunk_{chunk_counter}_{timestamp}.webm"
                chunk_file_path = meeting_dir / chunk_filename

                # Save the chunk directly (it's already a complete WebM file from frontend)
                with open(chunk_file_path, "wb") as f:
                    f.write(data)

                chunk_counter += 1

                logger.info(f"Saved VAD chunk {chunk_counter} for meeting {meeting_id}: {chunk_filename} ({len(data)} bytes)")
                await websocket.send_text(f"VAD chunk {chunk_counter} received: {len(data)} bytes")

                # Submit directly to transcription service
                job_id = await transcription_service.submit_transcription_job(meeting_id, chunk_filename)

                if job_id:
                    await manager.send_notification(
                        meeting_id,
                        "transcription_status",
                        "processing",
                        f"Processing VAD chunk {chunk_counter} ({len(data)} bytes)"
                    )
                    logger.info(f"Submitted job {job_id} for VAD chunk {chunk_filename}")
                else:
                    await manager.send_notification(
                        meeting_id,
                        "transcription_status",
                        "error",
                        f"Failed to submit transcription job for chunk {chunk_counter}"
                    )
                    logger.error(f"Failed to submit job for VAD chunk {chunk_filename}")

            except Exception as e:
                logger.error(f"Error processing VAD chunk for meeting {meeting_id}: {e}")
                await manager.send_notification(meeting_id, "transcription_status", "error", f"Error processing audio: {str(e)}")

    except WebSocketDisconnect:
        manager.disconnect(meeting_id)
        await MeetingService.update_status(meeting_id, "created")
        logger.info(f"WebSocket disconnected for meeting {meeting_id}. Total VAD chunks received: {chunk_counter}")

    except Exception as e:
        logger.error(f"WebSocket error for meeting {meeting_id}: {e}")
        manager.disconnect(meeting_id)
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close()
        except:
            pass