"""Pydantic schemas for TrainingSession."""
from datetime import datetime

from pydantic import BaseModel, Field


class TrainingSessionBase(BaseModel):
    client_id: str | None = Field(default=None, max_length=36)
    scenario_id: int | None = None
    language: str = Field(default="en", pattern="^(en|es)$")


class TrainingSessionCreate(TrainingSessionBase):
    pass


class TrainingSessionResponse(TrainingSessionBase):
    id: int
    status: str
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}
