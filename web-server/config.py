"""Configuration settings for the web server."""

import os
from typing import Optional

class Config:
    """Application configuration."""
    
    # Database
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = "meeting_db"
    
    # Services
    TRANSCRIPTION_SERVICE_URL: str = os.getenv("TRANSCRIPTION_SERVICE_URL", "http://localhost:8001")
    WEB_SERVER_URL: str = os.getenv("WEB_SERVER_URL", "http://localhost:8000")
    
    # File storage
    SHARED_AUDIO_PATH: str = "/app/shared_audio"
    
    # Authentication (temporary)
    DEFAULT_USER_ID: str = "user123"
    
    # CORS
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    @classmethod
    def get_webhook_url(cls) -> str:
        """Get the webhook URL for transcription callbacks."""
        return f"{cls.WEB_SERVER_URL}/webhook/transcription-completed"

# Global config instance
config = Config()