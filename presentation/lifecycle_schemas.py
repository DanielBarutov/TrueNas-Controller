"""Pydantic request/response schemas for agent lifecycle endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from domain.station import StationRole
from presentation.schemas import StationResponse


class StationCreateRequest(BaseModel):
    station_id: UUID | None = None
    display_name: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=255)
    role: StationRole = StationRole.CLIENT
    target_name: str | None = Field(default=None, min_length=1, max_length=255)
    target_iqn: str | None = Field(default=None, min_length=1, max_length=255)
    initiator_iqn: str | None = Field(default=None, min_length=1, max_length=255)


class StationStorageMappingRequest(BaseModel):
    target_name: str | None = Field(default=None, min_length=1, max_length=255)
    target_iqn: str | None = Field(default=None, min_length=1, max_length=255)
    initiator_iqn: str | None = Field(default=None, min_length=1, max_length=255)


class StationUpdateRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=255)
    role: StationRole
    enabled: bool = True


class StationRegistrationResponse(StationResponse):
    enrollment_token: str
    enrollment_expires_at: datetime


class ProvisioningTokenResponse(BaseModel):
    provisioning_token: str
    expires_at: datetime


class AgentEnrollRequest(BaseModel):
    enrollment_token: str = Field(min_length=1, max_length=256)
    agent_uuid: UUID
    hostname: str = Field(min_length=1, max_length=255)
    agent_version: str = Field(min_length=1, max_length=64)
    ip_addresses: list[str] = Field(default_factory=list, max_length=16)
    mac_addresses: list[str] = Field(default_factory=list, max_length=16)


class AgentBootstrapRequest(BaseModel):
    provisioning_token: str = Field(min_length=1, max_length=256)
    station_id: UUID
    display_name: str = Field(min_length=1, max_length=120)
    hostname: str = Field(min_length=1, max_length=255)
    role: StationRole = StationRole.CLIENT
    agent_uuid: UUID
    agent_version: str = Field(min_length=1, max_length=64)
    ip_addresses: list[str] = Field(default_factory=list, max_length=16)
    mac_addresses: list[str] = Field(default_factory=list, max_length=16)


class AgentEnrollResponse(BaseModel):
    station_id: UUID
    credential: str
    server_time: datetime


class AgentCommandIssueRequest(BaseModel):
    name: Literal["refresh_process_snapshot"]
    ttl_seconds: int = Field(default=300, ge=1, le=900)


class AgentCommandIssueResponse(BaseModel):
    command_id: UUID
    name: str
    expires_at: datetime
    status: str


class ProcessPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    pid: int | None = Field(default=None, ge=0)
    path: str | None = Field(default=None, max_length=1024)


class DrivePayload(BaseModel):
    letter: str = Field(min_length=1, max_length=3)
    present: bool
    free_bytes: int | None = Field(default=None, ge=0)


class HeartbeatRequest(BaseModel):
    protocol_version: Literal["1"] = "1"
    station_id: UUID
    captured_at: datetime
    hostname: str | None = Field(default=None, min_length=1, max_length=255)
    ip_addresses: list[str] | None = Field(default=None, max_length=16)
    mac_addresses: list[str] | None = Field(default=None, max_length=16)
    agent_version: str = Field(min_length=1, max_length=64)
    processes: list[ProcessPayload] = Field(default_factory=list, max_length=512)
    drives: list[DrivePayload] = Field(default_factory=list, max_length=32)


class AgentCommandResponse(BaseModel):
    command_id: UUID
    name: str = Field(min_length=1, max_length=64)
    expires_at: datetime
    signature: str = Field(min_length=1, max_length=128)


class HeartbeatResponse(BaseModel):
    status: str
    station_id: UUID
    received_at: datetime
    commands: list[AgentCommandResponse] = Field(default_factory=list, max_length=16)
