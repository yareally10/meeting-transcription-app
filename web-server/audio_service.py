import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydub import AudioSegment
import io

logger = logging.getLogger(__name__)

class AudioFileService:
    """Service to handle audio file operations for meetings"""
    
    # Class constants
    CHUNK_DURATION_MILLISECONDS = 5000
    PROCESSED_FOLDER_NAME = "processed"
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        # Track last processed position for each meeting
        self.last_processed_position: Dict[str, float] = {}
        logger.info(f"AudioFileService initialized with base path: {self.base_path}")
    
    def get_meeting_audio_path(self, meeting_id: str) -> Path:
        """Get the path to the raw audio file for a meeting"""
        meeting_dir = self.base_path / meeting_id
        meeting_dir.mkdir(parents=True, exist_ok=True)
        return meeting_dir / "raw.webm"
    
    def get_meeting_directory(self, meeting_id: str) -> Path:
        """Get the directory path for a meeting"""
        meeting_dir = self.base_path / meeting_id
        meeting_dir.mkdir(parents=True, exist_ok=True)
        return meeting_dir
    
    async def append_audio_chunk(self, meeting_id: str, audio_data: bytes) -> Dict[str, Any]:
        """
        Append audio chunk to the meeting's raw audio file
        Returns info about the operation
        """
        try:
            file_path = self.get_meeting_audio_path(meeting_id)
            
            # Check if file exists to determine if this is the first chunk
            is_first_chunk = not file_path.exists()
            
            # Append chunk to file
            with open(file_path, "ab") as f:
                f.write(audio_data)
            
            # Get updated file stats
            file_stats = file_path.stat()
            
            result = {
                "file_path": str(file_path),
                "is_first_chunk": is_first_chunk,
                "chunk_size": len(audio_data),
                "total_file_size": file_stats.st_size,
                "last_modified": file_stats.st_mtime
            }
            
            logger.info(f"{'Created' if is_first_chunk else 'Appended to'} {file_path} (+{len(audio_data)} bytes, total: {file_stats.st_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Error appending audio chunk for meeting {meeting_id}: {e}")
            raise
    
    def get_processed_directory(self, meeting_id: str) -> Path:
        """Get the processed directory path for a meeting"""
        meeting_dir = self.get_meeting_directory(meeting_id)
        processed_dir = meeting_dir / self.PROCESSED_FOLDER_NAME
        processed_dir.mkdir(parents=True, exist_ok=True)
        return processed_dir
    
    async def slice_next_unprocessed_chunk(self, meeting_id: str, duration_milliseconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Slice the next unprocessed chunk from the raw.webm file
        Tracks position to avoid overlap and ensure all audio is processed
        """
        try:
            if duration_milliseconds is None:
                duration_milliseconds = self.CHUNK_DURATION_MILLISECONDS
                
            # Get paths
            raw_file_path = self.get_meeting_audio_path(meeting_id)
            processed_dir = self.get_processed_directory(meeting_id)
            
            # Check if raw file exists
            if not raw_file_path.exists():
                logger.warning(f"Raw audio file does not exist: {raw_file_path}")
                return None
            
            # Load the audio file
            audio = AudioSegment.from_file(str(raw_file_path), format="webm")
            audio_duration_seconds = len(audio) / 1000.0
            
            # Get last processed position for this meeting
            last_position = self.last_processed_position.get(meeting_id, 0.0)
            
            # Check if there's unprocessed audio
            remaining_duration = audio_duration_seconds - last_position
            if remaining_duration < 1.0:  # Less than 1 second remaining
                logger.info(f"No significant unprocessed audio remaining for meeting {meeting_id} (only {remaining_duration:.2f}s)")
                return None
            
            # Determine chunk duration (might be less than requested if near end)
            actual_chunk_duration = min(duration_milliseconds / 1000, remaining_duration)
            
            # Extract the chunk
            start_time_ms = int(last_position * 1000)
            end_time_ms = int((last_position + actual_chunk_duration) * 1000)
            chunk = audio[start_time_ms:end_time_ms]
            
            # Generate timestamp filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            chunk_filename = f"chunk_{timestamp}.webm"
            chunk_file_path = processed_dir / chunk_filename
            
            # Save the chunk
            chunk.export(str(chunk_file_path), format="webm")
            
            # Update last processed position
            new_position = last_position + actual_chunk_duration
            self.last_processed_position[meeting_id] = new_position
            
            # Get file stats
            chunk_stats = chunk_file_path.stat()
            
            result = {
                "chunk_file_path": str(chunk_file_path),
                "chunk_filename": chunk_filename,
                "requested_duration_seconds": duration_milliseconds / 1000,
                "actual_duration_seconds": actual_chunk_duration,
                "chunk_size_bytes": chunk_stats.st_size,
                "original_audio_duration_seconds": audio_duration_seconds,
                "processed_from_seconds": last_position,
                "processed_to_seconds": new_position,
                "remaining_audio_seconds": audio_duration_seconds - new_position,
                "timestamp": timestamp
            }
            
            logger.info(f"Processed chunk {chunk_filename}: {last_position:.2f}s to {new_position:.2f}s ({actual_chunk_duration:.2f}s) - {remaining_duration - actual_chunk_duration:.2f}s remaining")
            return result
            
        except Exception as e:
            logger.error(f"Error processing next chunk for meeting {meeting_id}: {e}")
            return None
    
    def reset_processing_position(self, meeting_id: str):
        """Reset the processing position for a meeting (useful when starting new recording)"""
        if meeting_id in self.last_processed_position:
            del self.last_processed_position[meeting_id]
            logger.info(f"Reset processing position for meeting {meeting_id}")
