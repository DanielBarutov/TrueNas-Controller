"""Pure preflight wizard gating rules."""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from domain.preflight import PreflightReport


class WizardGateStatus(StrEnum):
    """Whether the wizard may advance to publish-job creation."""

    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class WizardGateInput:
    """Server-side reports and operator choice used for one gate evaluation."""

    admin_report: PreflightReport | None
    client_reports: dict[UUID, PreflightReport]
    selected_station_ids: tuple[UUID, ...]
    confirmation: bool | None


@dataclass(frozen=True, slots=True)
class WizardGateResult:
    """Explainable gate output; reasons are safe for an operator UI."""

    status: WizardGateStatus
    selected_station_ids: tuple[UUID, ...]
    reasons: tuple[str, ...]

    @property
    def can_advance(self) -> bool:
        return self.status is WizardGateStatus.READY


def evaluate_wizard_gate(data: WizardGateInput) -> WizardGateResult:
    """Require every server-side precondition before publish-job creation."""

    reasons: list[str] = []
    if data.admin_report is not None and not data.admin_report.can_publish:
        reasons.append("admin_preflight_blocked")
    if data.confirmation is not True:
        reasons.append("operator_confirmation_required")
    if not data.selected_station_ids:
        reasons.append("station_selection_required")

    for station_id in data.selected_station_ids:
        report = data.client_reports.get(station_id)
        if report is None:
            reasons.append(f"missing_preflight:{station_id}")
        elif not report.can_publish:
            reasons.append(f"client_preflight_blocked:{station_id}")

    status = WizardGateStatus.READY if not reasons else WizardGateStatus.BLOCKED
    return WizardGateResult(status, data.selected_station_ids, tuple(reasons))
