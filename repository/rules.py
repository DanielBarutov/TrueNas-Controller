"""SQLAlchemy process-rule repository."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.preflight import ProcessRule
from domain.station import StationRole
from repository.models import ProcessRuleRecord


class SqlAlchemyProcessRuleRepository:
    """Read enabled global/role-specific rules and stage new rules."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_role(self, role: StationRole) -> tuple[ProcessRule, ...]:
        statement = (
            select(ProcessRuleRecord)
            .where(
                ProcessRuleRecord.enabled.is_(True),
                or_(ProcessRuleRecord.role.is_(None), ProcessRuleRecord.role == role),
            )
            .order_by(ProcessRuleRecord.name, ProcessRuleRecord.id)
        )
        records = (await self._session.scalars(statement)).all()
        return tuple(
            ProcessRule(
                name=record.name,
                role=record.role,
                required_closed=record.required_closed,
                severity=record.severity,
                enabled=record.enabled,
                persistent_policy=record.persistent_policy,
            )
            for record in records
        )

    async def add(self, rule: ProcessRule) -> None:
        self._session.add(
            ProcessRuleRecord(
                name=rule.name,
                role=rule.role,
                required_closed=rule.required_closed,
                severity=rule.severity,
                enabled=rule.enabled,
                persistent_policy=rule.persistent_policy,
            )
        )
