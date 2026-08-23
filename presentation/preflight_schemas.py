"""Pydantic schemas for the operator preflight query."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PreflightRequest(BaseModel):
    station_id: UUID
    max_snapshot_age_seconds: int = Field(default=30, ge=1, le=3600)
    required_drive_letter: str = Field(default="D:", min_length=1, max_length=3)
    min_free_bytes: int = Field(default=0, ge=0)


class CheckResponse(BaseModel):
    status: str
    code: str
    message: str
    observed_at: datetime
    source_snapshot_id: UUID | None = None


class PreflightResponse(BaseModel):
    station_id: UUID
    status: str
    can_publish: bool
    evaluated_at: datetime
    checks: list[CheckResponse]
