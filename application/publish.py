"""Application fake publish workflow over a storage adapter Protocol."""

from dataclasses import dataclass
from uuid import UUID

from application.ports import PublishStorageAdapter
from domain.publish import PublishJob, PublishJobStatus, PublishTargetResult, TargetStatus


class PublishPreconditionError(ValueError):
    """Raised before any storage operation when the job cannot run."""


class UnknownStorageOutcome(RuntimeError):
    """Raised when a switch request may have reached storage."""


@dataclass(frozen=True, slots=True)
class PublishWorkflowResult:
    """Final fake workflow result and per-target outcomes."""

    job: PublishJob
    master_mapping: str | None
    targets: tuple[PublishTargetResult, ...]


class FakePublishWorkflow:
    """Run safe fake master/clone/switch/verify stages."""

    def __init__(self, adapter: PublishStorageAdapter) -> None:
        self._adapter = adapter

    async def execute(
        self,
        job: PublishJob,
        station_ids: tuple[UUID, ...],
        *,
        confirmed: bool,
    ) -> PublishWorkflowResult:
        if not station_ids:
            raise PublishPreconditionError("at least one station is required")
        if not confirmed:
            raise PublishPreconditionError("explicit confirmation is required")
        if job.status is PublishJobStatus.DRAFT:
            current = job.transition(PublishJobStatus.PREFLIGHT)
            current = current.transition(PublishJobStatus.AWAITING_CONFIRMATION)
            current = current.transition(PublishJobStatus.PUBLISHING)
        elif job.status is PublishJobStatus.PUBLISHING:
            current = job
        else:
            raise PublishPreconditionError("job must be draft or publishing")
        master_mapping = f"master:{job.id}"
        if not job.dry_run:
            master_mapping = await self._adapter.create_master(job.id, job.label)

        if job.dry_run:
            simulated_targets = []
            for station_id in station_ids:
                simulated_targets.append(
                    PublishTargetResult(
                        station_id=station_id,
                        status=TargetStatus.SIMULATED,
                        old_mapping=await self._adapter.read_mapping(station_id),
                        new_mapping=f"clone:{job.id}:{station_id}",
                    )
                )
            targets = tuple(simulated_targets)
            return PublishWorkflowResult(current, master_mapping, targets)

        current = current.transition(PublishJobStatus.SWITCHING)
        results_by_station: dict[UUID, PublishTargetResult] = {}
        pending_verification: list[tuple[UUID, str | None, str]] = []
        for station_id in station_ids:
            old_mapping = await self._adapter.read_mapping(station_id)
            try:
                clone_mapping = await self._adapter.create_clone(master_mapping, station_id)
                await self._adapter.switch_mapping(station_id, clone_mapping)
                pending_verification.append((station_id, old_mapping, clone_mapping))
            except UnknownStorageOutcome:
                read_back = await self._adapter.read_mapping(station_id)
                if read_back == clone_mapping:
                    results_by_station[station_id] = PublishTargetResult(
                        station_id,
                        TargetStatus.VERIFIED,
                        old_mapping,
                        new_mapping=read_back,
                    )
                else:
                    results_by_station[station_id] = PublishTargetResult(
                        station_id,
                        TargetStatus.RECOVERY_REQUIRED,
                        old_mapping,
                        error_code="switch_unknown",
                        error_message="switch outcome requires manual recovery",
                    )
            except Exception as error:
                results_by_station[station_id] = PublishTargetResult(
                    station_id,
                    TargetStatus.ERROR,
                    old_mapping,
                    error_code="target_failed",
                    error_message=str(error),
                )

        current = current.transition(PublishJobStatus.VERIFYING)
        for station_id, old_mapping, clone_mapping in pending_verification:
            try:
                verified = await self._adapter.verify_mapping(station_id, clone_mapping)
                if not verified:
                    raise ValueError("mapping verification failed")
                results_by_station[station_id] = PublishTargetResult(
                    station_id,
                    TargetStatus.VERIFIED,
                    old_mapping,
                    new_mapping=clone_mapping,
                )
            except Exception as error:
                results_by_station[station_id] = PublishTargetResult(
                    station_id,
                    TargetStatus.ERROR,
                    old_mapping,
                    new_mapping=clone_mapping,
                    error_code="verify_failed",
                    error_message=str(error),
                )

        results = [results_by_station[station_id] for station_id in station_ids]
        verified_count = sum(item.status is TargetStatus.VERIFIED for item in results)
        if verified_count == len(results):
            current = current.transition(PublishJobStatus.COMPLETED)
        elif verified_count == 0:
            current = current.transition(PublishJobStatus.FAILED)
        else:
            current = current.transition(PublishJobStatus.PARTIAL_FAILURE)
        return PublishWorkflowResult(current, master_mapping, tuple(results))
