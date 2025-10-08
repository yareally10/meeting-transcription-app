"""WebSocket connection manager for real-time notifications."""

import logging
import json
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket connection manager for real-time notifications."""

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str):
        """Accept a WebSocket connection and store it.

        Args:
            websocket: WebSocket connection
            meeting_id: Meeting identifier
        """
        await websocket.accept()
        self.active_connections[meeting_id] = websocket
        logger.info(f"WebSocket connected for meeting {meeting_id}")

    def disconnect(self, meeting_id: str):
        """Remove a WebSocket connection.

        Args:
            meeting_id: Meeting identifier
        """
        if meeting_id in self.active_connections:
            del self.active_connections[meeting_id]
            logger.info(f"WebSocket disconnected for meeting {meeting_id}")

    async def send_notification(
        self,
        meeting_id: str,
        notification_type: str,
        status: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send a notification message to a specific meeting's WebSocket connection.

        Args:
            meeting_id: Meeting identifier
            notification_type: Type of notification (e.g., "transcription_status")
            status: Status of the notification (e.g., "completed", "failed")
            message: Notification message
            data: Optional additional data to include
        """
        if meeting_id in self.active_connections:
            try:
                notification = {
                    "type": notification_type,
                    "status": status,
                    "message": message,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if data:
                    notification["data"] = data

                await self.active_connections[meeting_id].send_text(
                    json.dumps(notification)
                )
                logger.info(f"Sent notification to meeting {meeting_id}: {message}")
            except Exception as e:
                logger.error(
                    f"Failed to send notification to meeting {meeting_id}: {e}"
                )
                # Remove stale connection
                self.disconnect(meeting_id)
