"""SQLAlchemy repository for signed station-agent command delivery."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.agent_command import AgentCommand, AgentCommandName, AgentCommandStatus
from domain.time import ensure_utc
from repository.models import AgentCommandRecord


class SqlAlchemyAgentCommandRepository:
    """Lease commands transactionally and keep retries idempotent."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, command: AgentCommand) -> None:
        self._session.add(
            AgentCommandRecord(
                id=command.id,
                agent_id=command.agent_id,
                name=command.name.value,
                expires_at=command.expires_at,
                signature=command.signature,
                status=command.status.value,
                lease_until=command.lease_until,
                attempts=command.attempts,
            )
        )

    async def claim_for_agent(
        self,
        agent_id: UUID,
        *,
        now: datetime,
        lease_for: timedelta,
        limit: int,
    ) -> tuple[AgentCommand, ...]:
        if limit <= 0:
            raise ValueError("command claim limit must be positive")
        if lease_for <= timedelta(0):
            raise ValueError("command lease must be positive")
        statement = (
            select(AgentCommandRecord)
            .where(
                AgentCommandRecord.agent_id == agent_id,
                AgentCommandRecord.expires_at > now,
                or_(
                    AgentCommandRecord.status == AgentCommandStatus.PENDING.value,
                    and_(
                        AgentCommandRecord.status == AgentCommandStatus.LEASED.value,
                        AgentCommandRecord.lease_until <= now,
                    ),
                ),
            )
            .order_by(AgentCommandRecord.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        records = (await self._session.scalars(statement)).all()
        lease_until = now + lease_for
        commands: list[AgentCommand] = []
        for record in records:
            record.status = AgentCommandStatus.LEASED.value
            record.lease_until = lease_until
            record.attempts += 1
            commands.append(_to_domain(record))
        return tuple(commands)

    async def acknowledge(
        self,
        agent_id: UUID,
        command_id: UUID,
        *,
        now: datetime,
    ) -> bool:
        statement = (
            select(AgentCommandRecord)
            .where(
                AgentCommandRecord.id == command_id,
                AgentCommandRecord.agent_id == agent_id,
            )
            .with_for_update()
        )
        record = await self._session.scalar(statement)
        if record is None:
            return False
        if record.status == AgentCommandStatus.ACKNOWLEDGED.value:
            return True
        if ensure_utc(record.expires_at) <= ensure_utc(now):
            record.status = AgentCommandStatus.EXPIRED.value
            record.lease_until = None
            return False
        if record.status != AgentCommandStatus.LEASED.value:
            return False
        if record.lease_until is not None and ensure_utc(record.lease_until) < ensure_utc(now):
            return False
        record.status = AgentCommandStatus.ACKNOWLEDGED.value
        record.acknowledged_at = now
        record.lease_until = None
        return True


def _to_domain(record: AgentCommandRecord) -> AgentCommand:
    try:
        name = AgentCommandName(record.name)
        status = AgentCommandStatus(record.status)
    except ValueError as exc:
        raise ValueError("stored agent command is invalid") from exc
    return AgentCommand(
        id=record.id,
        agent_id=record.agent_id,
        name=name,
        expires_at=ensure_utc(record.expires_at),
        signature=record.signature,
        status=status,
        lease_until=ensure_utc(record.lease_until) if record.lease_until is not None else None,
        attempts=record.attempts,
    )
