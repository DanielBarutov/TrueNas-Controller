"""Ports owned by the application layer."""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol, Self
from uuid import UUID

from application.truenas import (
    TrueNASDataset,
    TrueNASExtent,
    TrueNASSnapshot,
    TrueNASTarget,
    TrueNASTargetExtent,
)
from domain.agent import AgentBinding
from domain.agent_command import AgentCommand
from domain.enrollment import EnrollmentToken
from domain.outbox import OutboxEvent
from domain.preflight import PreflightReport, ProcessRule
from domain.provisioning import ProvisioningToken
from domain.publish import PublishJob, PublishTarget
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

    async def restore(self, station: Station) -> None:
        """Restore a previously soft-deleted station with fresh registration data."""

    async def update_hostname(self, station_id: UUID, hostname: str) -> None:
        """Update the station hostname received during enrollment."""

    async def delete(self, station_id: UUID, deleted_at: datetime) -> bool:
        """Soft-delete a station and remove its active agent binding."""


class EnrollmentTokenRepository(Protocol):
    """Atomic one-time token persistence boundary."""

    async def add(self, token: EnrollmentToken) -> None:
        """Stage a new enrollment token."""

    async def consume(self, token_hash: str, now: datetime) -> EnrollmentToken | None:
        """Claim a valid token inside the current transaction."""


class ProvisioningTokenRepository(Protocol):
    """Atomic persistence boundary for station-less bootstrap tokens."""

    async def add(self, token: ProvisioningToken) -> None:
        """Stage a new provisioning token."""

    async def consume(self, token_hash: str, now: datetime) -> ProvisioningToken | None:
        """Claim a valid token inside the current transaction."""


class AgentRepository(Protocol):
    """Agent binding and heartbeat persistence boundary."""

    async def add(self, agent: AgentBinding) -> None:
        """Stage a new agent binding."""

    async def get_by_credential_hash(self, credential_hash: str) -> AgentBinding | None:
        """Load the binding without exposing the raw credential."""

    async def get_by_agent_uuid(self, agent_uuid: UUID) -> AgentBinding | None:
        """Load an agent binding for operator command issuance."""

    async def get_by_station_id(self, station_id: UUID) -> AgentBinding | None:
        """Load an existing agent binding for one stable station identifier."""

    async def record_heartbeat(
        self,
        agent_id: UUID,
        snapshot: ProcessSnapshot,
        received_at: datetime,
        *,
        hostname: str | None = None,
        ip_addresses: tuple[str, ...] | None = None,
        mac_addresses: tuple[str, ...] | None = None,
    ) -> None:
        """Persist snapshot, identity metadata and agent/station freshness state."""


class AgentCommandRepository(Protocol):
    """Durable lease/ack boundary for signed agent commands."""

    async def add(self, command: AgentCommand) -> None:
        """Stage one signed command for a bound agent."""

    async def claim_for_agent(
        self,
        agent_id: UUID,
        *,
        now: datetime,
        lease_for: timedelta,
        limit: int,
    ) -> tuple[AgentCommand, ...]:
        """Lease pending or expired-delivery commands for one heartbeat response."""

    async def acknowledge(
        self,
        agent_id: UUID,
        command_id: UUID,
        *,
        now: datetime,
    ) -> bool:
        """Acknowledge a command only for its owning agent and active lease."""


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


class PreflightReportQuery(Protocol):
    """Application boundary for a fresh station preflight report."""

    async def execute(self, *, station_id: UUID) -> PreflightReport:
        """Evaluate one station without mutating publish/storage state."""


class PublishJobRepository(Protocol):
    """Persistence boundary for durable publish job state."""

    async def get(self, job_id: UUID) -> PublishJob | None:
        """Return one job by its durable identifier."""

    async def get_by_idempotency_key(self, idempotency_key: str) -> PublishJob | None:
        """Return the job previously created with an idempotency key."""

    async def add(self, job: PublishJob) -> None:
        """Stage a new draft job."""

    async def update(self, job: PublishJob) -> None:
        """Stage a state or metadata update for an existing job."""


