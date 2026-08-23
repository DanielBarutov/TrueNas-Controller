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
    MetaData,
    String,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from domain.preflight import RuleSeverity
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
    game_version_marker: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
