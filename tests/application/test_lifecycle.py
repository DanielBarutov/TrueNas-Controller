from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from application.lifecycle import (
    AgentUnauthorizedError,
    BootstrapAgentUseCase,
    CreateProvisioningTokenUseCase,
    CreateStationUseCase,
    DeleteStationUseCase,
    EnrollAgentUseCase,
    EnrollmentRejectedError,
    HeartbeatRejectedError,
    ProvisioningRejectedError,
    ReceiveHeartbeatUseCase,
    hash_secret,
)
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from domain.station import StationRole
from repository.database import create_engine, create_session_factory
from repository.models import (
    AgentCommandRecord,
    AgentRecord,
    Base,
    EnrollmentTokenRecord,
    ProcessSnapshotRecord,
    ProvisioningTokenRecord,
    StationRecord,
)
from repository.uow import SqlAlchemyUnitOfWorkFactory


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


async def test_enrollment_is_one_shot_and_credential_is_hashed(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        now=now,
    )
    enrollment = EnrollAgentUseCase(factory)
    result = await enrollment.execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="client-01",
        agent_version="1.0.0",
        now=now + timedelta(seconds=1),
    )

    with pytest.raises(EnrollmentRejectedError):
        await enrollment.execute(
            enrollment_token=registration.enrollment_token,
            agent_uuid=uuid4(),
            hostname="client-01",
            agent_version="1.0.0",
            now=now + timedelta(seconds=2),
        )

    async with create_session_factory(engine)() as session:
        token = await session.scalar(select(EnrollmentTokenRecord))
        agent = await session.scalar(select(AgentRecord))
    assert token is not None and token.used_at is not None
    assert token.token_hash == hash_secret(registration.enrollment_token)
    assert token.token_hash != registration.enrollment_token
    assert agent is not None and agent.credential_hash != result.credential


async def test_create_station_preserves_report_station_uuid(engine: AsyncEngine) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    station_id = uuid4()

    registration = await CreateStationUseCase(factory).execute(
        station_id=station_id,
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
    )

    assert registration.station.station_id == station_id


async def test_provisioning_token_creates_and_enrolls_station_once(engine: AsyncEngine) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 25, 12, tzinfo=UTC)
    station_id = uuid4()
    token = await CreateProvisioningTokenUseCase(factory).execute(now=now)

    result = await BootstrapAgentUseCase(factory).execute(
        provisioning_token=token.token,
        station_id=station_id,
        display_name="Client auto",
        hostname="client-auto",
        role=StationRole.CLIENT,
        agent_uuid=station_id,
        agent_version="1.0.0",
        now=now + timedelta(seconds=1),
    )

    assert result.station_id == station_id
    async with create_session_factory(engine)() as session:
        station = await session.scalar(
            select(StationRecord).where(StationRecord.station_id == station_id)
        )
        agent = await session.scalar(select(AgentRecord))
        stored_token = await session.scalar(select(ProvisioningTokenRecord))
    assert station is not None
    assert station.display_name == "Client auto"
    assert agent is not None and agent.agent_uuid == station_id
    assert stored_token is not None and stored_token.used_at is not None

    with pytest.raises(ProvisioningRejectedError):
        await BootstrapAgentUseCase(factory).execute(
            provisioning_token=token.token,
            station_id=uuid4(),
            display_name="Second client",
            hostname="client-second",
            role=StationRole.CLIENT,
            agent_uuid=uuid4(),
            agent_version="1.0.0",
            now=now + timedelta(seconds=2),
        )


