"""Job management for transcription service."""

import queue
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class JobManager:
    """Manages transcription jobs and their status."""
    
    def __init__(self):
        self.job_queue: queue.Queue = queue.Queue()
        self.job_status: Dict[str, Dict[str, Any]] = {}
        self.job_status_lock = threading.Lock()
    
    def create_job(self, meeting_id: str, filename: str, webhook_url: str) -> str:
        """Create a new transcription job and return job ID."""
        job_id = str(uuid.uuid4())
        
        with self.job_status_lock:
            self.job_status[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "meeting_id": meeting_id,
                "filename": filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": None,
                "error_message": None
            }
        
        job_data = {
            "job_id": job_id,
            "meeting_id": meeting_id,
            "filename": filename,
            "webhook_url": webhook_url
        }
        
        self.job_queue.put(job_data)
        logger.info(f"Queued transcription job {job_id} for meeting {meeting_id}, file {filename}")
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        with self.job_status_lock:
            return self.job_status.get(job_id)
    
    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None):
        """Thread-safe job status update."""
        with self.job_status_lock:
            if job_id in self.job_status:
                self.job_status[job_id]["status"] = status
                if error_message:
                    self.job_status[job_id]["error_message"] = error_message
                if status in ["completed", "failed"]:
                    self.job_status[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    
    def get_next_job(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue."""
        try:
            return self.job_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def mark_job_done(self):
        """Mark current job as done in the queue."""
        self.job_queue.task_done()
    
    def get_queue_size(self) -> int:
        """Get current queue size."""
        return self.job_queue.qsize()
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        with self.job_status_lock:
            total_jobs = len(self.job_status)
            completed_jobs = sum(1 for job in self.job_status.values() if job["status"] == "completed")
            failed_jobs = sum(1 for job in self.job_status.values() if job["status"] == "failed")
            processing_jobs = sum(1 for job in self.job_status.values() if job["status"] == "processing")
            queued_jobs = sum(1 for job in self.job_status.values() if job["status"] == "queued")
        
        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "processing_jobs": processing_jobs,
            "queued_jobs": queued_jobs,
            "queue_size": self.get_queue_size()
        }