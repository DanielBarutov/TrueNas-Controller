from uuid import UUID

import pytest

from application.process_rules import (
    CreateProcessRuleUseCase,
    DeleteProcessRuleUseCase,
    ListProcessRulesUseCase,
)
from domain.preflight import ProcessRule, RuleSeverity
from domain.station import StationRole


class FakeRules:
    def __init__(self) -> None:
        self.rules: dict[UUID, ProcessRule] = {}
        self.commits = 0

    async def list_all(self) -> tuple[ProcessRule, ...]:
        return tuple(self.rules.values())

    async def list_for_role(self, role: StationRole) -> tuple[ProcessRule, ...]:
        return tuple(rule for rule in self.rules.values() if rule.role in {None, role})

    async def add(self, rule: ProcessRule) -> None:
        self.rules[rule.id] = rule  # type: ignore[index]

    async def delete(self, rule_id: UUID) -> bool:
        return self.rules.pop(rule_id, None) is not None


class FakeUow:
    def __init__(self, rules: FakeRules) -> None:
        self.process_rules = rules

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def commit(self) -> None:
        self.process_rules.commits += 1


@pytest.mark.asyncio
async def test_process_rule_commands_create_list_and_delete_policy() -> None:
    rules = FakeRules()

    def factory() -> FakeUow:
        return FakeUow(rules)

    created = await CreateProcessRuleUseCase(factory).execute(
        name="  Steam.exe ",
        role=StationRole.CLIENT,
        required_closed=True,
        severity=RuleSeverity.BLOCKING,
        enabled=True,
        persistent_policy=False,
    )

    assert created.id is not None
    assert created.name == "Steam.exe"
    assert await ListProcessRulesUseCase(factory).execute() == (created,)
    assert await DeleteProcessRuleUseCase(factory).execute(rule_id=created.id) is True
    assert await ListProcessRulesUseCase(factory).execute() == ()
    assert rules.commits == 2


@pytest.mark.asyncio
async def test_process_rule_command_rejects_blank_name() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        await CreateProcessRuleUseCase(lambda: FakeUow(FakeRules())).execute(
            name="  ",
            role=None,
            required_closed=True,
            severity=RuleSeverity.BLOCKING,
            enabled=True,
            persistent_policy=False,
        )
