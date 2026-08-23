"""Ports owned by the application layer."""

from collections.abc import Callable
from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from domain.agent import AgentBinding
from domain.enrollment import EnrollmentToken
from domain.preflight import ProcessRule
from domain.snapshot import ProcessSnapshot
from domain.station import Station, StationRole


class StationListQuery(Protocol):
    """Read-only application boundary used by the presentation layer."""

    async def execute(self, *, include_disabled: bool = False) -> list[Station]:
        """Return stations for the current dashboard read model."""


class StationRepository(Protocol):
    """Persistence operations required by station use cases."""

    async def get(self, station_id: UUID) -> Station | None:
        """Return a station by its stable station identifier."""

    async def list(self, *, include_disabled: bool = False) -> list[Station]:
        """Return registered stations for a read model."""

    async def add(self, station: Station) -> None:
        """Stage a new station for persistence in the current unit of work."""

    async def update_hostname(self, station_id: UUID, hostname: str) -> None:
        """Update the station hostname received during enrollment."""


class EnrollmentTokenRepository(Protocol):
    """Atomic one-time token persistence boundary."""

    async def add(self, token: EnrollmentToken) -> None:
        """Stage a new enrollment token."""

    async def consume(self, token_hash: str, now: datetime) -> EnrollmentToken | None:
        """Claim a valid token inside the current transaction."""


class AgentRepository(Protocol):
    """Agent binding and heartbeat persistence boundary."""

    async def add(self, agent: AgentBinding) -> None:
        """Stage a new agent binding."""

    async def get_by_credential_hash(self, credential_hash: str) -> AgentBinding | None:
        """Load the binding without exposing the raw credential."""

    async def record_heartbeat(
        self,
        agent_id: UUID,
        snapshot: ProcessSnapshot,
        received_at: datetime,
    ) -> None:
        """Persist snapshot and update the agent/station freshness state."""


class ProcessRuleRepository(Protocol):
    """Persistence boundary for editable process rules."""

    async def list_for_role(self, role: StationRole) -> tuple[ProcessRule, ...]:
        """Return enabled global and role-specific rules."""

    async def add(self, rule: ProcessRule) -> None:
        """Stage a process rule."""


class ProcessSnapshotRepository(Protocol):
    """Read-only latest snapshot boundary for preflight."""

    async def latest(self, station_id: UUID) -> ProcessSnapshot | None:
        """Return the newest stored snapshot for a stable station ID."""


class UnitOfWork(Protocol):
    """Transaction boundary for one application command or worker message."""

    stations: StationRepository
    enrollment_tokens: EnrollmentTokenRepository
    agents: AgentRepository
    process_rules: ProcessRuleRepository
    process_snapshots: ProcessSnapshotRepository

    async def __aenter__(self) -> Self:
        """Open the unit of work and its repositories."""

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the unit of work after commit or rollback."""

    async def commit(self) -> None:
        """Commit all staged changes atomically."""

    async def rollback(self) -> None:
        """Rollback all staged changes."""


UnitOfWorkFactory = Callable[[], UnitOfWork]
