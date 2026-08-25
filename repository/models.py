"""SQLAlchemy persistence models for the initial read-only backend slice."""

from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    Uuid,
    false,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.agent_command import AgentCommandStatus
from domain.outbox import OutboxEventStatus
from domain.preflight import RuleSeverity
from domain.publish import PublishJobStatus, StorageArtifactStatus
from domain.station import StationRole, StationStatus

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base metadata for Alembic and isolated repository tests."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for ORM defaults."""

    return datetime.now(UTC)


def enum_column(enum_type: type[Enum]) -> SqlEnum:
    """Store enum values instead of Python member names."""

    return SqlEnum(
        enum_type,
        name=enum_type.__name__.lower(),
        native_enum=False,
        values_callable=lambda values: [member.value for member in values],
    )


class StationRecord(Base):
    """Database representation of a registered station."""

    __tablename__ = "stations"
    __table_args__ = (
        Index("ix_stations_enabled_state", "enabled", "state"),
        CheckConstraint(
            "(enabled AND state <> 'disabled') OR (NOT enabled AND state = 'disabled')",
            name="enabled_state_consistent",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, default=uuid4
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[StationRole] = mapped_column(enum_column(StationRole), nullable=False)
    state: Mapped[StationStatus] = mapped_column(
        "state", enum_column(StationStatus), nullable=False, default=StationStatus.OFFLINE
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tags: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    current_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    desired_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    state_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    target_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_iqn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    initiator_iqn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    agent: Mapped["AgentRecord | None"] = relationship(
        back_populates="station", uselist=False, cascade="all, delete-orphan"
    )
    enrollment_tokens: Mapped[list["EnrollmentTokenRecord"]] = relationship(
        back_populates="station"
    )
    process_snapshots: Mapped[list["ProcessSnapshotRecord"]] = relationship(
        back_populates="station"
    )
    publish_targets: Mapped[list["PublishTargetRecord"]] = relationship(back_populates="station")


class AgentRecord(Base):
    """Database representation of the one-to-one station agent enrollment."""

    __tablename__ = "agents"
    __table_args__ = (Index("ix_agents_last_seen_at", "last_seen_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    agent_uuid: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), unique=True, nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credential_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_process_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_drive_snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_ip_addresses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_mac_addresses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)

    station: Mapped[StationRecord] = relationship(back_populates="agent")
    commands: Mapped[list["AgentCommandRecord"]] = relationship(back_populates="agent")


class AgentCommandRecord(Base):
    """Durable signed command waiting for delivery or acknowledgement."""

    __tablename__ = "agent_commands"
    __table_args__ = (
        Index("ix_agent_commands_agent_status", "agent_id", "status", "created_at"),
        Index("ix_agent_commands_lease_until", "lease_until"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    agent_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signature: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AgentCommandStatus.PENDING.value
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    agent: Mapped[AgentRecord] = relationship(back_populates="commands")


class EnrollmentTokenRecord(Base):
    """One-time enrollment token digest and lifecycle timestamps."""

    __tablename__ = "enrollment_tokens"
    __table_args__ = (Index("ix_enrollment_tokens_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    station: Mapped[StationRecord] = relationship(back_populates="enrollment_tokens")


class ProvisioningTokenRecord(Base):
    """Short-lived operator token used to create and enroll a new station."""

    __tablename__ = "provisioning_tokens"
    __table_args__ = (Index("ix_provisioning_tokens_expires_at", "expires_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProcessSnapshotRecord(Base):
    """Normalized process/drive snapshot received from a station agent."""

    __tablename__ = "process_snapshots"
    __table_args__ = (Index("ix_process_snapshots_station_captured", "station_id", "captured_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processes: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    drives: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False, default=list)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    freshness_status: Mapped[str] = mapped_column(String(32), nullable=False, default="fresh")

    station: Mapped[StationRecord] = relationship(back_populates="process_snapshots")


class ProcessRuleRecord(Base):
    """Editable process preflight rule."""

    __tablename__ = "process_rules"
    __table_args__ = (Index("ix_process_rules_enabled_role", "enabled", "role"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[StationRole | None] = mapped_column(enum_column(StationRole), nullable=True)
    required_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    severity: Mapped[RuleSeverity] = mapped_column(
        enum_column(RuleSeverity), nullable=False, default=RuleSeverity.BLOCKING
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    persistent_policy: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class PublishJobRecord(Base):
    """Durable publish command and its state-machine position."""

    __tablename__ = "publish_jobs"
    __table_args__ = (Index("ix_publish_jobs_status_created", "status", "created_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    dry_run: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    allow_hot_switch: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    step: Mapped[str] = mapped_column(String(64), nullable=False, default="draft")
    status: Mapped[PublishJobStatus] = mapped_column(
        enum_column(PublishJobStatus), nullable=False, default=PublishJobStatus.DRAFT
    )
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    operator_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    master_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    client_confirmation: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    client_confirmation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    targets: Mapped[list["PublishTargetRecord"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class PublishTargetRecord(Base):
    """Durable selection and per-station result for one publish job."""

    __tablename__ = "publish_targets"
    __table_args__ = (
        UniqueConstraint("job_id", "station_id", name="uq_publish_targets_job_station"),
        Index("ix_publish_targets_job_switch", "job_id", "switch_status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publish_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deselected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preflight_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preflight_result: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    old_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    new_version_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    old_mapping: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    new_mapping: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    switch_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verify_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    progress_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    job: Mapped[PublishJobRecord] = relationship(back_populates="targets")
    station: Mapped[StationRecord] = relationship(back_populates="publish_targets")


class PublishArtifactRecord(Base):
    """Dataset/clone created by a publish job and retained for cleanup."""

    __tablename__ = "publish_artifacts"
    __table_args__ = (
        UniqueConstraint("job_id", "station_id", name="uq_publish_artifacts_job_station"),
        Index("ix_publish_artifacts_cleanup", "is_current", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publish_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    station_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stations.station_id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_dataset: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(255), nullable=False)
    snapshot_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    mapping_ref: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[StorageArtifactStatus] = mapped_column(
        enum_column(StorageArtifactStatus),
        nullable=False,
        default=StorageArtifactStatus.RETIRED,
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class OutboxEventRecord(Base):
    """Transactional event waiting for a separate delivery attempt."""

    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_events_pending", "status", "available_at"),)

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    aggregate_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publish_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    correlation_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[OutboxEventStatus] = mapped_column(
        enum_column(OutboxEventStatus), nullable=False, default=OutboxEventStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
