"""Pure process and drive snapshot models received from an agent."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Normalized process information safe for the server read model."""

    name: str
    pid: int | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class DriveInfo:
    """Normalized drive availability information."""

    letter: str
    present: bool
    free_bytes: int | None = None


@dataclass(frozen=True, slots=True)
class ProcessSnapshot:
    """Agent snapshot stored for freshness and preflight decisions."""

    station_id: UUID
    captured_at: datetime
    agent_version: str
    processes: tuple[ProcessInfo, ...] = ()
    drives: tuple[DriveInfo, ...] = ()
