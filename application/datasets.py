"""Application use cases for the operator dataset inventory."""

from collections.abc import Callable
from dataclasses import dataclass, replace
from uuid import UUID

from application.ports import (
    DatasetCleanupTaskQueue,
    TrueNASReadOnlyClient,
    UnitOfWorkFactory,
)
from application.truenas import TrueNASExtent, TrueNASTarget, TrueNASTargetExtent
from domain.publish import PublishArtifact, StorageArtifactStatus
from domain.station import Station


class DatasetSelectionError(ValueError):
    """The operator selected an unknown or unsafe dataset record."""


class DatasetStorageSyncError(RuntimeError):
    """The current TrueNAS mapping could not be verified safely."""


TrueNASReadClientFactory = Callable[[], TrueNASReadOnlyClient]


@dataclass(frozen=True, slots=True)
class DatasetDeletionDispatch:
    """Minimal acknowledgement returned after a worker task is queued."""

    artifact_ids: tuple[UUID, ...]


class ListDatasetsUseCase:
    """Load tracked artifacts and reconcile their current state with TrueNAS."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        truenas_read_client_factory: TrueNASReadClientFactory | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._truenas_read_client_factory = truenas_read_client_factory

    async def execute(self, *, include_deleted: bool = False) -> tuple[PublishArtifact, ...]:
        async with self._uow_factory() as uow:
            artifacts = await uow.publish_artifacts.list_all(include_deleted=include_deleted)
            if self._truenas_read_client_factory is None:
                return artifacts
            stations = tuple(await uow.stations.list(include_disabled=True))

        live_mappings = await _read_live_mappings(
            self._truenas_read_client_factory,
            stations,
        )
        await _persist_current_state(self._uow_factory, artifacts, live_mappings)
        return _reconcile_artifacts(artifacts, live_mappings)


class QueueDatasetCleanupUseCase:
    """Validate selected tracked artifacts and hand deletion to the worker.

    The API only queues stable database IDs. TrueNAS credentials and the remote
    delete operation remain in the worker process. If a read-only TrueNAS
    client is configured, the selected records are checked against the live
    target-to-extent mapping before they enter the queue.
    """

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        queue: DatasetCleanupTaskQueue,
        truenas_read_client_factory: TrueNASReadClientFactory | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._queue = queue
        self._truenas_read_client_factory = truenas_read_client_factory

    async def execute(self, *, artifact_ids: tuple[UUID, ...]) -> DatasetDeletionDispatch:
        normalized_ids = tuple(dict.fromkeys(artifact_ids))
        if not normalized_ids:
            raise DatasetSelectionError("at least one dataset must be selected")

        async with self._uow_factory() as uow:
            selected = await uow.publish_artifacts.list_by_ids(normalized_ids)
            if self._truenas_read_client_factory is None:
                artifacts = selected
                stations = ()
            else:
                artifacts = await uow.publish_artifacts.list_all(include_deleted=True)
                stations_by_id: dict[UUID, Station] = {}
                for artifact in selected:
                    station = await uow.stations.get(artifact.station_id)
                    if station is not None:
                        stations_by_id[station.station_id] = station
                stations = tuple(stations_by_id.values())

        selected_by_id = {artifact.id: artifact for artifact in selected}
        missing = tuple(
            artifact_id for artifact_id in normalized_ids if artifact_id not in selected_by_id
        )
        if missing:
            raise DatasetSelectionError("one or more selected datasets were not found")

        if self._truenas_read_client_factory is not None:
            live_mappings = await _read_live_mappings(
                self._truenas_read_client_factory,
                stations,
            )
            await _persist_current_state(self._uow_factory, artifacts, live_mappings)
            selected_station_ids = {artifact.station_id for artifact in selected}
            unverified_station_ids = {
                station.station_id
                for station in stations
                if station.target_name and station.station_id not in live_mappings
            }
            untracked_station_ids = {
                station_id
                for station_id, live_mapping in live_mappings.items()
                if len(
                    [
                        artifact
                        for artifact in artifacts
                        if (
                            artifact.station_id == station_id
                            and artifact.deleted_at is None
                            and _artifact_matches_mapping(artifact, live_mapping)
                        )
                    ]
                )
                != 1
            }
            if selected_station_ids & (unverified_station_ids | untracked_station_ids):
                raise DatasetSelectionError(
                    "the current TrueNAS mapping is not verified as a unique tracked dataset"
                )
            selected = _reconcile_artifacts(selected, live_mappings)

        selected_by_id = {artifact.id: artifact for artifact in selected}
        if any(selected_by_id[artifact_id].is_current for artifact_id in normalized_ids):
            raise DatasetSelectionError("the dataset currently used by a station cannot be deleted")
        if any(
            selected_by_id[artifact_id].deleted_at is not None for artifact_id in normalized_ids
        ):
            raise DatasetSelectionError("one or more selected datasets were already deleted")

        self._queue.enqueue(artifact_ids=normalized_ids)
        return DatasetDeletionDispatch(normalized_ids)


async def _read_live_mappings(
    factory: TrueNASReadClientFactory,
    stations: tuple[Station, ...],
) -> dict[UUID, str]:
    client = factory()
    try:
        try:
            targets = await client.query_targets()
            associations = await client.query_target_extents()
            extents = await client.query_extents()
        except Exception as error:
            raise DatasetStorageSyncError(
                "TrueNAS current dataset mapping could not be verified"
            ) from error
    finally:
        await client.close()

    return _map_station_mappings(stations, targets, associations, extents)


def _map_station_mappings(
    stations: tuple[Station, ...],
    targets: tuple[TrueNASTarget, ...],
    associations: tuple[TrueNASTargetExtent, ...],
    extents: tuple[TrueNASExtent, ...],
) -> dict[UUID, str]:
    targets_by_name: dict[str, list[TrueNASTarget]] = {}
    for target in targets:
        targets_by_name.setdefault(target.name, []).append(target)
    extents_by_id = {extent.id: extent for extent in extents}
    live_mappings: dict[UUID, str] = {}
    for station in stations:
        if not station.target_name:
            continue
        matching_targets = targets_by_name.get(station.target_name, [])
        if len(matching_targets) != 1:
            continue
        target = matching_targets[0]
        target_associations = [item for item in associations if item.target_id == target.id]
        if len(target_associations) != 1:
            continue
        extent = extents_by_id.get(target_associations[0].extent_id)
        if extent is None or extent.path is None:
            continue
        live_mappings[station.station_id] = _canonical_mapping(extent.path)
    return live_mappings


async def _persist_current_state(
    uow_factory: UnitOfWorkFactory,
    artifacts: tuple[PublishArtifact, ...],
    live_mappings: dict[UUID, str],
) -> None:
    if not live_mappings:
        return
    async with uow_factory() as uow:
        for station_id, live_mapping in live_mappings.items():
            matches = [
                artifact
                for artifact in artifacts
                if (
                    artifact.station_id == station_id
                    and artifact.deleted_at is None
                    and _artifact_matches_mapping(artifact, live_mapping)
                )
            ]
            current_id = matches[0].id if len(matches) == 1 else None
            await uow.publish_artifacts.set_current_artifact(station_id, current_id)
        await uow.commit()


def _reconcile_artifacts(
    artifacts: tuple[PublishArtifact, ...],
    live_mappings: dict[UUID, str],
) -> tuple[PublishArtifact, ...]:
    current_ids: dict[UUID, UUID | None] = {}
    for station_id, live_mapping in live_mappings.items():
        matches = [
            artifact
            for artifact in artifacts
            if (
                artifact.station_id == station_id
                and artifact.deleted_at is None
                and _artifact_matches_mapping(artifact, live_mapping)
            )
        ]
        current_ids[station_id] = matches[0].id if len(matches) == 1 else None

    reconciled: list[PublishArtifact] = []
    for artifact in artifacts:
        expected_id = current_ids.get(artifact.station_id)
        if artifact.station_id not in current_ids or artifact.deleted_at is not None:
            reconciled.append(artifact)
        elif artifact.id == expected_id:
            reconciled.append(
                replace(
                    artifact,
                    status=StorageArtifactStatus.CURRENT,
                    is_current=True,
                    last_error=None,
                )
            )
        else:
            status = (
                StorageArtifactStatus.RETIRED
                if artifact.status is StorageArtifactStatus.CURRENT
                else artifact.status
            )
            reconciled.append(replace(artifact, status=status, is_current=False))
    return tuple(reconciled)


def _artifact_matches_mapping(artifact: PublishArtifact, live_mapping: str) -> bool:
    return live_mapping in {
        _canonical_mapping(artifact.mapping_ref),
        _canonical_mapping(f"zvol/{artifact.dataset_name}"),
    }


def _canonical_mapping(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("disk="):
        normalized = normalized.removeprefix("disk=")
    return normalized.removeprefix("/dev/")
