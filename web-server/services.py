"""Business logic services."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import HTTPException

from database import database
from models import Meeting, MeetingCreate, MeetingUpdate, KeywordsUpdate, TranscriptionWebhookResult
from config import config

logger = logging.getLogger(__name__)


class MeetingService:
    """Service for meeting operations."""
    
    @staticmethod
    async def create_meeting(meeting_data: MeetingCreate) -> Meeting:
        """Create a new meeting."""
        db = database.get_db()
        
        meeting_dict = meeting_data.model_dump()
        meeting_dict.update({
            "created_by": config.DEFAULT_USER_ID,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "created",
            "full_transcription": None
        })
        
        result = await db.meetings.insert_one(meeting_dict)
        created_meeting = await db.meetings.find_one({"_id": result.inserted_id})
        
        if not created_meeting:
            raise HTTPException(status_code=500, detail="Failed to create meeting")
        
        created_meeting["id"] = str(created_meeting["_id"])
        return Meeting(**created_meeting)
    
    @staticmethod
    async def get_meetings() -> List[Meeting]:
        """Get all meetings for the current user."""
        db = database.get_db()
        meetings = []
        
        cursor = db.meetings.find({"created_by": config.DEFAULT_USER_ID}).sort("created_at", -1)
        async for meeting in cursor:
            meeting["id"] = str(meeting["_id"])
            meetings.append(Meeting(**meeting))
        
        return meetings
    
    @staticmethod
    async def get_meeting(meeting_id: str) -> Meeting:
        """Get a specific meeting by ID."""
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        db = database.get_db()
        meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting["id"] = str(meeting["_id"])
        return Meeting(**meeting)
    
    @staticmethod
    async def update_meeting(meeting_id: str, meeting_update: MeetingUpdate) -> Meeting:
        """Update a meeting."""
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        update_data = {k: v for k, v in meeting_update.model_dump().items() if v is not None}
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid update data provided")
        
        update_data["updated_at"] = datetime.now(timezone.utc)
        
        db = database.get_db()
        result = await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        updated_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_meeting["id"] = str(updated_meeting["_id"])
        return Meeting(**updated_meeting)
    
    @staticmethod
    async def delete_meeting(meeting_id: str) -> dict:
        """Delete a meeting."""
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        db = database.get_db()
        result = await db.meetings.delete_one({"_id": ObjectId(meeting_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return {"message": "Meeting deleted successfully"}
    
    @staticmethod
    async def update_keywords(meeting_id: str, keywords_update: KeywordsUpdate) -> Meeting:
        """Update keywords for a specific meeting."""
        if not ObjectId.is_valid(meeting_id):
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        update_data = {
            "keywords": keywords_update.keywords,
            "updated_at": datetime.now(timezone.utc)
        }
        
        db = database.get_db()
        result = await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        updated_meeting = await db.meetings.find_one({"_id": ObjectId(meeting_id)})
        updated_meeting["id"] = str(updated_meeting["_id"])
        return Meeting(**updated_meeting)
    
    @staticmethod
    async def update_status(meeting_id: str, status: str) -> None:
        """Update meeting status."""
        if not ObjectId.is_valid(meeting_id):
            return
        
        db = database.get_db()
        await db.meetings.update_one(
            {"_id": ObjectId(meeting_id)},
            {"$set": {
                "status": status,
                "updated_at": datetime.now(timezone.utc)
            }}
        )


class TranscriptionWebhookService:
    """Service for handling transcription webhooks."""
    
    @staticmethod
    async def process_webhook(result: TranscriptionWebhookResult, manager) -> dict:
        """Process transcription webhook result."""
        logger.info(f"Received transcription webhook for meeting {result.meeting_id}, file {result.filename}, status: {result.status}")
        
        if not ObjectId.is_valid(result.meeting_id):
            logger.error(f"Invalid meeting ID in webhook: {result.meeting_id}")
            raise HTTPException(status_code=400, detail="Invalid meeting ID")
        
        db = database.get_db()
        meeting = await db.meetings.find_one({"_id": ObjectId(result.meeting_id)})
        if not meeting:
            logger.error(f"Meeting not found for webhook: {result.meeting_id}")
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if result.status == "completed":
            await TranscriptionWebhookService._handle_success(result, meeting, db, manager)
        elif result.status == "failed":
            await TranscriptionWebhookService._handle_failure(result, manager)
        
        logger.info(f"Successfully processed webhook for meeting {result.meeting_id}, file {result.filename}")
        return {"status": "success", "message": "Webhook processed"}
    
    @staticmethod
    async def _handle_success(result: TranscriptionWebhookResult, meeting: dict, db, manager):
        """Handle successful transcription."""
        logger.info(f"Processing successful transcription for meeting {result.meeting_id}, file {result.filename}")
        
        if not result.transcription_text:
            logger.warning(f"No transcription text received for file {result.filename} in meeting {result.meeting_id}")
            await manager.send_notification(
                result.meeting_id, 
                "transcription_status", 
                "warning", 
                f"No transcription text received for {result.filename}"
            )
            return
        
        # Update meeting with transcription result
        current_transcription = meeting.get("full_transcription", "") or ""
        
        if current_transcription:
            updated_transcription = current_transcription + " " + result.transcription_text
        else:
            updated_transcription = result.transcription_text
        
        logger.info(f"Updating meeting {result.meeting_id} with {len(result.transcription_text)} characters from {result.filename}")
        
        await db.meetings.update_one(
            {"_id": ObjectId(result.meeting_id)},
            {"$set": {
                "full_transcription": updated_transcription,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        logger.info(f"Successfully updated meeting {result.meeting_id} with transcription from {result.filename}")
        
        # Send success notification
        await manager.send_notification(
            result.meeting_id, 
            "transcription_status", 
            "completed", 
            f"Transcription completed for audio chunk ({result.filename})",
            {
                "text_snippet": result.transcription_text[:100] + "..." if len(result.transcription_text) > 100 else result.transcription_text,
                "full_text": result.transcription_text
            }
        )
    
    @staticmethod
    async def _handle_failure(result: TranscriptionWebhookResult, manager):
        """Handle failed transcription."""
        logger.error(f"Transcription failed for meeting {result.meeting_id}, file {result.filename}: {result.error_message or 'Unknown error'}")
        
        await manager.send_notification(
            result.meeting_id, 
            "transcription_status", 
            "failed", 
            f"Transcription failed for {result.filename}: {result.error_message or 'Unknown error'}"
        )