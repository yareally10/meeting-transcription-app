"""Configuration management for the transcription service."""

import os
from typing import Optional


class Config:
    """Configuration settings for the transcription service."""

    def __init__(self):
        self.web_server_url = os.getenv("WEB_SERVER_URL", "http://localhost:8000")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        self.shared_audio_path = "/app/shared_audio"
        self.webhook_timeout = 30.0

    def validate(self) -> Optional[str]:
        """Validate configuration and return error message if invalid."""
        if not self.openai_api_key:
            return "OPENAI_API_KEY not set - transcription will fail"

        if self.max_concurrent_jobs <= 0:
            return "MAX_CONCURRENT_JOBS must be greater than 0"

        if not self.redis_url:
            return "REDIS_URL not set - job queue will fail"

        return None


# Global config instance
config = Config()