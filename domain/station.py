"""Station entities and station-level invariants."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class StationRole(StrEnum):
    """Role assigned to a registered station."""

    ADMIN = "admin"
    CLIENT = "client"


class StationStatus(StrEnum):
    """Operational status reported by the server-side station registry."""

    ONLINE = "online"
    STALE = "stale"
    OFFLINE = "offline"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class Station:
    """A registered station without persistence or transport concerns."""

    id: UUID
    station_id: UUID
    display_name: str
    hostname: str
    role: StationRole
    status: StationStatus = StationStatus.OFFLINE
    enabled: bool = True
    deleted_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValueError("display_name must not be blank")
        if not self.hostname.strip():
            raise ValueError("hostname must not be blank")
        if self.deleted_at is not None and self.enabled:
            raise ValueError("deleted station must be disabled")
        if not self.enabled and self.status is not StationStatus.DISABLED:
            raise ValueError("disabled station must have disabled status")
        if self.enabled and self.status is StationStatus.DISABLED:
            raise ValueError("disabled status requires a disabled station")

    @property
    def is_available(self) -> bool:
        """Return whether the station may participate in read-only workflows."""

        return self.enabled and self.deleted_at is None and self.status is not StationStatus.OFFLINE
