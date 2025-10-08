"""Meeting service for CRUD operations."""

import logging
from datetime import datetime, timezone
from typing import List
from bson import ObjectId
from fastapi import HTTPException

from database import database
from models import Meeting, MeetingCreate, MeetingUpdate, KeywordsUpdate

logger = logging.getLogger(__name__)


class MeetingService:
    """Service for meeting operations."""

    @staticmethod
    async def create_meeting(meeting_data: MeetingCreate) -> Meeting:
        """Create a new meeting."""
        db = database.get_db()

        meeting_dict = meeting_data.model_dump()
        meeting_dict.update({
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
        """Get all meetings."""
        db = database.get_db()
        meetings = []

        cursor = db.meetings.find({}).sort("created_at", -1)
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
