"""Fake worker executor that persists deterministic workflow outcomes."""

from collections.abc import Callable
from dataclasses import replace
from uuid import UUID

from application.ports import (
    PublishStorageAdapter,
    TrueNASReadOnlyClient,
    TrueNASWriteClient,
    UnitOfWorkFactory,
)
from application.publish import FakePublishWorkflow, PublishWorkflowResult
from application.truenas_publish import TrueNASPublishWorkflow
from domain.publish import PublishJob, PublishTarget, TargetStatus
from domain.station import Station


class PublishExecutorStateError(ValueError):
    """Raised when loaded worker state cannot be persisted safely."""


PublishStorageAdapterFactory = Callable[[], PublishStorageAdapter]
TrueNASReadClientFactory = Callable[[], TrueNASReadOnlyClient]
TrueNASWriteClientFactory = Callable[[], TrueNASWriteClient]


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
        await _persist_result(self._uow_factory, job, targets, result)


class TrueNASPublishTaskExecutor:
    """Run the real TrueNAS workflow after reloading station mappings."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        read_client_factory: TrueNASReadClientFactory,
        write_client_factory: TrueNASWriteClientFactory,
    ) -> None:
        self._uow_factory = uow_factory
        self._read_client_factory = read_client_factory
        self._write_client_factory = write_client_factory

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
        stations = await _load_stations(self._uow_factory, selected_targets)
        read_client = self._read_client_factory()
        write_client = self._write_client_factory()
        try:
            result = await TrueNASPublishWorkflow(read_client, write_client).execute(
                job,
                stations,
                confirmed=job.client_confirmation is True,
            )
        finally:
            await read_client.close()
            await write_client.close()
        await _persist_result(self._uow_factory, job, targets, result)


async def _load_stations(
    uow_factory: UnitOfWorkFactory,
    targets: tuple[PublishTarget, ...],
) -> tuple[Station, ...]:
    async with uow_factory() as uow:
        stations: list[Station] = []
        for target in targets:
            station = await uow.stations.get(target.station_id)
            if station is None:
                raise PublishExecutorStateError(f"station not found: {target.station_id}")
            stations.append(station)
    return tuple(stations)


async def _persist_result(
    uow_factory: UnitOfWorkFactory,
    original_job: PublishJob,
    original_targets: tuple[PublishTarget, ...],
    result: PublishWorkflowResult,
) -> None:
    targets_by_station = {target.station_id: target for target in original_targets}
    async with uow_factory() as uow:
        current_job = await uow.publish_jobs.get(original_job.id)
        if current_job is None:
            raise PublishExecutorStateError("publish job not found while persisting result")
        current_targets = await uow.publish_targets.list_for_job(original_job.id)
        current_by_station = {target.station_id: target for target in current_targets}
        if set(current_by_station) != set(targets_by_station):
            raise PublishExecutorStateError("publish target set changed while worker was running")

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
