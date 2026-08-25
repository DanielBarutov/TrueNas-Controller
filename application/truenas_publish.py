"""Application workflow for publishing a full dataset through TrueNAS iSCSI."""

from dataclasses import dataclass, replace
import re
from uuid import UUID

from application.ports import TrueNASReadOnlyClient, TrueNASWriteClient
from application.publish import PublishPreconditionError, PublishWorkflowResult
from application.truenas import TrueNASDataset
from domain.publish import PublishJob, PublishJobStatus, PublishTargetResult, TargetStatus
from domain.station import Station


class TrueNASPublishError(RuntimeError):
    """The TrueNAS state cannot be safely matched to the station registry."""


@dataclass(frozen=True, slots=True)
class ExistingExtentMapping:
    """Read-only identity of the existing target/extent association."""

    station_id: UUID
    target_id: int
    extent_id: int
    lun_id: int
    old_device: str | None


@dataclass(frozen=True, slots=True)
class _StationPlan:
    station: Station
    mapping: ExistingExtentMapping
    destination_dataset: str
    destination_device: str


class TrueNASPublishWorkflow:
    """Create clones and update only the device/file of existing extents."""

    def __init__(
        self,
        read_client: TrueNASReadOnlyClient,
        write_client: TrueNASWriteClient,
    ) -> None:
        self._read_client = read_client
        self._write_client = write_client

    async def execute(
        self,
        job: PublishJob,
        stations: tuple[Station, ...],
        *,
        confirmed: bool,
    ) -> PublishWorkflowResult:
        if not stations:
            raise PublishPreconditionError("at least one station is required")
        if not confirmed:
            raise PublishPreconditionError("explicit confirmation is required")
        if len({station.station_id for station in stations}) != len(stations):
            raise PublishPreconditionError("station selection must be unique")

        current = _enter_publishing(job)
        source = await self._find_source_dataset(job.source_dataset)
        mappings = await self._resolve_mappings(stations)
        plans = tuple(
            _build_station_plan(job, station, mappings[station.station_id]) for station in stations
        )

        if job.dry_run:
            return PublishWorkflowResult(
                replace_job_status(current, PublishJobStatus.COMPLETED, "dry_run_simulation"),
                master_mapping=f"dry-run:{job.source_dataset}",
                targets=tuple(
                    PublishTargetResult(
                        station_id=plan.station.station_id,
                        status=TargetStatus.SIMULATED,
                        old_mapping=plan.mapping.old_device,
                        new_mapping=plan.destination_device,
                    )
                    for plan in plans
                ),
            )

        snapshot_ref = await self._ensure_snapshot(job, source.name)
        current = current.transition(PublishJobStatus.SWITCHING)
        results: list[PublishTargetResult] = []
        for plan in plans:
            results.append(await self._apply_station(snapshot_ref, plan))

        current = current.transition(PublishJobStatus.VERIFYING)
        verified_count = sum(item.status is TargetStatus.VERIFIED for item in results)
        if verified_count == len(results):
            current = current.transition(PublishJobStatus.COMPLETED)
        elif verified_count == 0:
            current = current.transition(PublishJobStatus.FAILED)
        else:
            current = current.transition(PublishJobStatus.PARTIAL_FAILURE)
        return PublishWorkflowResult(current, snapshot_ref, tuple(results))

    async def _find_source_dataset(self, source_dataset: str) -> TrueNASDataset:
        datasets = await self._read_client.query_datasets()
        source = next(
            (item for item in datasets if item.name == source_dataset or item.id == source_dataset),
            None,
        )
        if source is None:
            raise TrueNASPublishError(f"source dataset is not found: {source_dataset}")
        return source

    async def _resolve_mappings(
        self,
        stations: tuple[Station, ...],
    ) -> dict[UUID, ExistingExtentMapping]:
        targets = await self._read_client.query_targets()
        associations = await self._read_client.query_target_extents()
        extents = {item.id: item for item in await self._read_client.query_extents()}
        mappings: dict[UUID, ExistingExtentMapping] = {}
        for station in stations:
            target_name = station.target_name
            if not target_name:
                raise TrueNASPublishError(
                    f"station {station.station_id} has no TrueNAS target_name mapping"
                )
            target = next((item for item in targets if item.name == target_name), None)
            if target is None:
                raise TrueNASPublishError(
                    f"TrueNAS target {target_name!r} was not found for station {station.station_id}"
                )
            target_associations = [item for item in associations if item.target_id == target.id]
            if len(target_associations) != 1:
                raise TrueNASPublishError(
                    f"target {target.name!r} must have exactly one extent association"
                )
            association = target_associations[0]
            extent = extents.get(association.extent_id)
            if extent is None:
                raise TrueNASPublishError(
                    f"extent {association.extent_id} for target {target.name!r} was not found"
                )
            mappings[station.station_id] = ExistingExtentMapping(
                station_id=station.station_id,
                target_id=target.id,
                extent_id=extent.id,
                lun_id=association.lun_id,
                old_device=extent.path,
            )
        return mappings

    async def _ensure_snapshot(self, job: PublishJob, source_dataset: str) -> str:
        snapshot_name = f"tnas-controller-{job.id.hex[:16]}"
        full_name = f"{source_dataset}@{snapshot_name}"
        snapshots = await self._read_client.query_snapshots()
        existing = next(
            (
                item
                for item in snapshots
                if item.name == full_name and item.dataset == source_dataset
            ),
            None,
        )
        if existing is not None:
            return existing.name
        created = await self._write_client.create_snapshot(source_dataset, snapshot_name)
        if created.dataset != source_dataset or created.name != full_name:
            raise TrueNASPublishError("TrueNAS returned an unexpected snapshot identity")
        return created.name

    async def _apply_station(
        self,
        snapshot_ref: str,
        plan: _StationPlan,
    ) -> PublishTargetResult:
        write_attempted = False
        try:
            datasets = await self._read_client.query_datasets()
            if not any(item.name == plan.destination_dataset for item in datasets):
                await self._write_client.clone_snapshot(snapshot_ref, plan.destination_dataset)
            if plan.mapping.old_device != plan.destination_device:
                write_attempted = True
                await self._write_client.update_extent_device(
                    plan.mapping.extent_id,
                    plan.destination_device,
                )
            await self._verify_read_back(plan)
        except Exception as error:
            if write_attempted:
                try:
                    await self._verify_read_back(plan)
                except Exception:
                    return PublishTargetResult(
                        plan.station.station_id,
                        TargetStatus.RECOVERY_REQUIRED,
                        plan.mapping.old_device,
                        new_mapping=plan.destination_device,
                        error_code="extent_update_unknown",
                        error_message=(
                            "extent update outcome is unknown; read-back did not confirm it"
                        ),
                    )
                return PublishTargetResult(
                    plan.station.station_id,
                    TargetStatus.VERIFIED,
                    plan.mapping.old_device,
                    new_mapping=plan.destination_device,
                )
            return PublishTargetResult(
                plan.station.station_id,
                TargetStatus.ERROR,
                plan.mapping.old_device,
                new_mapping=plan.destination_device,
                error_code="target_failed",
                error_message=str(error),
            )
        return PublishTargetResult(
            plan.station.station_id,
            TargetStatus.VERIFIED,
            plan.mapping.old_device,
            new_mapping=plan.destination_device,
        )

    async def _verify_read_back(self, plan: _StationPlan) -> None:
        associations = await self._read_client.query_target_extents()
        matching = [
            item
            for item in associations
            if item.target_id == plan.mapping.target_id
            and item.extent_id == plan.mapping.extent_id
            and item.lun_id == plan.mapping.lun_id
        ]
        if len(matching) != 1:
            raise TrueNASPublishError(
                f"target/extent/LUN association changed for station {plan.station.station_id}"
            )
        extents = await self._read_client.query_extents()
        extent = next((item for item in extents if item.id == plan.mapping.extent_id), None)
        if extent is None or extent.path != plan.destination_device:
            raise TrueNASPublishError(
                f"extent {plan.mapping.extent_id} read-back device does not match clone"
            )


def _enter_publishing(job: PublishJob) -> PublishJob:
    if job.status is PublishJobStatus.DRAFT:
        current = job.transition(PublishJobStatus.PREFLIGHT)
        current = current.transition(PublishJobStatus.AWAITING_CONFIRMATION)
        return current.transition(PublishJobStatus.PUBLISHING)
    if job.status is PublishJobStatus.PUBLISHING:
        return job
    raise PublishPreconditionError("job must be draft or publishing")


def replace_job_status(job: PublishJob, status: PublishJobStatus, reason: str) -> PublishJob:
    return replace(job.transition(status), status_reason=reason)


def _build_station_plan(
    job: PublishJob,
    station: Station,
    mapping: ExistingExtentMapping,
) -> _StationPlan:
    suffix = _safe_slug(station.display_name)
    destination_dataset = f"{job.source_dataset}-{suffix}-{job.id.hex[:12]}"
    return _StationPlan(
        station=station,
        mapping=mapping,
        destination_dataset=destination_dataset,
        destination_device=f"/dev/zvol/{destination_dataset}",
    )


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return (slug or "station")[:48]
