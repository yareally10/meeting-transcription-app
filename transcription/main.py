from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os
import asyncio
import httpx
import threading
import queue
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Meeting Transcription Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
SHARED_AUDIO_PATH = "/app/shared_audio"

# Set OpenAI API key
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    logger.warning("OPENAI_API_KEY not set - transcription will fail")

# Internal job queue and status tracking
job_queue = queue.Queue()
job_status: Dict[str, Dict[str, Any]] = {}
job_status_lock = threading.Lock()

class TranscriptionRequest(BaseModel):
    meeting_id: str
    filename: str
    webhook_url: str

class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    created_at: str
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

def update_job_status(job_id: str, status: str, error_message: Optional[str] = None):
    """Thread-safe job status update"""
    with job_status_lock:
        if job_id in job_status:
            job_status[job_id]["status"] = status
            if error_message:
                job_status[job_id]["error_message"] = error_message
            if status in ["completed", "failed"]:
                job_status[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

async def send_webhook(webhook_url: str, result_data: Dict[str, Any]):
    """Send transcription result to web server via webhook"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(webhook_url, json=result_data, timeout=30.0)
            if response.status_code == 200:
                logger.info(f"Webhook sent successfully to {webhook_url}")
            else:
                logger.error(f"Webhook failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Error sending webhook to {webhook_url}: {e}")

def process_transcription_job(job_data: Dict[str, Any]):
    """Background worker function to process transcription jobs"""
    job_id = job_data["job_id"]
    meeting_id = job_data["meeting_id"]
    filename = job_data["filename"]
    webhook_url = job_data["webhook_url"]
    
    logger.info(f"Starting transcription job {job_id} for meeting {meeting_id}, file {filename}")
    update_job_status(job_id, "processing")
    
    start_time = datetime.now()
    
    try:
        # Build file path
        audio_file_path = Path(SHARED_AUDIO_PATH) / meeting_id / "raw" / filename
        
        if not audio_file_path.exists():
            raise Exception(f"Audio file not found: {audio_file_path}")
        
        logger.info(f"Processing audio file: {audio_file_path}")
        
        # Process audio with OpenAI Whisper
        with open(audio_file_path, 'rb') as audio_file:
            response = openai.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json"
            )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Extract transcription results
        transcription_text = response.text
        confidence = getattr(response, 'confidence', 0.9)  # Whisper doesn't always provide confidence
        
        # Prepare webhook result
        result_data = {
            "job_id": job_id,
            "meeting_id": meeting_id,
            "filename": filename,
            "transcription_text": transcription_text,
            "confidence": confidence,
            "processing_time": processing_time,
            "status": "completed",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Send webhook
        asyncio.run(send_webhook(webhook_url, result_data))
        
        # Update job status
        update_job_status(job_id, "completed")
        logger.info(f"Transcription job {job_id} completed successfully")
        
    except Exception as e:
        error_message = str(e)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        logger.error(f"Transcription job {job_id} failed: {error_message}")
        
        # Send failure webhook
        result_data = {
            "job_id": job_id,
            "meeting_id": meeting_id,
            "filename": filename,
            "status": "failed",
            "error_message": error_message,
            "processing_time": processing_time,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        asyncio.run(send_webhook(webhook_url, result_data))
        update_job_status(job_id, "failed", error_message)

def worker_thread():
    """Background worker thread that processes jobs from the queue"""
    logger.info("Starting transcription worker thread")
    while True:
        try:
            job_data = job_queue.get(timeout=1.0)
            process_transcription_job(job_data)
            job_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"Worker thread error: {e}")

# Start worker threads
for i in range(MAX_CONCURRENT_JOBS):
    thread = threading.Thread(target=worker_thread, daemon=True)
    thread.start()
    logger.info(f"Started worker thread {i+1}")

@app.get("/")
async def root():
    return {"message": "Meeting Transcription Service", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_size": job_queue.qsize(),
        "max_workers": MAX_CONCURRENT_JOBS
    }

@app.get("/stats")
async def get_stats():
    """Get processing statistics"""
    with job_status_lock:
        total_jobs = len(job_status)
        completed_jobs = sum(1 for job in job_status.values() if job["status"] == "completed")
        failed_jobs = sum(1 for job in job_status.values() if job["status"] == "failed")
        processing_jobs = sum(1 for job in job_status.values() if job["status"] == "processing")
        queued_jobs = sum(1 for job in job_status.values() if job["status"] == "queued")
    
    return {
        "total_jobs": total_jobs,
        "completed_jobs": completed_jobs,
        "failed_jobs": failed_jobs,
        "processing_jobs": processing_jobs,
        "queued_jobs": queued_jobs,
        "queue_size": job_queue.qsize()
    }

@app.post("/transcribe")
async def transcribe_audio_file(request: TranscriptionRequest):
    """Accept single audio file for transcription processing"""
    
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Check if audio file exists
    audio_file_path = Path(SHARED_AUDIO_PATH) / request.meeting_id / "raw" / request.filename
    if not audio_file_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {request.filename}")
    
    # Generate unique job ID
    job_id = str(uuid.uuid4())
    
    try:
        # Create job entry
        with job_status_lock:
            job_status[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "meeting_id": request.meeting_id,
                "filename": request.filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "error_message": None
            }
        
        # Add job to queue
        job_data = {
            "job_id": job_id,
            "meeting_id": request.meeting_id,
            "filename": request.filename,
            "webhook_url": request.webhook_url
        }
        
        job_queue.put(job_data)
        
        logger.info(f"Queued transcription job {job_id} for meeting {request.meeting_id}, file {request.filename}")
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Audio file {request.filename} queued for transcription",
            "queue_position": job_queue.qsize()
        }
        
    except Exception as e:
        logger.error(f"Error processing transcription request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process transcription request: {str(e)}")

@app.get("/job/{job_id}")
async def get_job_status(job_id: str):
    """Get status of a specific transcription job"""
    with job_status_lock:
        if job_id not in job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatus(**job_status[job_id])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)