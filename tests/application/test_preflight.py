from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from application.lifecycle import CreateStationUseCase, EnrollAgentUseCase, ReceiveHeartbeatUseCase
import application.preflight as preflight_module
from application.preflight import EvaluateStationPreflightUseCase
from domain.preflight import CheckStatus, ProcessRule, RuleSeverity
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from domain.station import StationRole
from repository.database import create_engine, create_session_factory
from repository.models import Base, ProcessRuleRecord, ProcessSnapshotRecord
from repository.snapshots import SqlAlchemyProcessSnapshotRepository
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


@pytest.mark.parametrize("new_capture_age", [0, 45])
async def test_preflight_uses_latest_received_heartbeat_after_clock_correction(
    engine: AsyncEngine,
    new_capture_age: int,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Clock correction",
        hostname="clock-correction",
        role=StationRole.CLIENT,
        now=now,
    )
    station_id = registration.station.station_id
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=uuid4(),
        hostname="clock-correction",
        agent_version="1.0.0",
        now=now,
    )
    latest_received_at = now + timedelta(seconds=10)
    latest_captured_at = latest_received_at - timedelta(seconds=new_capture_age)
    for captured_at, received_at in (
        (now + timedelta(minutes=1), now),
        (latest_captured_at, latest_received_at),
    ):
        await ReceiveHeartbeatUseCase(factory).execute(
            credential=enrollment.credential,
            snapshot=ProcessSnapshot(
                station_id=station_id,
                captured_at=captured_at,
                agent_version="1.0.0",
                drives=(DriveInfo("D:", True, 100),),
            ),
            received_at=received_at,
        )

    async with factory() as uow:
        latest = await uow.process_snapshots.latest(station_id)
    assert latest is not None
    assert latest.captured_at.replace(tzinfo=UTC) == latest_captured_at

    report = await EvaluateStationPreflightUseCase(factory).execute(
        station_id=station_id,
        now=latest_received_at + timedelta(seconds=1),
    )

    assert report.can_publish is (new_capture_age == 0)
    assert report.checks[0].code == ("snapshot_fresh" if new_capture_age == 0 else "snapshot_stale")


@pytest.mark.parametrize(
    ("capture_offset", "explicit_now", "expected_code"),
    [(1, False, "snapshot_fresh"), (-29, False, "snapshot_stale"), (-29, True, "snapshot_fresh")],
)
async def test_preflight_evaluates_freshness_after_snapshot_read(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    capture_offset: int,
    explicit_now: bool,
    expected_code: str,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    started_at = datetime(2026, 9, 8, 12, tzinfo=UTC)
    registration = await CreateStationUseCase(factory).execute(
        display_name="Read timing",
        hostname="read-timing",
        role=StationRole.CLIENT,
        now=started_at,
    )
    clock = [started_at]

    class ReadClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0].astimezone(tz)

    async def latest_during_read(self, station_id):
        # Simulate a heartbeat arriving during IO, or a previously fresh
        # snapshot expiring before the read completes, without wall-clock sleeps.
        clock[0] = started_at + timedelta(seconds=2)
        return ProcessSnapshot(
            station_id=station_id,
            captured_at=started_at + timedelta(seconds=capture_offset),
            agent_version="1.0.0",
            drives=(DriveInfo("D:", True, 100),),
        )

    monkeypatch.setattr(preflight_module, "datetime", ReadClock)
    monkeypatch.setattr(SqlAlchemyProcessSnapshotRepository, "latest", latest_during_read)

    report = await EvaluateStationPreflightUseCase(factory).execute(
        station_id=registration.station.station_id,
        now=started_at if explicit_now else None,
    )

    assert report.evaluated_at == (started_at if explicit_now else clock[0])
    assert report.checks[0].code == expected_code
    assert report.can_publish is (expected_code == "snapshot_fresh")


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
