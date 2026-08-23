"""Versioned agent payloads and safe server-command validation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from domain.snapshot import ProcessSnapshot

AGENT_PROTOCOL_VERSION = "1"


class HeartbeatTransportError(RuntimeError):
    """Heartbeat delivery failed without exposing credentials or payload data."""


class HeartbeatTransport(Protocol):
    """Outbound transport used by the agent heartbeat loop."""

    async def send(
        self,
        payload: Mapping[str, object],
        credential: str,
    ) -> tuple[ServerCommand, ...]:
        """Send one heartbeat and return signed commands included in its response."""

    async def acknowledge(self, command_id: UUID, credential: str) -> None:
        """Acknowledge one successfully executed command."""


@dataclass(frozen=True, slots=True)
class AgentIdentity:
    """Non-secret identity metadata included in the agent payload."""

    station_id: UUID
    hostname: str
    agent_version: str
    ip_addresses: tuple[str, ...] = ()
    mac_addresses: tuple[str, ...] = ()


class HeartbeatPayloadBuilder:
    """Serialize a domain snapshot into the versioned wire payload."""

    def __init__(self, identity: AgentIdentity) -> None:
        self._identity = identity

    def build(self, snapshot: ProcessSnapshot) -> dict[str, object]:
        if snapshot.station_id != self._identity.station_id:
            raise ValueError("snapshot station does not match agent identity")
        return {
            "protocol_version": AGENT_PROTOCOL_VERSION,
            "station_id": str(snapshot.station_id),
            "hostname": self._identity.hostname,
            "ip_addresses": list(self._identity.ip_addresses),
            "mac_addresses": list(self._identity.mac_addresses),
            "agent_version": snapshot.agent_version,
            "captured_at": _utc_isoformat(snapshot.captured_at),
            "processes": [
                {"name": item.name, "pid": item.pid, "path": item.path}
                for item in snapshot.processes
            ],
            "drives": [
                {
                    "letter": item.letter,
                    "present": item.present,
                    "free_bytes": item.free_bytes,
                }
                for item in snapshot.drives
            ],
        }


@dataclass(frozen=True, slots=True)
class ServerCommand:
    """Opaque server command accepted only after local validation."""

    command_id: UUID
    name: str
    expires_at: datetime
    signature: str


SignatureVerifier = Callable[[ServerCommand], bool]


class InvalidAgentCommand(ValueError):
    """Command is unknown, expired, malformed or not authenticated."""


class AgentCommandValidator:
    """Allow only the non-destructive process refresh command."""

    ALLOWED_COMMAND = "refresh_process_snapshot"

    def __init__(self, signature_verifier: SignatureVerifier) -> None:
        self._signature_verifier = signature_verifier

    def validate(self, command: ServerCommand, *, now: datetime) -> ServerCommand:
        if command.name != self.ALLOWED_COMMAND:
            raise InvalidAgentCommand("unsupported agent command")
        if not command.signature:
            raise InvalidAgentCommand("agent command signature is missing")
        if _utc(command.expires_at) <= _utc(now):
            raise InvalidAgentCommand("agent command is expired")
        if not self._signature_verifier(command):
            raise InvalidAgentCommand("agent command signature is invalid")
        return command


class AgentCommandReceiver(Protocol):
    """Local command execution boundary owned by the agent runtime."""

    async def handle(self, command: ServerCommand, *, now: datetime) -> None:
        """Validate and execute one supported command."""


def _utc_isoformat(value: datetime) -> str:
    return _utc(value).isoformat()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
