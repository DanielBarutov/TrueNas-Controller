"""Pydantic request/response schemas for agent lifecycle endpoints."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from domain.station import StationRole
from presentation.schemas import StationResponse


class StationCreateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=255)
    role: StationRole = StationRole.CLIENT


class StationRegistrationResponse(StationResponse):
    enrollment_token: str
    enrollment_expires_at: datetime


class AgentEnrollRequest(BaseModel):
    enrollment_token: str = Field(min_length=1, max_length=256)
    agent_uuid: UUID
    hostname: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(min_length=1, max_length=64)
    ip_addresses: list[str] = Field(default_factory=list, max_length=16)
    mac_addresses: list[str] = Field(default_factory=list, max_length=16)


class AgentEnrollResponse(BaseModel):
    station_id: UUID
    credential: str
    server_time: datetime


class ProcessPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    pid: int | None = Field(default=None, ge=0)
    path: str | None = Field(default=None, max_length=1024)


class DrivePayload(BaseModel):
    letter: str = Field(min_length=1, max_length=3)
    present: bool
    free_bytes: int | None = Field(default=None, ge=0)


class HeartbeatRequest(BaseModel):
    station_id: UUID
    captured_at: datetime
    agent_version: str = Field(min_length=1, max_length=64)
    processes: list[ProcessPayload] = Field(default_factory=list, max_length=512)
    drives: list[DrivePayload] = Field(default_factory=list, max_length=32)
    game_version_marker: str | None = Field(default=None, max_length=255)


class HeartbeatResponse(BaseModel):
    status: str
    station_id: UUID
    received_at: datetime
