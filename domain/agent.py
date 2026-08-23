"""Pure agent enrollment and heartbeat binding model."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class AgentBinding:
    """Agent identity bound to a stable station identifier."""

    id: UUID
    station_id: UUID
    agent_uuid: UUID
    agent_version: str
    credential_hash: str
    credential_created_at: datetime
    revoked_at: datetime | None = None
    station_enabled: bool = True
    station_deleted_at: datetime | None = None
    last_ip_addresses: tuple[str, ...] = ()
    last_mac_addresses: tuple[str, ...] = ()

    def can_accept_heartbeat(self) -> bool:
        """Return whether this binding is allowed to submit a heartbeat."""

        return self.revoked_at is None and self.station_enabled and self.station_deleted_at is None
