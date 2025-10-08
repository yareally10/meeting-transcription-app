"""Job management for transcription service using Redis."""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
import redis
import json

from redis_queue import RedisQueue

logger = logging.getLogger(__name__)


class JobManager:
    """Manages transcription jobs and their status using Redis."""

    def __init__(self, redis_url: str):
        """Initialize JobManager with Redis backend.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.redis_queue = RedisQueue(redis_url)
        self.job_status_prefix = "transcription:job:"

        # Test Redis connection
        if not self.redis_queue.ping():
            raise ConnectionError("Failed to connect to Redis")

        logger.info("JobManager initialized with Redis backend")

    def create_job(self, meeting_id: str, filename: str, webhook_url: str) -> str:
        """Create a new transcription job and return job ID."""
        job_id = str(uuid.uuid4())

        # Store job status in Redis
        job_status = {
            "job_id": job_id,
            "status": "queued",
            "meeting_id": meeting_id,
            "filename": filename,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
            "error_message": None
        }

        job_status_key = f"{self.job_status_prefix}{job_id}"
        self.redis_client.setex(
            job_status_key,
            86400,  # TTL: 24 hours
            json.dumps(job_status)
        )

        # Queue job for processing
        job_data = {
            "job_id": job_id,
            "meeting_id": meeting_id,
            "filename": filename,
            "webhook_url": webhook_url
        }

        self.redis_queue.enqueue(job_data)
        logger.info(f"Queued transcription job {job_id} for meeting {meeting_id}, file {filename}")

        return job_id

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job from Redis."""
        job_status_key = f"{self.job_status_prefix}{job_id}"
        job_data = self.redis_client.get(job_status_key)

        if job_data:
            return json.loads(job_data)
        return None

    def update_job_status(self, job_id: str, status: str, error_message: Optional[str] = None):
        """Update job status in Redis."""
        job_status = self.get_job_status(job_id)

        if job_status:
            job_status["status"] = status
            if error_message:
                job_status["error_message"] = error_message
            if status in ["completed", "failed"]:
                job_status["completed_at"] = datetime.now(timezone.utc).isoformat()

            job_status_key = f"{self.job_status_prefix}{job_id}"
            self.redis_client.setex(
                job_status_key,
                86400,  # TTL: 24 hours
                json.dumps(job_status)
            )

    def get_next_job(self, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """Get the next job from the Redis queue."""
        return self.redis_queue.dequeue(timeout=timeout)

    def mark_job_done(self):
        """Mark current job as done (no-op for Redis, kept for compatibility)."""
        pass

    def get_queue_size(self) -> int:
        """Get current queue size from Redis."""
        return self.redis_queue.get_queue_size()

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics from Redis."""
        # Scan for all job keys
        job_keys = []
        cursor = 0
        while True:
            cursor, keys = self.redis_client.scan(
                cursor,
                match=f"{self.job_status_prefix}*",
                count=100
            )
            job_keys.extend(keys)
            if cursor == 0:
                break

        # Count jobs by status
        total_jobs = len(job_keys)
        completed_jobs = 0
        failed_jobs = 0
        processing_jobs = 0
        queued_jobs = 0

        for key in job_keys:
            job_data = self.redis_client.get(key)
            if job_data:
                job_status = json.loads(job_data)
                status = job_status.get("status", "")
                if status == "completed":
                    completed_jobs += 1
                elif status == "failed":
                    failed_jobs += 1
                elif status == "processing":
                    processing_jobs += 1
                elif status == "queued":
                    queued_jobs += 1

        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "failed_jobs": failed_jobs,
            "processing_jobs": processing_jobs,
            "queued_jobs": queued_jobs,
            "queue_size": self.get_queue_size()
        }