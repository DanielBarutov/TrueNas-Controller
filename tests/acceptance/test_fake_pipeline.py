from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.publish_commands import CreatePublishJobUseCase
from application.publish_confirmation import PreparePublishJobUseCase
from application.publish_dispatch import DispatchPublishJobUseCase
from application.publish_executor import FakePublishTaskExecutor
from domain.preflight import CheckStatus, PreflightReport
from domain.station import Station, StationRole, StationStatus
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory
from truenas_adapter.mock_client import FakePublishStorageAdapter
from worker.composition import PublishTaskApplicationHandler
from worker.outbox_relay import PublishOutboxRelay
from worker.tasks import PublishTaskPayload


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


def station(name: str, role: StationRole) -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name=name,
        hostname=name.casefold(),
        role=role,
        status=StationStatus.ONLINE,
    )


class FakePreflightQuery:
    def __init__(self, reports: dict[UUID, PreflightReport]) -> None:
        self._reports = reports

    async def execute(self, *, station_id: UUID) -> PreflightReport:
        return self._reports[station_id]


class CaptureQueue:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, UUID, str]] = []

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        self.calls.append((job_id, correlation_id, idempotency_key))


async def test_full_fake_publish_pipeline_is_persisted_and_idempotent(
    engine: AsyncEngine,
) -> None:
    factory = SqlAlchemyUnitOfWorkFactory(create_session_factory(engine))
    admin, client = station("Admin", StationRole.ADMIN), station("Client", StationRole.CLIENT)
    async with factory() as uow:
        await uow.stations.add(admin)
        await uow.stations.add(client)
        await uow.commit()

    draft = await CreatePublishJobUseCase(factory).execute(
        label="build-acceptance",
        game_name="game",
        station_ids=(client.station_id,),
        idempotency_key="acceptance-key",
        correlation_id=uuid4(),
        dry_run=False,
    )
    now = datetime.now(UTC)
    reports = {
        admin.station_id: PreflightReport(admin.station_id, CheckStatus.PASS, (), now),
        client.station_id: PreflightReport(client.station_id, CheckStatus.PASS, (), now),
    }
    prepared = await PreparePublishJobUseCase(
        factory,
        FakePreflightQuery(reports),
    ).execute(
        job_id=draft.job.id,
        admin_station_id=admin.station_id,
        confirmation=True,
    )
    assert prepared.job.status.value == "awaiting_confirmation"

    await DispatchPublishJobUseCase(factory).execute(job_id=draft.job.id)
    queue = CaptureQueue()
    relay_result = await PublishOutboxRelay(
        factory,
        queue,
        worker_id="acceptance-relay",
    ).run_once(now=datetime.now(UTC))
    assert relay_result.dispatched == 1
    assert len(queue.calls) == 1

    adapter = FakePublishStorageAdapter()
    handler = PublishTaskApplicationHandler(
        factory,
        lambda: FakePublishTaskExecutor(factory, lambda: adapter),
    )
    task = PublishTaskPayload(*queue.calls[0])
    await handler.handle(task)
    await handler.handle(task)

    async with factory() as uow:
        job = await uow.publish_jobs.get(draft.job.id)
        targets = await uow.publish_targets.list_for_job(draft.job.id)
    assert job is not None and job.status.value == "completed"
    assert targets[0].switch_status == "switched"
    assert targets[0].verify_status == "verified"
    assert len(adapter.masters) == 1
    assert len(adapter.clones) == 1