async def test_delete_station_hides_registry_and_removes_agent_binding(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        now=now,
    )
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )
    snapshot = ProcessSnapshot(
        station_id=registration.station.station_id,
        captured_at=now,
        agent_version="1.0.0",
    )
    await ReceiveHeartbeatUseCase(factory).execute(
        credential=enrollment.credential,
        snapshot=snapshot,
        received_at=now,
    )
    async with create_session_factory(engine)() as session:
        agent = await session.scalar(select(AgentRecord))
        assert agent is not None
        session.add(
            AgentCommandRecord(
                agent_id=agent.id,
                name="refresh_process_snapshot",
                expires_at=now + timedelta(minutes=5),
                signature="test-signature",
            )
        )
        await session.commit()

    deleted_at = now + timedelta(minutes=1)
    assert await DeleteStationUseCase(factory).execute(
        station_id=registration.station.station_id,
        now=deleted_at,
    )
    assert not await DeleteStationUseCase(factory).execute(
        station_id=registration.station.station_id,
        now=deleted_at + timedelta(seconds=1),
    )

    async with create_session_factory(engine)() as session:
        station = await session.scalar(select(StationRecord))
        token = await session.scalar(select(EnrollmentTokenRecord))
        stored_agent = await session.scalar(select(AgentRecord))
        stored_command = await session.scalar(select(AgentCommandRecord))
        stored_snapshot = await session.scalar(select(ProcessSnapshotRecord))
    assert station is not None
    assert station.enabled is False
    assert station.deleted_at is not None
    assert station.deleted_at.replace(tzinfo=UTC) == deleted_at
    assert station.state.value == "disabled"
    assert token is not None and token.revoked_at is not None
    assert token.revoked_at.replace(tzinfo=UTC) == deleted_at
    assert stored_agent is None
    assert stored_command is None
    assert stored_snapshot is not None

    with pytest.raises(AgentUnauthorizedError):
        await ReceiveHeartbeatUseCase(factory).execute(
            credential=enrollment.credential,
            snapshot=snapshot,
            received_at=deleted_at,
        )

    restored = await CreateStationUseCase(factory).execute(
        station_id=registration.station.station_id,
        display_name="Client 01 restored",
        hostname="client-01-restored",
        role=StationRole.CLIENT,
        now=deleted_at + timedelta(minutes=1),
    )
    assert restored.station.id == registration.station.id
    assert restored.station.deleted_at is None


async def test_heartbeat_updates_station_and_snapshot(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        now=now,
    )
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )
    snapshot = ProcessSnapshot(
        station_id=registration.station.station_id,
        captured_at=now,
        agent_version="1.0.1",
        processes=(ProcessInfo(name="game.exe", pid=42, path="D:\\Games\\game.exe"),),
        drives=(DriveInfo(letter="D:", present=True, free_bytes=1234),),
    )

    result = await ReceiveHeartbeatUseCase(factory).execute(
        credential=enrollment.credential,
        snapshot=snapshot,
        hostname="CLIENT-01-renamed",
        ip_addresses=("192.0.2.10",),
        mac_addresses=("00:11:22:33:44:55",),
        received_at=now + timedelta(seconds=1),
    )

    assert result.station_id == registration.station.station_id
    async with create_session_factory(engine)() as session:
        stored_snapshot = await session.scalar(select(ProcessSnapshotRecord))
        stored_agent = await session.scalar(select(AgentRecord))
        station = await session.scalar(select(StationRecord))
    assert stored_snapshot is not None
    assert stored_snapshot.processes == [
        {"name": "game.exe", "pid": 42, "path": "D:\\Games\\game.exe"}
    ]
    assert stored_agent is not None and stored_agent.status == "online"
    assert stored_agent.last_ip_addresses == ["192.0.2.10"]
    assert stored_agent.last_mac_addresses == ["00:11:22:33:44:55"]

    assert station is not None and station.hostname == "CLIENT-01-renamed"


async def test_heartbeat_rejects_wrong_binding_and_stale_timestamp(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        now=now,
    )
    other_registration = await CreateStationUseCase(factory).execute(
        display_name="Client 02",
        hostname="client-02",
        role=StationRole.CLIENT,
        now=now,
    )
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )
    receive = ReceiveHeartbeatUseCase(factory)

    with pytest.raises(AgentUnauthorizedError):
        await receive.execute(
            credential=enrollment.credential,
            snapshot=ProcessSnapshot(
                station_id=other_registration.station.station_id,
                captured_at=now,
                agent_version="1.0.0",
            ),
            received_at=now,
        )

    with pytest.raises(HeartbeatRejectedError):
        await receive.execute(
            credential=enrollment.credential,
            snapshot=ProcessSnapshot(
                station_id=registration.station.station_id,
                captured_at=now - timedelta(minutes=6),
                agent_version="1.0.0",
            ),
            received_at=now,
        )


async def test_agent_uuid_cannot_be_enrolled_twice(engine: AsyncEngine) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)
    first = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        now=now,
    )
    second = await CreateStationUseCase(factory).execute(
        display_name="Client 02",
        hostname="client-02",
        role=StationRole.CLIENT,
        now=now,
    )
    agent_uuid = uuid4()
    enrollment = EnrollAgentUseCase(factory)
    await enrollment.execute(
        enrollment_token=first.enrollment_token,
        agent_uuid=agent_uuid,
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )

    with pytest.raises(IntegrityError):
        await enrollment.execute(
            enrollment_token=second.enrollment_token,
            agent_uuid=agent_uuid,
            hostname="client-02",
            agent_version="1.0.0",
            now=now,
        )