class PublishTargetRepository(Protocol):
    """Persistence boundary for the materialized station selection."""

    async def list_for_job(self, job_id: UUID) -> tuple[PublishTarget, ...]:
        """Return targets using stable station identifiers."""

    async def add(self, target: PublishTarget) -> None:
        """Stage one selected or deselected target."""

    async def add_many(self, targets: tuple[PublishTarget, ...]) -> None:
        """Stage all target rows in the current job transaction."""

    async def update(self, target: PublishTarget) -> None:
        """Stage a result/preflight update for an existing target."""


class OutboxRepository(Protocol):
    """Persistence boundary for transactionally staged external events."""

    async def add(self, event: OutboxEvent) -> None:
        """Stage one event in the current domain transaction."""

    async def claim_pending(
        self,
        *,
        limit: int,
        worker_id: str,
        now: datetime,
        lease_for: timedelta,
    ) -> tuple[OutboxEvent, ...]:
        """Lease pending events for one relay instance."""

    async def mark_dispatched(self, event_id: UUID, dispatched_at: datetime) -> None:
        """Mark one successfully handed-off event."""

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        error: str,
        retry_at: datetime,
        max_attempts: int,
    ) -> None:
        """Record a failed attempt and schedule retry or terminal failure."""


class PublishStorageAdapter(Protocol):
    """High-level storage port implemented by fake/TrueNAS adapters."""

    async def create_master(self, job_id: UUID, label: str) -> str:
        """Create or return the idempotent master object reference."""

    async def create_clone(self, master_mapping: str, station_id: UUID) -> str:
        """Create or return one writable clone for the station."""

    async def read_mapping(self, station_id: UUID) -> str | None:
        """Read current station mapping."""

    async def switch_mapping(self, station_id: UUID, clone_mapping: str) -> None:
        """Switch mapping for one station."""

    async def verify_mapping(self, station_id: UUID, clone_mapping: str) -> bool:
        """Verify mapping independently after switch."""


class TrueNASJsonRpcTransport(Protocol):
    """Minimal JSON-RPC transport used by the read-only TrueNAS adapter."""

    async def request(self, method: str, params: object | None = None) -> object:
        """Send one request without exposing credentials to the application."""

    async def close(self) -> None:
        """Release the external connection without logging its credentials."""


class TrueNASReadOnlyClient(Protocol):
    """Read-only TrueNAS metadata port for application use cases."""

    async def ping(self) -> None:
        """Verify that the configured TrueNAS API responds."""

    async def query_datasets(self) -> tuple[TrueNASDataset, ...]:
        """Read dataset and zvol metadata."""

    async def query_snapshots(self) -> tuple[TrueNASSnapshot, ...]:
        """Read snapshot metadata."""

    async def query_targets(self) -> tuple[TrueNASTarget, ...]:
        """Read iSCSI target metadata."""

    async def query_extents(self) -> tuple[TrueNASExtent, ...]:
        """Read iSCSI extent metadata."""

    async def query_target_extents(self) -> tuple[TrueNASTargetExtent, ...]:
        """Read target-to-extent attachment metadata."""

    async def close(self) -> None:
        """Release the adapter connection at the end of a smoke/use session."""


class PublishTaskExecutor(Protocol):
    """Next-stage executor invoked after durable worker state is loaded."""

    async def execute(
        self,
        job: PublishJob,
        targets: tuple[PublishTarget, ...],
        *,
        correlation_id: UUID,
    ) -> None:
        """Execute one idempotent publish stage without owning persistence setup."""


class PublishTaskQueue(Protocol):
    """Minimal queue boundary for a durable publish task."""

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        """Enqueue only the identifiers needed to reload state in the worker."""


class UnitOfWork(Protocol):
    """Transaction boundary for one application command or worker message."""

    stations: StationRepository
    enrollment_tokens: EnrollmentTokenRepository
    provisioning_tokens: ProvisioningTokenRepository
    agents: AgentRepository
    agent_commands: AgentCommandRepository
    process_rules: ProcessRuleRepository
    process_snapshots: ProcessSnapshotRepository
    publish_jobs: PublishJobRepository
    publish_targets: PublishTargetRepository
    outbox_events: OutboxRepository

    async def __aenter__(self) -> Self:
        """Open the unit of work and its repositories."""

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the unit of work after commit or rollback."""

    async def commit(self) -> None:
        """Commit all staged changes atomically."""

    async def rollback(self) -> None:
        """Rollback all staged changes."""


UnitOfWorkFactory = Callable[[], UnitOfWork]
