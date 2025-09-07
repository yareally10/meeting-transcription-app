"""Database connection and operations."""

import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from config import config

logger = logging.getLogger(__name__)

class Database:
    """Database connection manager."""
    
    client: Optional[AsyncIOMotorClient] = None
    db = None
    
    @classmethod
    async def connect(cls):
        """Initialize database connection."""
        cls.client = AsyncIOMotorClient(config.MONGODB_URL)
        cls.db = cls.client[config.DATABASE_NAME]
        
        try:
            await cls.client.admin.command('ping')
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
    
    @classmethod
    async def close(cls):
        """Close database connection."""
        if cls.client:
            cls.client.close()
            logger.info("Database connection closed")
    
    @classmethod
    def get_db(cls):
        """Get database instance."""
        if cls.db is None:
            raise RuntimeError("Database not initialized. Call connect() first.")
        return cls.db

# Global database instance
database = Database()