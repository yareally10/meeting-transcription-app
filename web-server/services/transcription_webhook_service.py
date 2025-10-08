"""Service for handling transcription webhook callbacks."""

import logging
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException

from database import database
from models import TranscriptionWebhookResult

logger = logging.getLogger(__name__)


class TranscriptionWebhookService:
    """Service for handling transcription webhooks."""

    @staticmethod
    async def process_webhook(result: TranscriptionWebhookResult, manager) -> dict:
        """Process transcription webhook result.

        Args:
            result: Transcription webhook result data
            manager: WebSocket manager for sending notifications

        Returns:
            Success response dictionary

        Raises:
            HTTPException: If meeting ID is invalid or meeting not found
        """
        logger.info(
            f"Received transcription webhook for meeting {result.meeting_id}, "
            f"file {result.filename}, status: {result.status}"
        )

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

        logger.info(
            f"Successfully processed webhook for meeting {result.meeting_id}, "
            f"file {result.filename}"
        )
        return {"status": "success", "message": "Webhook processed"}

    @staticmethod
    async def _handle_success(
        result: TranscriptionWebhookResult,
        meeting: dict,
        db,
        manager
    ):
        """Handle successful transcription.

        Args:
            result: Transcription webhook result
            meeting: Meeting document from database
            db: Database connection
            manager: WebSocket manager
        """
        logger.info(
            f"Processing successful transcription for meeting {result.meeting_id}, "
            f"file {result.filename}"
        )

        if not result.transcription_text:
            logger.warning(
                f"No transcription text received for file {result.filename} "
                f"in meeting {result.meeting_id}"
            )
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

        logger.info(
            f"Updating meeting {result.meeting_id} with "
            f"{len(result.transcription_text)} characters from {result.filename}"
        )

        await db.meetings.update_one(
            {"_id": ObjectId(result.meeting_id)},
            {"$set": {
                "full_transcription": updated_transcription,
                "updated_at": datetime.now(timezone.utc)
            }}
        )

        logger.info(
            f"Successfully updated meeting {result.meeting_id} with "
            f"transcription from {result.filename}"
        )

        # Send success notification
        text_snippet = (
            result.transcription_text[:100] + "..."
            if len(result.transcription_text) > 100
            else result.transcription_text
        )

        await manager.send_notification(
            result.meeting_id,
            "transcription_status",
            "completed",
            f"Transcription completed for audio chunk ({result.filename})",
            {
                "text_snippet": text_snippet,
                "full_text": result.transcription_text
            }
        )

    @staticmethod
    async def _handle_failure(result: TranscriptionWebhookResult, manager):
        """Handle failed transcription.

        Args:
            result: Transcription webhook result
            manager: WebSocket manager
        """
        logger.error(
            f"Transcription failed for meeting {result.meeting_id}, "
            f"file {result.filename}: {result.error_message or 'Unknown error'}"
        )

        await manager.send_notification(
            result.meeting_id,
            "transcription_status",
            "failed",
            f"Transcription failed for {result.filename}: "
            f"{result.error_message or 'Unknown error'}"
        )
