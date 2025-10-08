"""Transcription worker for processing audio files."""

import threading
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
import openai

from config import config
from job_manager import JobManager
from webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)


class TranscriptionWorker:
    """Worker class for processing transcription jobs."""
    
    def __init__(self, job_manager: JobManager, worker_id: int):
        self.job_manager = job_manager
        self.worker_id = worker_id
        self.webhook_handler = WebhookHandler()
        
        # Set OpenAI API key
        if config.openai_api_key:
            openai.api_key = config.openai_api_key
    
    def process_job(self, job_data: Dict[str, Any]) -> None:
        """Process a single transcription job."""
        job_id = job_data["job_id"]
        meeting_id = job_data["meeting_id"]
        filename = job_data["filename"]
        webhook_url = job_data["webhook_url"]
        
        logger.info(f"Worker {self.worker_id}: Starting transcription job {job_id} for meeting {meeting_id}, file {filename}")
        self.job_manager.update_job_status(job_id, "processing")
        
        start_time = datetime.now()
        
        try:
            # Build file path - files are in audio folder
            audio_file_path = Path(config.shared_audio_path) / meeting_id / "audio" / filename
            
            if not audio_file_path.exists():
                raise FileNotFoundError(f"Audio file not found: {audio_file_path}")
            
            logger.info(f"Worker {self.worker_id}: Processing audio file: {audio_file_path}")
            
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
            
            # Prepare success webhook result
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
            webhook_success = self.webhook_handler.send_webhook_sync(webhook_url, result_data)
            
            if webhook_success:
                self.job_manager.update_job_status(job_id, "completed")
                logger.info(f"Worker {self.worker_id}: Transcription job {job_id} completed successfully")
            else:
                logger.warning(f"Worker {self.worker_id}: Job {job_id} completed but webhook failed")
                self.job_manager.update_job_status(job_id, "completed")
            
        except Exception as e:
            error_message = str(e)
            processing_time = (datetime.now() - start_time).total_seconds()
            
            logger.error(f"Worker {self.worker_id}: Transcription job {job_id} failed: {error_message}")
            
            # Prepare failure webhook result
            result_data = {
                "job_id": job_id,
                "meeting_id": meeting_id,
                "filename": filename,
                "status": "failed",
                "error_message": error_message,
                "processing_time": processing_time,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
            # Send failure webhook
            self.webhook_handler.send_webhook_sync(webhook_url, result_data)
            self.job_manager.update_job_status(job_id, "failed", error_message)
    
    def run(self) -> None:
        """Main worker loop that processes jobs from the queue."""
        logger.info(f"Starting transcription worker {self.worker_id}")
        while True:
            try:
                job_data = self.job_manager.get_next_job(timeout=1)
                if job_data:
                    self.process_job(job_data)
                    self.job_manager.mark_job_done()
            except Exception as e:
                logger.error(f"Worker {self.worker_id} error: {e}")
    
    def start_thread(self) -> threading.Thread:
        """Start the worker in a daemon thread."""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        logger.info(f"Started worker thread {self.worker_id}")
        return thread