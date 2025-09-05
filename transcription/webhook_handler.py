"""Webhook handling for transcription service."""

import asyncio
import httpx
import logging
from typing import Dict, Any

from config import config

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles webhook notifications."""
    
    @staticmethod
    async def send_webhook(webhook_url: str, result_data: Dict[str, Any]) -> bool:
        """
        Send transcription result to web server via webhook.
        
        Returns:
            bool: True if webhook was sent successfully, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url, 
                    json=result_data, 
                    timeout=config.webhook_timeout
                )
                if response.status_code == 200:
                    logger.info(f"Webhook sent successfully to {webhook_url}")
                    return True
                else:
                    logger.error(f"Webhook failed: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            logger.error(f"Error sending webhook to {webhook_url}: {e}")
            return False
    
    @staticmethod
    def send_webhook_sync(webhook_url: str, result_data: Dict[str, Any]) -> bool:
        """Synchronous wrapper for send_webhook."""
        return asyncio.run(WebhookHandler.send_webhook(webhook_url, result_data))