from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from application.agent_commands import IssueAgentCommandUseCase
from application.lifecycle import CreateStationUseCase, EnrollAgentUseCase, ReceiveHeartbeatUseCase
from domain.agent_command import AgentCommandStatus
from domain.snapshot import ProcessSnapshot
from domain.station import StationRole
from repository.database import create_engine, create_session_factory
from repository.models import Base
from repository.uow import SqlAlchemyUnitOfWorkFactory


class FakeSigner:
    def sign(self, command_id, name: str, expires_at: datetime) -> str:
        return f"signed:{command_id}:{name}:{expires_at.isoformat()}"


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    database_engine = create_engine("sqlite+aiosqlite:///:memory:")
    async with database_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database_engine
    await database_engine.dispose()


async def test_agent_command_is_leased_retried_and_acknowledged(
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
    agent_uuid = uuid4()
    enrollment = await EnrollAgentUseCase(factory).execute(
        enrollment_token=registration.enrollment_token,
        agent_uuid=agent_uuid,
        hostname="client-01",
        agent_version="1.0.0",
        now=now,
    )
    issued = await IssueAgentCommandUseCase(factory, FakeSigner()).execute(
        agent_uuid=agent_uuid,
        name="refresh_process_snapshot",
        now=now,
    )
    heartbeat = await ReceiveHeartbeatUseCase(factory).execute(
        credential=enrollment.credential,
        snapshot=ProcessSnapshot(
            station_id=registration.station.station_id,
            captured_at=now,
            agent_version="1.0.0",
        ),
        received_at=now + timedelta(seconds=1),
    )
    assert heartbeat.commands[0].id == issued.id
    assert heartbeat.commands[0].status is AgentCommandStatus.LEASED

    async with factory() as uow:
        binding = await uow.agents.get_by_agent_uuid(agent_uuid)
        assert binding is not None
        second_claim = await uow.agent_commands.claim_for_agent(
            binding.id,
            now=now + timedelta(seconds=2),
            lease_for=timedelta(seconds=30),
            limit=16,
        )
        await uow.commit()
    assert second_claim == ()

    async with factory() as uow:
        binding = await uow.agents.get_by_agent_uuid(agent_uuid)
        assert binding is not None
        assert (
            await uow.agent_commands.claim_for_agent(
                binding.id,
                now=now + timedelta(seconds=3),
                lease_for=timedelta(seconds=30),
                limit=16,
            )
            == ()
        )

    async with factory() as uow:
        binding = await uow.agents.get_by_agent_uuid(agent_uuid)
        assert binding is not None
        retry_claim = await uow.agent_commands.claim_for_agent(
            binding.id,
            now=now + timedelta(seconds=32),
            lease_for=timedelta(seconds=30),
            limit=16,
        )
        assert retry_claim[0].id == issued.id
        assert retry_claim[0].attempts == 2
        assert (
            await uow.agent_commands.acknowledge(
                binding.id,
                issued.id,
                now=now + timedelta(seconds=33),
            )
            is True
        )
        await uow.commit()

    async with factory() as uow:
        binding = await uow.agents.get_by_agent_uuid(agent_uuid)
        assert binding is not None
        assert (
            await uow.agent_commands.claim_for_agent(
                binding.id,
                now=now + timedelta(seconds=34),
                lease_for=timedelta(seconds=30),
                limit=16,
            )
            == ()
        )
