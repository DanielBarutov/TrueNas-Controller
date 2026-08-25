"""Concrete SQLAlchemy unit-of-work implementation."""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports import (
    AgentCommandRepository,
    OutboxRepository,
    PublishJobRepository,
    PublishTargetRepository,
    StationRepository,
    UnitOfWork,
)
from repository.agent_commands import SqlAlchemyAgentCommandRepository
from repository.agents import SqlAlchemyAgentRepository
from repository.enrollment_tokens import SqlAlchemyEnrollmentTokenRepository
from repository.outbox import SqlAlchemyOutboxRepository
from repository.provisioning_tokens import SqlAlchemyProvisioningTokenRepository
from repository.publish_jobs import SqlAlchemyPublishJobRepository
from repository.publish_targets import SqlAlchemyPublishTargetRepository
from repository.rules import SqlAlchemyProcessRuleRepository
from repository.snapshots import SqlAlchemyProcessSnapshotRepository
from repository.stations import SqlAlchemyStationRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Own exactly one session for one application operation."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._stations: StationRepository | None = None
        self._enrollment_tokens: SqlAlchemyEnrollmentTokenRepository | None = None
        self._provisioning_tokens: SqlAlchemyProvisioningTokenRepository | None = None
        self._agents: SqlAlchemyAgentRepository | None = None
        self._agent_commands: AgentCommandRepository | None = None
        self._process_rules: SqlAlchemyProcessRuleRepository | None = None
        self._process_snapshots: SqlAlchemyProcessSnapshotRepository | None = None
        self._publish_jobs: PublishJobRepository | None = None
        self._publish_targets: PublishTargetRepository | None = None
        self._outbox_events: OutboxRepository | None = None

    @property
    def stations(self) -> StationRepository:
        if self._stations is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._stations

    @property
    def enrollment_tokens(self) -> SqlAlchemyEnrollmentTokenRepository:
        if self._enrollment_tokens is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._enrollment_tokens

    @property
    def provisioning_tokens(self) -> SqlAlchemyProvisioningTokenRepository:
        if self._provisioning_tokens is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._provisioning_tokens

    @property
    def agents(self) -> SqlAlchemyAgentRepository:
        if self._agents is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._agents

    @property
    def agent_commands(self) -> AgentCommandRepository:
        if self._agent_commands is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._agent_commands

    @property
    def process_rules(self) -> SqlAlchemyProcessRuleRepository:
        if self._process_rules is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._process_rules

    @property
    def process_snapshots(self) -> SqlAlchemyProcessSnapshotRepository:
        if self._process_snapshots is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._process_snapshots

    @property
    def publish_jobs(self) -> PublishJobRepository:
        if self._publish_jobs is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._publish_jobs

    @property
    def publish_targets(self) -> PublishTargetRepository:
        if self._publish_targets is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._publish_targets

    @property
    def outbox_events(self) -> OutboxRepository:
        if self._outbox_events is None:
            raise RuntimeError("unit of work must be entered before accessing repositories")
        return self._outbox_events

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        if self._session is not None:
            raise RuntimeError("unit of work cannot be entered twice")
        self._session = self._session_factory()
        self._stations = SqlAlchemyStationRepository(self._session)
        self._enrollment_tokens = SqlAlchemyEnrollmentTokenRepository(self._session)
        self._provisioning_tokens = SqlAlchemyProvisioningTokenRepository(self._session)
        self._agents = SqlAlchemyAgentRepository(self._session)
        self._agent_commands = SqlAlchemyAgentCommandRepository(self._session)
        self._process_rules = SqlAlchemyProcessRuleRepository(self._session)
        self._process_snapshots = SqlAlchemyProcessSnapshotRepository(self._session)
        self._publish_jobs = SqlAlchemyPublishJobRepository(self._session)
        self._publish_targets = SqlAlchemyPublishTargetRepository(self._session)
        self._outbox_events = SqlAlchemyOutboxRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if exc_type is not None:
                await session.rollback()
        finally:
            await session.close()
            self._session = None
            self._stations = None
            self._enrollment_tokens = None
            self._provisioning_tokens = None
            self._agents = None
            self._agent_commands = None
            self._process_rules = None
            self._process_snapshots = None
            self._publish_jobs = None
            self._publish_targets = None
            self._outbox_events = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("unit of work must be entered before transaction operations")
        return self._session


class SqlAlchemyUnitOfWorkFactory:
    """Create a fresh UoW object for every use case or worker message."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)
