"""Operator commands for the editable process preflight policy."""

from uuid import UUID, uuid4

from application.ports import UnitOfWorkFactory
from domain.preflight import ProcessRule, RuleSeverity
from domain.station import StationRole


class ListProcessRulesUseCase:
    """Read the complete process policy for the operator screen."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self) -> tuple[ProcessRule, ...]:
        async with self._uow_factory() as uow:
            return await uow.process_rules.list_all()


class CreateProcessRuleUseCase:
    """Create one explicit rule; the caller must choose its blocking policy."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        name: str,
        role: StationRole | None,
        required_closed: bool,
        severity: RuleSeverity,
        enabled: bool,
        persistent_policy: bool,
    ) -> ProcessRule:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("process rule name cannot be empty")
        rule = ProcessRule(
            id=uuid4(),
            name=normalized_name,
            role=role,
            required_closed=required_closed,
            severity=severity,
            enabled=enabled,
            persistent_policy=persistent_policy,
        )
        async with self._uow_factory() as uow:
            await uow.process_rules.add(rule)
            await uow.commit()
        return rule


class DeleteProcessRuleUseCase:
    """Remove only a policy row; historical snapshots remain immutable."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, rule_id: UUID) -> bool:
        async with self._uow_factory() as uow:
            deleted = await uow.process_rules.delete(rule_id)
            if deleted:
                await uow.commit()
            return deleted
