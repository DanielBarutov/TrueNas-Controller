"""Station registry, enrollment and heartbeat use cases."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
import hashlib
import ipaddress
import re
import secrets
from uuid import UUID, uuid4

from application.ports import UnitOfWorkFactory
from domain.agent import AgentBinding
from domain.agent_command import AgentCommand
from domain.enrollment import EnrollmentToken
from domain.provisioning import ProvisioningToken
from domain.snapshot import ProcessSnapshot
from domain.station import Station, StationRole, StationStatus
from domain.time import ensure_utc

ENROLLMENT_TOKEN_TTL = timedelta(minutes=10)
PROVISIONING_TOKEN_TTL = timedelta(minutes=15)
HEARTBEAT_CLOCK_SKEW = timedelta(minutes=5)
AGENT_COMMAND_LEASE = timedelta(seconds=30)
AGENT_COMMAND_BATCH_SIZE = 16


class EnrollmentRejectedError(ValueError):
    """Raised when an enrollment token cannot be claimed."""


class ProvisioningRejectedError(ValueError):
    """Raised when a station bootstrap token cannot be claimed."""


class ProvisioningConflictError(ValueError):
    """Raised when bootstrap would replace an existing agent binding."""


class StationRegistrationConflictError(ValueError):
    """Raised when an active station already owns the requested stable UUID."""


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
class ProvisioningTokenRegistration:
    """Provisioning token shown to an operator exactly once."""

    token: str
    expires_at: datetime


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
    commands: tuple[AgentCommand, ...] = ()


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
        station_id: UUID | None = None,
        display_name: str,
        hostname: str,
        role: StationRole,
        now: datetime | None = None,
    ) -> StationRegistration:
        created_at = ensure_utc(now or datetime.now(UTC))
        station = Station(
            id=uuid4(),
            station_id=station_id or uuid4(),
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
            existing = await uow.stations.get(station.station_id)
            if existing is None:
                await uow.stations.add(station)
            elif existing.deleted_at is None:
                raise StationRegistrationConflictError(
                    "station with this stable UUID is already registered"
                )
            else:
                station = replace(station, id=existing.id)
                await uow.stations.restore(station)
            await uow.enrollment_tokens.add(token)
            await uow.commit()
        return StationRegistration(station, raw_token, token_expires_at)


class CreateProvisioningTokenUseCase:
    """Issue a short-lived token for automatic station creation on a client PC."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, now: datetime | None = None) -> ProvisioningTokenRegistration:
        created_at = ensure_utc(now or datetime.now(UTC))
        raw_token = secrets.token_urlsafe(32)
        expires_at = created_at + PROVISIONING_TOKEN_TTL
        token = ProvisioningToken(
            id=uuid4(),
            token_hash=hash_secret(raw_token),
            expires_at=expires_at,
        )
        async with self._uow_factory() as uow:
            await uow.provisioning_tokens.add(token)
            await uow.commit()
        return ProvisioningTokenRegistration(raw_token, expires_at)


