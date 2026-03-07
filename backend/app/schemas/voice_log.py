"""Pydantic schemas for VoiceLog."""
from datetime import datetime

from pydantic import BaseModel, Field


class VoiceLogBase(BaseModel):
    session_id: int
    role: str = Field(..., pattern="^(pilot|atc)$")
    transcript: str = Field(..., min_length=1)
    audio_duration_ms: int | None = None


class VoiceLogCreate(VoiceLogBase):
    pass


class VoiceLogResponse(VoiceLogBase):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
