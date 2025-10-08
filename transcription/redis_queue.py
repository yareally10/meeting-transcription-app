"""Redis-based queue manager for transcription jobs."""

import redis
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RedisQueue:
    """Redis-based job queue with pub/sub support."""

    def __init__(self, redis_url: str):
        """Initialize Redis connection.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
        """
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.queue_key = "transcription:job_queue"
        self.processing_key = "transcription:processing"

    def ping(self) -> bool:
        """Check if Redis is accessible."""
        try:
            return self.redis_client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def enqueue(self, job_data: Dict[str, Any]) -> bool:
        """Add a job to the queue.

        Args:
            job_data: Job data dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            job_json = json.dumps(job_data)
            self.redis_client.rpush(self.queue_key, job_json)
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue job: {e}")
            return False

    def dequeue(self, timeout: int = 1) -> Optional[Dict[str, Any]]:
        """Get the next job from the queue (blocking).

        Args:
            timeout: Timeout in seconds for blocking pop

        Returns:
            Job data dictionary or None if timeout/error
        """
        try:
            result = self.redis_client.blpop(self.queue_key, timeout=timeout)
            if result:
                _, job_json = result
                return json.loads(job_json)
            return None
        except Exception as e:
            logger.error(f"Failed to dequeue job: {e}")
            return None

    def get_queue_size(self) -> int:
        """Get the current queue size.

        Returns:
            Number of jobs in queue
        """
        try:
            return self.redis_client.llen(self.queue_key)
        except Exception as e:
            logger.error(f"Failed to get queue size: {e}")
            return 0

    def clear_queue(self) -> bool:
        """Clear all jobs from the queue.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.redis_client.delete(self.queue_key)
            return True
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return False
