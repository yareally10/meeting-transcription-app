import logging
import json
from typing import Dict
from datetime import datetime, timezone
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket connection manager for real-time notifications"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, meeting_id: str):
        """Accept a WebSocket connection and store it"""
        await websocket.accept()
        self.active_connections[meeting_id] = websocket
        logger.info(f"WebSocket connected for meeting {meeting_id}")
    
    def disconnect(self, meeting_id: str):
        """Remove a WebSocket connection"""
        if meeting_id in self.active_connections:
            del self.active_connections[meeting_id]
            logger.info(f"WebSocket disconnected for meeting {meeting_id}")
    
    async def send_notification(self, meeting_id: str, notification_type: str, status: str, message: str, data=None):
        """Send a notification message to a specific meeting's WebSocket connection"""
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
                
                await self.active_connections[meeting_id].send_text(json.dumps(notification))
                logger.info(f"Sent notification to meeting {meeting_id}: {message}")
            except Exception as e:
                logger.error(f"Failed to send notification to meeting {meeting_id}: {e}")
                # Remove stale connection
                self.disconnect(meeting_id)
    
    def get_connection_count(self) -> int:
        """Get the total number of active connections"""
        return len(self.active_connections)
    
    def is_connected(self, meeting_id: str) -> bool:
        """Check if a meeting has an active WebSocket connection"""
        return meeting_id in self.active_connections
    
    async def broadcast_to_all(self, notification_type: str, status: str, message: str, data=None):
        """Broadcast a message to all active connections"""
        if not self.active_connections:
            return
        
        notification = {
            "type": notification_type,
            "status": status,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if data:
            notification["data"] = data
        
        message_json = json.dumps(notification)
        
        # Send to all connections and track failed ones
        failed_connections = []
        for meeting_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to broadcast to meeting {meeting_id}: {e}")
                failed_connections.append(meeting_id)
        
        # Clean up failed connections
        for meeting_id in failed_connections:
            self.disconnect(meeting_id)
        
        logger.info(f"Broadcast message to {len(self.active_connections)} connections, {len(failed_connections)} failed")