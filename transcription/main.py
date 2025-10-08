from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime, timezone
from pathlib import Path

from config import config
from job_manager import JobManager
from transcription_worker import TranscriptionWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate configuration
config_error = config.validate()
if config_error:
    logger.warning(config_error)

app = FastAPI(title="Meeting Transcription Service", version="1.0.0")

# Only allow requests from the web server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.web_server_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize job manager with Redis
try:
    job_manager = JobManager(config.redis_url)
    logger.info(f"Connected to Redis at {config.redis_url}")
except Exception as e:
    logger.error(f"Failed to initialize JobManager with Redis: {e}")
    raise

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

# Start worker threads
workers = []
for i in range(config.max_concurrent_jobs):
    worker = TranscriptionWorker(job_manager, i + 1)
    thread = worker.start_thread()
    workers.append((worker, thread))

@app.get("/")
async def root():
    return {"message": "Meeting Transcription Service", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_size": job_manager.get_queue_size(),
        "max_workers": config.max_concurrent_jobs
    }

@app.get("/stats")
async def get_stats():
    """Get processing statistics"""
    return job_manager.get_stats()

@app.post("/transcribe")
async def transcribe_audio_file(request: TranscriptionRequest):
    """Accept single audio file for transcription processing"""
    
    if not config.openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Check if audio file exists in audio folder
    audio_file_path = Path(config.shared_audio_path) / request.meeting_id / "audio" / request.filename
    if not audio_file_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {request.filename}")
    
    try:
        # Create and queue job
        job_id = job_manager.create_job(request.meeting_id, request.filename, request.webhook_url)
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Audio file {request.filename} queued for transcription",
            "queue_position": job_manager.get_queue_size()
        }
        
    except Exception as e:
        logger.error(f"Error processing transcription request: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process transcription request: {str(e)}")

@app.get("/job/{job_id}")
async def get_job_status_endpoint(job_id: str):
    """Get status of a specific transcription job"""
    job_status = job_manager.get_job_status(job_id)
    if not job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatus(**job_status)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)