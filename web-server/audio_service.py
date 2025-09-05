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
    CHUNK_DURATION_SECONDS = 5.0
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
    
    def get_audio_file_info(self, meeting_id: str) -> Dict[str, Any]:
        """Get information about the meeting's audio file"""
        try:
            file_path = self.get_meeting_audio_path(meeting_id)
            
            if not file_path.exists():
                return {
                    "exists": False,
                    "file_path": str(file_path),
                    "size": 0
                }
            
            file_stats = file_path.stat()
            return {
                "exists": True,
                "file_path": str(file_path),
                "size": file_stats.st_size,
                "last_modified": file_stats.st_mtime,
                "created": file_stats.st_ctime
            }
            
        except Exception as e:
            logger.error(f"Error getting audio file info for meeting {meeting_id}: {e}")
            raise
    
    def delete_audio_file(self, meeting_id: str) -> bool:
        """Delete the audio file for a meeting"""
        try:
            file_path = self.get_meeting_audio_path(meeting_id)
            
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted audio file: {file_path}")
                return True
            else:
                logger.info(f"Audio file does not exist: {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting audio file for meeting {meeting_id}: {e}")
            raise
    
    def list_meeting_files(self, meeting_id: str) -> Dict[str, Any]:
        """List all files in the meeting directory"""
        try:
            meeting_dir = self.get_meeting_directory(meeting_id)
            
            files = []
            if meeting_dir.exists():
                for file_path in meeting_dir.iterdir():
                    if file_path.is_file():
                        stats = file_path.stat()
                        files.append({
                            "name": file_path.name,
                            "path": str(file_path),
                            "size": stats.st_size,
                            "last_modified": stats.st_mtime,
                            "created": stats.st_ctime
                        })
            
            return {
                "meeting_id": meeting_id,
                "directory": str(meeting_dir),
                "files": files,
                "file_count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Error listing files for meeting {meeting_id}: {e}")
            raise
    
    def get_processed_directory(self, meeting_id: str) -> Path:
        """Get the processed directory path for a meeting"""
        meeting_dir = self.get_meeting_directory(meeting_id)
        processed_dir = meeting_dir / self.PROCESSED_FOLDER_NAME
        processed_dir.mkdir(parents=True, exist_ok=True)
        return processed_dir
    
    async def slice_last_seconds(self, meeting_id: str, duration_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Slice the last N seconds from the raw.webm file and save to processed folder
        Returns info about the sliced chunk if successful, None if failed
        """
        try:
            if duration_seconds is None:
                duration_seconds = self.CHUNK_DURATION_SECONDS
                
            # Get paths
            raw_file_path = self.get_meeting_audio_path(meeting_id)
            processed_dir = self.get_processed_directory(meeting_id)
            
            # Check if raw file exists
            if not raw_file_path.exists():
                logger.warning(f"Raw audio file does not exist: {raw_file_path}")
                return None
            
            # Generate timestamp filename
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
            chunk_filename = f"chunk_{timestamp}.webm"
            chunk_file_path = processed_dir / chunk_filename
            
            logger.info(f"Slicing last {duration_seconds}s from {raw_file_path}")
            
            # Load the audio file
            audio = AudioSegment.from_file(str(raw_file_path), format="webm")
            
            # Check if audio is long enough
            audio_duration_ms = len(audio)
            audio_duration_seconds = audio_duration_ms / 1000.0
            
            if audio_duration_seconds < duration_seconds:
                logger.warning(f"Audio file is only {audio_duration_seconds:.2f}s long, shorter than requested {duration_seconds}s")
                # Take the entire audio if it's shorter than requested duration
                chunk = audio
                actual_duration = audio_duration_seconds
            else:
                # Extract the last N seconds
                start_time_ms = audio_duration_ms - (duration_seconds * 1000)
                chunk = audio[start_time_ms:]
                actual_duration = duration_seconds
            
            # Save the chunk as WebM
            chunk.export(str(chunk_file_path), format="webm")
            
            # Get file stats
            chunk_stats = chunk_file_path.stat()
            
            result = {
                "chunk_file_path": str(chunk_file_path),
                "chunk_filename": chunk_filename,
                "requested_duration_seconds": duration_seconds,
                "actual_duration_seconds": actual_duration,
                "chunk_size_bytes": chunk_stats.st_size,
                "original_audio_duration_seconds": audio_duration_seconds,
                "timestamp": timestamp
            }
            
            logger.info(f"Successfully sliced {actual_duration:.2f}s chunk to {chunk_file_path} ({chunk_stats.st_size} bytes)")
            return result
            
        except Exception as e:
            logger.error(f"Error slicing audio for meeting {meeting_id}: {e}")
            return None
    
    async def slice_next_unprocessed_chunk(self, meeting_id: str, duration_seconds: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Slice the next unprocessed chunk from the raw.webm file
        Tracks position to avoid overlap and ensure all audio is processed
        """
        try:
            if duration_seconds is None:
                duration_seconds = self.CHUNK_DURATION_SECONDS
                
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
            actual_chunk_duration = min(duration_seconds, remaining_duration)
            
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
                "requested_duration_seconds": duration_seconds,
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
    
    async def process_remaining_audio(self, meeting_id: str) -> List[Dict[str, Any]]:
        """
        Process all remaining unprocessed audio when recording stops
        Returns list of processed chunks
        """
        chunks = []
        logger.info(f"Processing remaining audio for meeting {meeting_id}")
        
        while True:
            chunk_result = await self.slice_next_unprocessed_chunk(meeting_id)
            if chunk_result is None:
                break
            chunks.append(chunk_result)
            
            # Safety check to avoid infinite loop
            if len(chunks) > 100:  # Max 100 chunks = 500 seconds = 8+ minutes
                logger.warning(f"Processed {len(chunks)} chunks, stopping to avoid infinite loop")
                break
        
        logger.info(f"Finished processing remaining audio: {len(chunks)} chunks created")
        return chunks