"""Station registry, enrollment and heartbeat use cases."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from uuid import UUID, uuid4

from application.ports import UnitOfWorkFactory
from domain.agent import AgentBinding
from domain.enrollment import EnrollmentToken
from domain.snapshot import ProcessSnapshot
from domain.station import Station, StationRole, StationStatus
from domain.time import ensure_utc

ENROLLMENT_TOKEN_TTL = timedelta(minutes=10)
HEARTBEAT_CLOCK_SKEW = timedelta(minutes=5)


class EnrollmentRejectedError(ValueError):
    """Raised when an enrollment token cannot be claimed."""


class AgentUnauthorizedError(ValueError):
    """Raised when an agent credential or station binding is invalid."""


class HeartbeatRejectedError(ValueError):
    """Raised when a heartbeat timestamp or payload cannot be accepted."""


@dataclass(frozen=True, slots=True)
class StationRegistration:
    """Station plus the one-time token shown to the operator once."""

    station: Station
    enrollment_token: str
    enrollment_expires_at: datetime


@dataclass(frozen=True, slots=True)
class EnrollmentResult:
    """Credential returned exactly once after successful enrollment."""

    station_id: UUID
    credential: str
    server_time: datetime


@dataclass(frozen=True, slots=True)
class HeartbeatResult:
    """Acknowledgement returned after a heartbeat commit."""

    station_id: UUID
    received_at: datetime


def hash_secret(value: str) -> str:
    """Hash a high-entropy token/credential before persistence."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class CreateStationUseCase:
    """Create an enabled station draft and one enrollment token."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        display_name: str,
        hostname: str,
        role: StationRole,
        now: datetime | None = None,
    ) -> StationRegistration:
        created_at = ensure_utc(now or datetime.now(UTC))
        station = Station(
            id=uuid4(),
            station_id=uuid4(),
            display_name=display_name,
            hostname=hostname,
            role=role,
            status=StationStatus.OFFLINE,
        )
        raw_token = secrets.token_urlsafe(32)
        token_expires_at = created_at + ENROLLMENT_TOKEN_TTL
        token = EnrollmentToken(
            id=uuid4(),
            station_id=station.station_id,
            token_hash=hash_secret(raw_token),
            expires_at=token_expires_at,
        )
        async with self._uow_factory() as uow:
            await uow.stations.add(station)
            await uow.enrollment_tokens.add(token)
            await uow.commit()
        return StationRegistration(station, raw_token, token_expires_at)


class EnrollAgentUseCase:
    """Atomically claim a token and create a station-bound agent credential."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        enrollment_token: str,
        agent_uuid: UUID,
        hostname: str,
        agent_version: str,
        ip_addresses: tuple[str, ...] = (),
        mac_addresses: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> EnrollmentResult:
        enrolled_at = ensure_utc(now or datetime.now(UTC))
        raw_credential = secrets.token_urlsafe(32)
        async with self._uow_factory() as uow:
            token = await uow.enrollment_tokens.consume(hash_secret(enrollment_token), enrolled_at)
            if token is None:
                raise EnrollmentRejectedError("enrollment token is invalid or expired")
            await uow.stations.update_hostname(token.station_id, hostname)
            agent = AgentBinding(
                id=uuid4(),
                station_id=token.station_id,
                agent_uuid=agent_uuid,
                agent_version=agent_version,
                credential_hash=hash_secret(raw_credential),
                credential_created_at=enrolled_at,
                last_ip_addresses=ip_addresses,
                last_mac_addresses=mac_addresses,
            )
            await uow.agents.add(agent)
            await uow.commit()
        return EnrollmentResult(token.station_id, raw_credential, enrolled_at)


class ReceiveHeartbeatUseCase:
    """Validate an agent binding and persist its normalized snapshot."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        credential: str,
        snapshot: ProcessSnapshot,
        received_at: datetime | None = None,
    ) -> HeartbeatResult:
        accepted_at = ensure_utc(received_at or datetime.now(UTC))
        normalized_snapshot = replace(snapshot, captured_at=ensure_utc(snapshot.captured_at))
        if abs(accepted_at - normalized_snapshot.captured_at) > HEARTBEAT_CLOCK_SKEW:
            raise HeartbeatRejectedError("heartbeat timestamp is outside the allowed clock skew")
        async with self._uow_factory() as uow:
            agent = await uow.agents.get_by_credential_hash(hash_secret(credential))
            if agent is None or not agent.can_accept_heartbeat():
                raise AgentUnauthorizedError("agent credential or station binding is invalid")
            if agent.station_id != normalized_snapshot.station_id:
                raise AgentUnauthorizedError("agent is bound to another station")
            await uow.agents.record_heartbeat(agent.id, normalized_snapshot, accepted_at)
            await uow.commit()
        return HeartbeatResult(normalized_snapshot.station_id, accepted_at)
