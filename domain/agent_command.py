"""Pure command envelope and canonical signing payload for station agents."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import json
from uuid import UUID

COMMAND_PROTOCOL_VERSION = "1"


class AgentCommandName(StrEnum):
    """Commands that the Windows agent may execute locally."""

    REFRESH_PROCESS_SNAPSHOT = "refresh_process_snapshot"


class AgentCommandStatus(StrEnum):
    """Durable delivery state for one signed agent command."""

    PENDING = "pending"
    LEASED = "leased"
    ACKNOWLEDGED = "acknowledged"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class AgentCommand:
    """Server-issued command with no arbitrary shell/process arguments."""

    id: UUID
    agent_id: UUID
    name: AgentCommandName
    expires_at: datetime
    signature: str
    status: AgentCommandStatus = AgentCommandStatus.PENDING
    lease_until: datetime | None = None
    attempts: int = 0


def canonical_command_payload(
    command_id: UUID,
    name: str,
    expires_at: datetime,
) -> bytes:
    """Serialize signed fields deterministically and without delimiter ambiguity."""

    normalized_expiry = _utc(expires_at).isoformat(timespec="microseconds")
    return json.dumps(
        {
            "command_id": str(command_id),
            "expires_at": normalized_expiry,
            "name": name,
            "protocol_version": COMMAND_PROTOCOL_VERSION,
        },
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
