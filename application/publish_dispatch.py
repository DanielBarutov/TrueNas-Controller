"""Safe transition from confirmed preflight into the worker queue."""

from dataclasses import dataclass, replace
from uuid import UUID, uuid4

from application.ports import UnitOfWorkFactory
from application.publish_commands import PublishJobNotFoundError
from domain.outbox import OutboxEvent
from domain.preflight import CheckStatus
from domain.publish import PublishJob, PublishJobStatus, PublishTarget


class PublishDispatchStateError(ValueError):
    """Raised when a publish job is not safe to dispatch."""


@dataclass(frozen=True, slots=True)
class PublishDispatchResult:
    """Persisted job state after a successful queue handoff."""

    job: PublishJob


class DispatchPublishJobUseCase:
    """Commit publishing state and its minimal task event atomically."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, job_id: UUID) -> PublishDispatchResult:
        async with self._uow_factory() as uow:
            job = await uow.publish_jobs.get(job_id)
            if job is None:
                raise PublishJobNotFoundError("publish job not found")
            targets = await uow.publish_targets.list_for_job(job_id)
            self._validate(job, targets)
            updated_job = replace(job.transition(PublishJobStatus.PUBLISHING), status_reason=None)
            await uow.publish_jobs.update(updated_job)
            await uow.outbox_events.add(
                OutboxEvent(
                    id=uuid4(),
                    aggregate_id=updated_job.id,
                    event_type="publish.dispatch",
                    payload={
                        "job_id": str(updated_job.id),
                        "correlation_id": str(updated_job.correlation_id),
                        "idempotency_key": updated_job.idempotency_key,
                    },
                    correlation_id=updated_job.correlation_id,
                )
            )
            await uow.commit()

        return PublishDispatchResult(updated_job)

    @staticmethod
    def _validate(job: PublishJob, targets: tuple[PublishTarget, ...]) -> None:
        if job.status is not PublishJobStatus.AWAITING_CONFIRMATION:
            raise PublishDispatchStateError(
                f"job must await confirmation before dispatch: {job.status.value}"
            )
        if job.client_confirmation is not True:
            raise PublishDispatchStateError("explicit operator confirmation is required")

        selected_targets = [target for target in targets if target.selected]
        if not selected_targets:
            raise PublishDispatchStateError("at least one selected target is required")
        allowed_statuses = {CheckStatus.PASS.value, CheckStatus.WARNING.value}
        if any(target.preflight_status not in allowed_statuses for target in selected_targets):
            raise PublishDispatchStateError("all selected targets require passing preflight")
