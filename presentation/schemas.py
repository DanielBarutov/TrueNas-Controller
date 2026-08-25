"""Pydantic response schemas for the read-only API."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict

from domain.station import Station, StationRole, StationStatus


class StationResponse(BaseModel):
    """Public station representation without persistence-only fields."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    station_id: UUID
    display_name: str
    hostname: str
    role: StationRole
    status: StationStatus
    enabled: bool
    deleted_at: str | None
    target_name: str | None
    target_iqn: str | None
    initiator_iqn: str | None

    @classmethod
    def from_domain(cls, station: Station) -> "StationResponse":
        return cls(
            id=station.id,
            station_id=station.station_id,
            display_name=station.display_name,
            hostname=station.hostname,
            role=station.role,
            status=station.status,
            enabled=station.enabled,
            deleted_at=None if station.deleted_at is None else station.deleted_at.isoformat(),
            target_name=station.target_name,
            target_iqn=station.target_iqn,
            initiator_iqn=station.initiator_iqn,
        )
