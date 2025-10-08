"""Pydantic models for the API."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from bson import ObjectId
from config import config


class PyObjectId(str):
    """Custom Pydantic type for MongoDB ObjectId."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, _=None):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid objectid")
            return v
        raise ValueError("Invalid objectid")

    @classmethod
    def __get_pydantic_json_schema__(
        cls, _source_type, _handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        return {"type": "string", "description": "MongoDB ObjectId"}


class MeetingBase(BaseModel):
    """Base meeting model."""
    title: str
    description: str = ""
    keywords: List[str] = []


class MeetingCreate(MeetingBase):
    """Meeting creation model."""
    pass


class MeetingUpdate(BaseModel):
    """Meeting update model."""
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None


class Meeting(MeetingBase):
    """Full meeting model."""
    id: PyObjectId = None
    createdAt: datetime = Field(alias="created_at")
    updatedAt: datetime = Field(alias="updated_at")
    status: str = "created"
    fullTranscription: Optional[str] = Field(None, alias="full_transcription")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda v: v.isoformat()
        }


class KeywordsUpdate(BaseModel):
    """Keywords update model."""
    keywords: List[str]


class TranscriptionWebhookResult(BaseModel):
    """Webhook result from transcription service."""
    job_id: str
    meeting_id: str
    filename: str
    transcription_text: Optional[str] = None
    confidence: Optional[float] = None
    processing_time: float
    status: str  # "completed" or "failed"
    error_message: Optional[str] = None
    processed_at: str