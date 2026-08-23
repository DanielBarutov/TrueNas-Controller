from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from application.lifecycle import CreateStationUseCase, EnrollAgentUseCase, ReceiveHeartbeatUseCase
from application.preflight import EvaluateStationPreflightUseCase
from domain.preflight import CheckStatus, ProcessRule, RuleSeverity
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from domain.station import StationRole
from repository.database import create_engine, create_session_factory
from repository.models import Base, ProcessRuleRecord, ProcessSnapshotRecord
from repository.uow import SqlAlchemyUnitOfWorkFactory


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


async def test_process_rule_repository_filters_role_and_enabled(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    async with factory() as uow:
        await uow.process_rules.add(ProcessRule("global.exe"))
        await uow.process_rules.add(ProcessRule("admin.exe", role=StationRole.ADMIN))
        await uow.process_rules.add(ProcessRule("disabled.exe", enabled=False))
        await uow.commit()

    async with factory() as uow:
        rules = await uow.process_rules.list_for_role(StationRole.CLIENT)

    assert [rule.name for rule in rules] == ["global.exe"]


async def test_application_preflight_uses_latest_snapshot_and_rules(
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
    async with factory() as uow:
        await uow.process_rules.add(ProcessRule("game.exe", severity=RuleSeverity.BLOCKING))
        await uow.commit()
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )
    await ReceiveHeartbeatUseCase(factory).execute(
        credential=enrollment.credential,
        snapshot=ProcessSnapshot(
            station_id=registration.station.station_id,
            captured_at=now,
            agent_version="1.0.0",
            processes=(ProcessInfo("game.exe", 10, "D:\\Games\\game.exe"),),
            drives=(DriveInfo("D:", True, 100),),
        ),
        received_at=now,
    )

    report = await EvaluateStationPreflightUseCase(factory).execute(
        station_id=registration.station.station_id,
        min_free_bytes=50,
        now=now + timedelta(seconds=1),
    )

    assert report.status is CheckStatus.BLOCK
    assert report.can_publish is False
    async with create_session_factory(engine)() as session:
        assert await session.scalar(select(ProcessSnapshotRecord)) is not None
        assert await session.scalar(select(ProcessRuleRecord)) is not None


async def test_application_preflight_without_snapshot_is_unknown(engine: AsyncEngine) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    registration = await CreateStationUseCase(factory).execute(
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
    )

    report = await EvaluateStationPreflightUseCase(factory).execute(
        station_id=registration.station.station_id,
    )

    assert report.status is CheckStatus.UNKNOWN
    assert report.can_publish is False
