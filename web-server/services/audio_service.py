"""Service to handle audio file storage for meetings."""

import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AudioFileService:
    """Service to handle audio file storage operations for meetings."""

    def __init__(self, base_path: str):
        """Initialize AudioFileService with base storage path.

        Args:
            base_path: Base directory path for audio storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.session_counters = {}  # Track chunk counters per session
        logger.info(f"AudioFileService initialized with base path: {self.base_path}")

    async def save_audio_chunk(
        self,
        meeting_id: str,
        session_id: str,
        audio_data: bytes
    ) -> Dict[str, Any]:
        """Save an audio chunk for a meeting session.

        Automatically generates filename with session ID, counter, and timestamp.
        Creates directory structure: {base_path}/{meeting_id}/audio/

        Args:
            meeting_id: The meeting identifier
            session_id: The WebSocket session identifier
            audio_data: Raw audio chunk data

        Returns:
            Dictionary with file save information including:
                - filename: Generated filename
                - file_path: Full path to saved file
                - file_size: Size in bytes
                - chunk_number: Chunk counter for this session
                - meeting_id: Meeting identifier
                - session_id: Session identifier
                - saved_at: ISO timestamp

        Raises:
            Exception: If file save operation fails
        """
        try:
            # Get and increment chunk counter for this session
            if session_id not in self.session_counters:
                self.session_counters[session_id] = 0
            chunk_number = self.session_counters[session_id]
            self.session_counters[session_id] += 1

            # Generate filename with session ID, counter, and timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            filename = f"audio_chunk_{session_id}_{chunk_number}_{timestamp}.webm"

            # Create meeting audio directory
            audio_dir = self.base_path / meeting_id / "audio"
            audio_dir.mkdir(parents=True, exist_ok=True)

            file_path = audio_dir / filename

            # Save the file
            with open(file_path, "wb") as f:
                f.write(audio_data)

            # Get file stats
            file_stats = file_path.stat()

            result = {
                "filename": filename,
                "file_path": str(file_path),
                "file_size": file_stats.st_size,
                "chunk_number": chunk_number,
                "meeting_id": meeting_id,
                "session_id": session_id,
                "saved_at": datetime.now(timezone.utc).isoformat()
            }

            logger.info(
                f"Saved audio chunk {chunk_number} (session {session_id}) "
                f"for meeting {meeting_id}: {filename} ({file_stats.st_size} bytes)"
            )
            return result

        except Exception as e:
            logger.error(
                f"Error saving audio chunk for meeting {meeting_id}, "
                f"session {session_id}: {e}"
            )
            raise

    def cleanup_session(self, session_id: str) -> None:
        """Clean up session counter when WebSocket disconnects.

        Args:
            session_id: The WebSocket session identifier
        """
        if session_id in self.session_counters:
            del self.session_counters[session_id]
            logger.debug(f"Cleaned up session counter for session {session_id}")
