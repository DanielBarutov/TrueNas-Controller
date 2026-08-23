"""Fake worker executor that persists deterministic workflow outcomes."""

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

from application.ports import PublishStorageAdapter, UnitOfWorkFactory
from application.publish import FakePublishWorkflow, PublishWorkflowResult
from domain.publish import PublishJob, PublishTarget, TargetStatus


class PublishExecutorStateError(ValueError):
    """Raised when loaded worker state cannot be persisted safely."""


PublishStorageAdapterFactory = Callable[[], PublishStorageAdapter]


class FakePublishTaskExecutor:
    """Execute fake storage workflow outside DB transaction, then persist results."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        adapter_factory: PublishStorageAdapterFactory,
    ) -> None:
        self._uow_factory = uow_factory
        self._adapter_factory = adapter_factory

    async def execute(
        self,
        job: PublishJob,
        targets: tuple[PublishTarget, ...],
        *,
        correlation_id: UUID,
    ) -> None:
        if job.correlation_id != correlation_id:
            raise PublishExecutorStateError("executor correlation ID does not match job")
        if job.status.value in {"completed", "partial_failure", "failed"}:
            return

        selected_targets = tuple(target for target in targets if target.selected)
        if not selected_targets:
            raise PublishExecutorStateError("at least one selected target is required")
        result = await FakePublishWorkflow(self._adapter_factory()).execute(
            job,
            tuple(target.station_id for target in selected_targets),
            confirmed=job.client_confirmation is True,
        )
        await self._persist_result(job, targets, result)

    async def _persist_result(
        self,
        original_job: PublishJob,
        original_targets: tuple[PublishTarget, ...],
        result: PublishWorkflowResult,
    ) -> None:
        targets_by_station = {target.station_id: target for target in original_targets}
        async with self._uow_factory() as uow:
            current_job = await uow.publish_jobs.get(original_job.id)
            if current_job is None:
                raise PublishExecutorStateError("publish job not found while persisting result")
            current_targets = await uow.publish_targets.list_for_job(original_job.id)
            current_by_station = {target.station_id: target for target in current_targets}
            if set(current_by_station) != set(targets_by_station):
                raise PublishExecutorStateError(
                    "publish target set changed while worker was running"
                )

            for target_result in result.targets:
                current_target = current_by_station[target_result.station_id]
                await uow.publish_targets.update(
                    replace(
                        current_target,
                        old_mapping=_mapping_payload(target_result.old_mapping),
                        new_mapping=_mapping_payload(target_result.new_mapping),
                        switch_status=_switch_status(target_result.status),
                        verify_status=_verify_status(target_result.status),
                        error_code=target_result.error_code,
                        error_message=target_result.error_message,
                        progress_percent=100,
                    )
                )
            await uow.publish_jobs.update(result.job)
            await uow.commit()


def _mapping_payload(mapping: str | None) -> dict[str, object] | None:
    return None if mapping is None else {"ref": mapping}


def _switch_status(status: TargetStatus) -> str:
    if status is TargetStatus.SIMULATED:
        return "simulated"
    if status is TargetStatus.VERIFIED:
        return "switched"
    return status.value


def _verify_status(status: TargetStatus) -> str:
    if status is TargetStatus.SIMULATED:
        return "simulated"
    if status is TargetStatus.VERIFIED:
        return "verified"
    return status.value
