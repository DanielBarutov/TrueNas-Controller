"""Persisted operator confirmation and server-side publish preflight gate."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID

from application.ports import PreflightReportQuery, UnitOfWorkFactory
from application.publish_commands import PublishJobNotFoundError
from domain.preflight import PreflightReport
from domain.publish import PublishJob, PublishJobStatus
from domain.wizard import WizardGateInput, WizardGateResult, evaluate_wizard_gate


class PublishConfirmationStateError(ValueError):
    """Raised when a job cannot accept a preflight/confirmation command."""


@dataclass(frozen=True, slots=True)
class PublishPreflightResult:
    """Gate decision and the reports persisted for the publish job."""

    job: PublishJob
    gate: WizardGateResult
    admin_report: PreflightReport | None
    client_reports: dict[UUID, PreflightReport]


class PreparePublishJobUseCase:
    """Evaluate fresh reports and persist safe job/target preflight state."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        preflight_query: PreflightReportQuery,
    ) -> None:
        self._uow_factory = uow_factory
        self._preflight_query = preflight_query

    async def execute(
        self,
        *,
        job_id: UUID,
        admin_station_id: UUID | None,
        confirmation: bool | None,
    ) -> PublishPreflightResult:
        async with self._uow_factory() as uow:
            job = await uow.publish_jobs.get(job_id)
            if job is None:
                raise PublishJobNotFoundError("publish job not found")
            targets = await uow.publish_targets.list_for_job(job.id)

        self._validate_status(job)
        selected_station_ids = tuple(target.station_id for target in targets if target.selected)
        admin_report = (
            await self._preflight_query.execute(station_id=admin_station_id)
            if admin_station_id is not None
            else None
        )
        client_reports = {
            station_id: await self._preflight_query.execute(station_id=station_id)
            for station_id in selected_station_ids
        }
        gate = evaluate_wizard_gate(
            WizardGateInput(
                admin_report=admin_report,
                client_reports=client_reports,
                selected_station_ids=selected_station_ids,
                confirmation=confirmation,
            )
        )

        async with self._uow_factory() as uow:
            current_job = await uow.publish_jobs.get(job_id)
            if current_job is None:
                raise PublishJobNotFoundError("publish job not found")
            current_targets = await uow.publish_targets.list_for_job(job_id)
            if {target.station_id for target in current_targets} != {
                target.station_id for target in targets
            }:
                raise PublishConfirmationStateError(
                    "publish target selection changed during preflight"
                )
            self._validate_status(current_job)

            updated_targets = tuple(
                replace(
                    target,
                    preflight_status=(
                        client_reports[target.station_id].status.value if target.selected else None
                    ),
                    preflight_result=(
                        _serialize_report(client_reports[target.station_id])
                        if target.selected
                        else None
                    ),
                )
                for target in current_targets
            )
            updated_job = self._update_job(current_job, gate, confirmation)
            for target in updated_targets:
                await uow.publish_targets.update(target)
            await uow.publish_jobs.update(updated_job)
            await uow.commit()

        return PublishPreflightResult(updated_job, gate, admin_report, client_reports)

    @staticmethod
    def _validate_status(job: PublishJob) -> None:
        if job.status not in {
            PublishJobStatus.DRAFT,
            PublishJobStatus.PREFLIGHT,
            PublishJobStatus.AWAITING_CONFIRMATION,
        }:
            raise PublishConfirmationStateError(
                f"job cannot accept preflight in state {job.status.value}"
            )

    @staticmethod
    def _update_job(
        job: PublishJob,
        gate: WizardGateResult,
        confirmation: bool | None,
    ) -> PublishJob:
        updated = job
        if updated.status is PublishJobStatus.DRAFT:
            updated = updated.transition(PublishJobStatus.PREFLIGHT)

        preflight_ready = gate.can_advance or all(
            reason == "operator_confirmation_required" for reason in gate.reasons
        )
        if preflight_ready and updated.status is PublishJobStatus.PREFLIGHT:
            updated = updated.transition(PublishJobStatus.AWAITING_CONFIRMATION)

        confirmation_value = updated.client_confirmation if confirmation is None else confirmation
        confirmation_at = (
            updated.client_confirmation_at if confirmation is None else datetime.now(UTC)
        )
        return replace(
            updated,
            status_reason=None if gate.can_advance else ";".join(gate.reasons),
            client_confirmation=confirmation_value,
            client_confirmation_at=confirmation_at,
        )


def _serialize_report(report: PreflightReport) -> dict[str, object]:
    """Convert a domain report into JSON-safe, secret-free persistence data."""

    return {
        "station_id": str(report.station_id),
        "status": report.status.value,
        "evaluated_at": report.evaluated_at.isoformat(),
        "checks": [
            {
                "status": check.status.value,
                "code": check.code,
                "message": check.message,
                "observed_at": check.observed_at.isoformat(),
                "source_snapshot_id": (
                    None if check.source_snapshot_id is None else str(check.source_snapshot_id)
                ),
                "matched_processes": [
                    {
                        "name": process.name,
                        "pid": process.pid,
                        "path": process.path,
                    }
                    for process in check.matched_processes
                ],
            }
            for check in report.checks
        ],
    }