class DeleteStationUseCase:
    """Remove a station from the active registry and invalidate its agent."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, station_id: UUID, now: datetime | None = None) -> bool:
        deleted_at = ensure_utc(now or datetime.now(UTC))
        async with self._uow_factory() as uow:
            deleted = await uow.stations.delete(station_id, deleted_at)
            if not deleted:
                return False
            await uow.commit()
        return True


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


class BootstrapAgentUseCase:
    """Create a client station when absent and enroll its agent atomically."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        provisioning_token: str,
        station_id: UUID,
        display_name: str,
        hostname: str,
        role: StationRole,
        agent_uuid: UUID,
        agent_version: str,
        ip_addresses: tuple[str, ...] = (),
        mac_addresses: tuple[str, ...] = (),
        now: datetime | None = None,
    ) -> EnrollmentResult:
        enrolled_at = ensure_utc(now or datetime.now(UTC))
        if role is not StationRole.CLIENT:
            raise ProvisioningRejectedError(
                "automatic bootstrap is allowed only for client stations"
            )
        if station_id != agent_uuid:
            raise ProvisioningRejectedError(
                "station_id and agent_uuid must be the same stable UUID"
            )
        raw_credential = secrets.token_urlsafe(32)
        async with self._uow_factory() as uow:
            token = await uow.provisioning_tokens.consume(
                hash_secret(provisioning_token), enrolled_at
            )
            if token is None:
                raise ProvisioningRejectedError("provisioning token is invalid or expired")

            existing_agent = await uow.agents.get_by_agent_uuid(agent_uuid)
            if existing_agent is not None:
                raise ProvisioningConflictError("agent UUID is already enrolled")

            station = await uow.stations.get(station_id)
            if station is None:
                station = Station(
                    id=uuid4(),
                    station_id=station_id,
                    display_name=display_name,
                    hostname=hostname,
                    role=role,
                    status=StationStatus.OFFLINE,
                )
                await uow.stations.add(station)
            elif station.deleted_at is not None:
                station = replace(
                    station,
                    display_name=display_name,
                    hostname=hostname,
                    role=role,
                    status=StationStatus.OFFLINE,
                    enabled=True,
                    deleted_at=None,
                )
                await uow.stations.restore(station)
            else:
                if station.role is not role:
                    raise ProvisioningConflictError("station exists with a different role")
                if await uow.agents.get_by_station_id(station_id) is not None:
                    raise ProvisioningConflictError("station already has an enrolled agent")
                await uow.stations.update_hostname(station_id, hostname)

            agent = AgentBinding(
                id=uuid4(),
                station_id=station_id,
                agent_uuid=agent_uuid,
                agent_version=agent_version,
                credential_hash=hash_secret(raw_credential),
                credential_created_at=enrolled_at,
                last_ip_addresses=ip_addresses,
                last_mac_addresses=mac_addresses,
            )
            await uow.agents.add(agent)
            await uow.commit()
        return EnrollmentResult(station_id, raw_credential, enrolled_at)


class ReceiveHeartbeatUseCase:
    """Validate an agent binding and persist its normalized snapshot."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        credential: str,
        snapshot: ProcessSnapshot,
        hostname: str | None = None,
        ip_addresses: tuple[str, ...] | None = None,
        mac_addresses: tuple[str, ...] | None = None,
        received_at: datetime | None = None,
    ) -> HeartbeatResult:
        accepted_at = ensure_utc(received_at or datetime.now(UTC))
        normalized_snapshot = replace(snapshot, captured_at=ensure_utc(snapshot.captured_at))
        normalized_hostname = _normalize_hostname(hostname)
        normalized_ips = _normalize_ip_addresses(ip_addresses)
        normalized_macs = _normalize_mac_addresses(mac_addresses)
        if abs(accepted_at - normalized_snapshot.captured_at) > HEARTBEAT_CLOCK_SKEW:
            raise HeartbeatRejectedError("heartbeat timestamp is outside the allowed clock skew")
        async with self._uow_factory() as uow:
            agent = await uow.agents.get_by_credential_hash(hash_secret(credential))
            if agent is None or not agent.can_accept_heartbeat():
                raise AgentUnauthorizedError("agent credential or station binding is invalid")
            if agent.station_id != normalized_snapshot.station_id:
                raise AgentUnauthorizedError("agent is bound to another station")
            await uow.agents.record_heartbeat(
                agent.id,
                normalized_snapshot,
                accepted_at,
                hostname=normalized_hostname,
                ip_addresses=normalized_ips,
                mac_addresses=normalized_macs,
            )
            commands = await uow.agent_commands.claim_for_agent(
                agent.id,
                now=accepted_at,
                lease_for=AGENT_COMMAND_LEASE,
                limit=AGENT_COMMAND_BATCH_SIZE,
            )
            await uow.commit()
        return HeartbeatResult(normalized_snapshot.station_id, accepted_at, commands)


def _normalize_hostname(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 255:
        raise HeartbeatRejectedError("agent hostname is invalid")
    return normalized


def _normalize_ip_addresses(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    normalized: list[str] = []
    for value in values:
        candidate = value.strip()
        try:
            ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise HeartbeatRejectedError("agent IP address is invalid") from exc
        if candidate not in normalized:
            normalized.append(candidate)
    if len(normalized) > 16:
        raise HeartbeatRejectedError("too many agent IP addresses")
    return tuple(normalized)


def _normalize_mac_addresses(values: tuple[str, ...] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    normalized: list[str] = []
    for value in values:
        candidate = value.strip().upper()
        if re.fullmatch(r"[0-9A-F]{2}([:-][0-9A-F]{2}){5}", candidate) is None:
            raise HeartbeatRejectedError("agent MAC address is invalid")
        if candidate not in normalized:
            normalized.append(candidate)
    if len(normalized) > 16:
        raise HeartbeatRejectedError("too many agent MAC addresses")
    return tuple(normalized)
