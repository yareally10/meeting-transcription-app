from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import List, Optional
import os
import logging

logger = logging.getLogger(__name__)

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = "meeting_db"

class DatabaseManager:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database = None
        
    async def connect_to_database(self):
        """Create database connection"""
        self.client = AsyncIOMotorClient(MONGODB_URL)
        self.database = self.client[DATABASE_NAME]
        
        try:
            await self.client.admin.command('ping')
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise
            
    async def close_database_connection(self):
        """Close database connection"""
        if self.client:
            self.client.close()
            logger.info("Database connection closed")

    def get_collection(self, collection_name: str):
        """Get collection from database"""
        if not self.database:
            raise Exception("Database not connected")
        return self.database[collection_name]

db_manager = DatabaseManager()

async def get_database():
    """Dependency to get database instance"""
    if not db_manager.database:
        await db_manager.connect_to_database()
    return db_manager.database