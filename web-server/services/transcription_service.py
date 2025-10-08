import logging
import httpx
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class TranscriptionService:
    """Service to handle interactions with the transcription service container"""
    
    def __init__(self, transcription_service_url: str, web_server_url: str):
        self.transcription_service_url = transcription_service_url
        self.web_server_url = web_server_url
        self.webhook_url = f"{web_server_url}/webhook/transcription-completed"
        logger.info(f"TranscriptionService initialized with URL: {transcription_service_url}")
    
    async def submit_transcription_job(self, meeting_id: str, filename: str) -> Optional[str]:
        """
        Submit a transcription job to the transcription service
        Returns job_id if successful, None if failed
        """
        try:
            request_data = {
                "meeting_id": meeting_id,
                "filename": filename,
                "webhook_url": self.webhook_url
            }
            
            logger.info(f"Submitting transcription job for meeting {meeting_id}, file {filename}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.transcription_service_url}/transcribe",
                    json=request_data,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get("job_id")
                    logger.info(f"Successfully queued transcription job {job_id} for meeting {meeting_id}, file {filename}")
                    return job_id
                else:
                    logger.error(f"Transcription service error: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout submitting transcription job for meeting {meeting_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error submitting transcription job for meeting {meeting_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error submitting transcription job for meeting {meeting_id}: {e}")
            return None
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a transcription job
        Returns job status info if successful, None if failed
        """
        try:
            logger.info(f"Checking status of transcription job {job_id}")
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.transcription_service_url}/jobs/{job_id}",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Job {job_id} status: {result.get('status', 'unknown')}")
                    return result
                elif response.status_code == 404:
                    logger.warning(f"Transcription job {job_id} not found")
                    return None
                else:
                    logger.error(f"Error getting job status: {response.status_code} - {response.text}")
                    return None
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout checking status of job {job_id}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Request error checking job {job_id} status: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error checking job {job_id} status: {e}")
            return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a transcription job
        Returns True if successful, False if failed
        """
        try:
            logger.info(f"Cancelling transcription job {job_id}")
            
            async with httpx.AsyncClient() as client:
                response = await client.delete(
                    f"{self.transcription_service_url}/jobs/{job_id}",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully cancelled transcription job {job_id}")
                    return True
                elif response.status_code == 404:
                    logger.warning(f"Transcription job {job_id} not found for cancellation")
                    return False
                else:
                    logger.error(f"Error cancelling job: {response.status_code} - {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"Timeout cancelling job {job_id}")
            return False
        except httpx.RequestError as e:
            logger.error(f"Request error cancelling job {job_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error cancelling job {job_id}: {e}")
            return False
    
    async def get_service_health(self) -> Dict[str, Any]:
        """
        Check the health status of the transcription service
        Returns health info
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.transcription_service_url}/health",
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Transcription service health: {result.get('status', 'unknown')}")
                    return {
                        "healthy": True,
                        "status": result.get("status", "unknown"),
                        "details": result
                    }
                else:
                    logger.warning(f"Transcription service health check failed: {response.status_code}")
                    return {
                        "healthy": False,
                        "status": "unhealthy",
                        "error": f"HTTP {response.status_code}"
                    }
                    
        except httpx.TimeoutException:
            logger.error("Timeout checking transcription service health")
            return {
                "healthy": False,
                "status": "timeout",
                "error": "Service timeout"
            }
        except httpx.RequestError as e:
            logger.error(f"Request error checking transcription service health: {e}")
            return {
                "healthy": False,
                "status": "connection_error",
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error checking transcription service health: {e}")
            return {
                "healthy": False,
                "status": "error",
                "error": str(e)
            }
    
    def get_webhook_url(self) -> str:
        """Get the webhook URL for transcription callbacks"""
        return self.webhook_url