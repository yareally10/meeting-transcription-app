"""WebSocket connection manager for real-time notifications."""

import logging
import json
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketException

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket connection manager for real-time notifications."""

    # Maximum number of concurrent connections allowed per meeting
    MAX_CONNECTIONS_PER_MEETING = 6

    def __init__(self):
        """Initialize connection manager."""
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, websocket: WebSocket, meeting_id: str, connection_id: str):
        """Accept a WebSocket connection and store it.

        Args:
            websocket: WebSocket connection
            meeting_id: Meeting identifier
            connection_id: Unique identifier for this connection

        Raises:
            WebSocketException: If connection limit is reached for this meeting
        """
        # Check if meeting has reached connection limit
        if meeting_id in self.active_connections:
            if len(self.active_connections[meeting_id]) >= self.MAX_CONNECTIONS_PER_MEETING:
                await websocket.accept()
                await websocket.send_text(
                    json.dumps({
                        "type": "connection_error",
                        "status": "rejected",
                        "message": f"Meeting has reached maximum connection limit of {self.MAX_CONNECTIONS_PER_MEETING}",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                )
                await websocket.close(code=1008, reason="Connection limit reached")
                logger.warning(
                    f"Connection rejected for meeting {meeting_id}: limit of {self.MAX_CONNECTIONS_PER_MEETING} reached"
                )
                raise WebSocketException(code=1008, reason="Connection limit reached")

        await websocket.accept()

        # Initialize meeting dictionary if it doesn't exist
        if meeting_id not in self.active_connections:
            self.active_connections[meeting_id] = {}

        self.active_connections[meeting_id][connection_id] = websocket
        logger.info(
            f"WebSocket connected for meeting {meeting_id}, connection {connection_id} "
            f"({len(self.active_connections[meeting_id])}/{self.MAX_CONNECTIONS_PER_MEETING} connections)"
        )

    def disconnect(self, meeting_id: str, connection_id: str):
        """Remove a WebSocket connection.

        Args:
            meeting_id: Meeting identifier
            connection_id: Unique identifier for the connection to remove
        """
        if meeting_id in self.active_connections:
            if connection_id in self.active_connections[meeting_id]:
                del self.active_connections[meeting_id][connection_id]
                logger.info(
                    f"WebSocket disconnected for meeting {meeting_id}, connection {connection_id} "
                    f"({len(self.active_connections[meeting_id])} remaining)"
                )

                # Clean up meeting key if no more connections
                if not self.active_connections[meeting_id]:
                    del self.active_connections[meeting_id]
                    logger.info(f"All connections closed for meeting {meeting_id}")

    def get_connection_count(self, meeting_id: str) -> int:
        """Get the number of active connections for a meeting.

        Args:
            meeting_id: Meeting identifier

        Returns:
            Number of active connections for the meeting
        """
        return len(self.active_connections.get(meeting_id, {}))

    async def send_notification(
        self,
        meeting_id: str,
        notification_type: str,
        status: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ):
        """Send a notification message to all WebSocket connections for a meeting.

        Broadcasts the notification to all active connections for the specified meeting.
        Automatically removes any failed/stale connections.

        Args:
            meeting_id: Meeting identifier
            notification_type: Type of notification (e.g., "transcription_status")
            status: Status of the notification (e.g., "completed", "failed")
            message: Notification message
            data: Optional additional data to include
        """
        if meeting_id in self.active_connections:
            notification = {
                "type": notification_type,
                "status": status,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            if data:
                notification["data"] = data

            notification_json = json.dumps(notification)
            dead_connections = []

            # Broadcast to all connections for this meeting
            for connection_id, websocket in self.active_connections[meeting_id].items():
                try:
                    await websocket.send_text(notification_json)
                except Exception as e:
                    logger.error(
                        f"Failed to send notification to meeting {meeting_id}, "
                        f"connection {connection_id}: {e}"
                    )
                    dead_connections.append(connection_id)

            # Remove failed connections
            for connection_id in dead_connections:
                self.disconnect(meeting_id, connection_id)

            if dead_connections:
                logger.info(
                    f"Removed {len(dead_connections)} dead connection(s) from meeting {meeting_id}"
                )
            else:
                logger.info(
                    f"Sent notification to {len(self.active_connections.get(meeting_id, {}))} "
                    f"connection(s) for meeting {meeting_id}: {message}"
                )

    async def send_to_connection(
        self,
        meeting_id: str,
        connection_id: str,
        message: str
    ):
        """Send a message to a specific WebSocket connection.

        Args:
            meeting_id: Meeting identifier
            connection_id: Unique identifier for the connection
            message: Message to send
        """
        if meeting_id in self.active_connections:
            if connection_id in self.active_connections[meeting_id]:
                try:
                    await self.active_connections[meeting_id][connection_id].send_text(message)
                    logger.debug(
                        f"Sent message to meeting {meeting_id}, connection {connection_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to send message to meeting {meeting_id}, "
                        f"connection {connection_id}: {e}"
                    )
                    # Remove stale connection
                    self.disconnect(meeting_id, connection_id)
