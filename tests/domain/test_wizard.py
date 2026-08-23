from datetime import UTC, datetime
from uuid import uuid4

from domain.preflight import CheckResult, CheckStatus, PreflightReport
from domain.wizard import WizardGateInput, WizardGateStatus, evaluate_wizard_gate

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def report(station_id, status: CheckStatus) -> PreflightReport:
    return PreflightReport(
        station_id=station_id,
        status=status,
        checks=(
            CheckResult(
                status=status,
                code=f"{status.value}_check",
                message=status.value,
                observed_at=NOW,
            ),
        ),
        evaluated_at=NOW,
    )


def test_blocked_admin_or_missing_confirmation_blocks_gate() -> None:
    admin_id = uuid4()
    client_id = uuid4()
    result = evaluate_wizard_gate(
        WizardGateInput(
            admin_report=report(admin_id, CheckStatus.BLOCK),
            client_reports={client_id: report(client_id, CheckStatus.PASS)},
            selected_station_ids=(client_id,),
            confirmation=None,
        )
    )

    assert result.status is WizardGateStatus.BLOCKED
    assert "admin_preflight_blocked" in result.reasons
    assert "operator_confirmation_required" in result.reasons


def test_missing_selection_or_client_report_blocks_gate() -> None:
    admin_id = uuid4()
    client_id = uuid4()
    no_selection = evaluate_wizard_gate(
        WizardGateInput(report(admin_id, CheckStatus.PASS), {}, (), True)
    )
    missing_report = evaluate_wizard_gate(
        WizardGateInput(report(admin_id, CheckStatus.PASS), {}, (client_id,), True)
    )

    assert no_selection.can_advance is False
    assert "station_selection_required" in no_selection.reasons
    assert f"missing_preflight:{client_id}" in missing_report.reasons


def test_block_or_unknown_client_report_blocks_gate() -> None:
    admin_id = uuid4()
    client_id = uuid4()

    for status in (CheckStatus.BLOCK, CheckStatus.UNKNOWN):
        result = evaluate_wizard_gate(
            WizardGateInput(
                admin_report=report(admin_id, CheckStatus.PASS),
                client_reports={client_id: report(client_id, status)},
                selected_station_ids=(client_id,),
                confirmation=True,
            )
        )
        assert result.status is WizardGateStatus.BLOCKED


def test_pass_and_warning_clients_with_confirmation_are_ready() -> None:
    admin_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    result = evaluate_wizard_gate(
        WizardGateInput(
            admin_report=report(admin_id, CheckStatus.WARNING),
            client_reports={
                first_id: report(first_id, CheckStatus.PASS),
                second_id: report(second_id, CheckStatus.WARNING),
            },
            selected_station_ids=(first_id, second_id),
            confirmation=True,
        )
    )

    assert result.status is WizardGateStatus.READY
    assert result.can_advance is True
    assert result.reasons == ()
