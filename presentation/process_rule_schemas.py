"""HTTP schemas for the operator process policy."""

from uuid import UUID

from pydantic import BaseModel, Field

from domain.preflight import ProcessRule, RuleSeverity
from domain.station import StationRole


class ProcessRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: StationRole | None = None
    required_closed: bool = True
    severity: RuleSeverity = RuleSeverity.BLOCKING
    enabled: bool = True
    persistent_policy: bool = False


class ProcessRuleResponse(BaseModel):
    id: UUID
    name: str
    role: StationRole | None
    required_closed: bool
    severity: RuleSeverity
    enabled: bool
    persistent_policy: bool

    @classmethod
    def from_domain(cls, rule: ProcessRule) -> "ProcessRuleResponse":
        if rule.id is None:
            raise ValueError("process rule has no persistent id")
        return cls(
            id=rule.id,
            name=rule.name,
            role=rule.role,
            required_closed=rule.required_closed,
            severity=rule.severity,
            enabled=rule.enabled,
            persistent_policy=rule.persistent_policy,
        )
