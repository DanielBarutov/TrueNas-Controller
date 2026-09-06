from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.datasets import (
    DatasetSelectionError,
    ListDatasetsUseCase,
    QueueDatasetCleanupUseCase,
)
from application.truenas import TrueNASExtent, TrueNASTarget, TrueNASTargetExtent
from domain.publish import PublishArtifact, StorageArtifactStatus
from domain.station import Station, StationRole, StationStatus


class FakeArtifacts:
    def __init__(self, artifacts: tuple[PublishArtifact, ...]) -> None:
        self.artifacts = artifacts

    async def list_all(self, *, include_deleted: bool = False):
        if include_deleted:
            return self.artifacts
        return tuple(artifact for artifact in self.artifacts if artifact.deleted_at is None)

    async def list_by_ids(self, artifact_ids):
        return tuple(artifact for artifact in self.artifacts if artifact.id in artifact_ids)

    async def set_current_artifact(self, station_id, artifact_id):
        return None


class FakeStations:
    def __init__(self, stations: tuple[Station, ...]) -> None:
        self.stations = stations

    async def list(self, *, include_disabled: bool = False):
        return list(self.stations)

    async def get(self, station_id):
        return next(
            (station for station in self.stations if station.station_id == station_id),
            None,
        )


class FakeUow:
    def __init__(
        self,
        artifacts: tuple[PublishArtifact, ...],
        stations: tuple[Station, ...] = (),
    ) -> None:
        self.publish_artifacts = FakeArtifacts(artifacts)
        self.stations = FakeStations(stations)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def commit(self):
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def enqueue(self, *, artifact_ids):
        self.calls.append(artifact_ids)


def make_artifact(
    *,
    station_id=None,
    current: bool = False,
    deleted: bool = False,
) -> PublishArtifact:
    dataset_name = f"games/clone-{uuid4().hex[:8]}"
    return PublishArtifact(
        id=uuid4(),
        job_id=uuid4(),
        station_id=station_id or uuid4(),
        source_dataset="games/master-games",
        dataset_name=dataset_name,
        snapshot_ref="games/master-games@snapshot",
        mapping_ref=f"zvol/{dataset_name}",
        created_at=datetime.now(UTC),
        status=StorageArtifactStatus.DELETED
        if deleted
        else (StorageArtifactStatus.CURRENT if current else StorageArtifactStatus.RETIRED),
        is_current=current,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


@pytest.mark.asyncio
async def test_list_datasets_hides_deleted_records_by_default() -> None:
    active, deleted = make_artifact(), make_artifact(deleted=True)
    use_case = ListDatasetsUseCase(lambda: FakeUow((active, deleted)))

    assert await use_case.execute() == (active,)
    assert await use_case.execute(include_deleted=True) == (active, deleted)


@pytest.mark.asyncio
async def test_queue_dataset_cleanup_deduplicates_and_sends_ids_to_worker() -> None:
    artifact = make_artifact()
    queue = FakeQueue()
    use_case = QueueDatasetCleanupUseCase(
        lambda: FakeUow((artifact,)),
        queue,
    )

    result = await use_case.execute(artifact_ids=(artifact.id, artifact.id))

    assert result.artifact_ids == (artifact.id,)
    assert queue.calls == [(artifact.id,)]


@pytest.mark.asyncio
async def test_queue_dataset_cleanup_rejects_current_dataset() -> None:
    artifact = make_artifact(current=True)
    use_case = QueueDatasetCleanupUseCase(lambda: FakeUow((artifact,)), FakeQueue())

    with pytest.raises(DatasetSelectionError, match="currently used"):
        await use_case.execute(artifact_ids=(artifact.id,))


class FakeTrueNASReadClient:
    def __init__(self, path: str) -> None:
        self.path = path
        self.closed = False

    async def query_targets(self):
        return (TrueNASTarget(id=1, name="iscsi/pc01", alias=None),)

    async def query_target_extents(self):
        return (TrueNASTargetExtent(target_id=1, extent_id=10, lun_id=0),)

    async def query_extents(self):
        return (TrueNASExtent(id=10, name="extent-pc01", path=self.path, extent_type="DISK"),)

    async def close(self):
        self.closed = True


def make_station_for_live_mapping() -> Station:
    return Station(
        id=uuid4(),
        station_id=uuid4(),
        display_name="Client 01",
        hostname="client-01",
        role=StationRole.CLIENT,
        status=StationStatus.ONLINE,
        target_name="iscsi/pc01",
    )


@pytest.mark.asyncio
async def test_list_datasets_uses_live_truenas_mapping_for_current_status() -> None:
    station = make_station_for_live_mapping()
    artifact = make_artifact(station_id=station.station_id)
    client = FakeTrueNASReadClient(f"/dev/{artifact.mapping_ref}")
    use_case = ListDatasetsUseCase(
        lambda: FakeUow((artifact,), (station,)),
        lambda: client,
    )

    result = await use_case.execute()

    assert result[0].is_current is True
    assert result[0].status is StorageArtifactStatus.CURRENT
    assert client.closed is True


@pytest.mark.asyncio
async def test_list_datasets_switches_current_version_after_manual_truenas_change() -> None:
    station = make_station_for_live_mapping()
    old_artifact = make_artifact(station_id=station.station_id, current=True)
    new_artifact = make_artifact(station_id=station.station_id)
    client = FakeTrueNASReadClient(new_artifact.mapping_ref)
    use_case = ListDatasetsUseCase(
        lambda: FakeUow((old_artifact, new_artifact), (station,)),
        lambda: client,
    )

    result = await use_case.execute()

    by_id = {artifact.id: artifact for artifact in result}
    assert by_id[old_artifact.id].is_current is False
    assert by_id[old_artifact.id].status is StorageArtifactStatus.RETIRED
    assert by_id[new_artifact.id].is_current is True
    assert by_id[new_artifact.id].status is StorageArtifactStatus.CURRENT


@pytest.mark.asyncio
async def test_queue_cleanup_rechecks_live_truenas_mapping_before_enqueue() -> None:
    station = make_station_for_live_mapping()
    artifact = make_artifact(station_id=station.station_id)
    client = FakeTrueNASReadClient(artifact.mapping_ref)
    queue = FakeQueue()
    use_case = QueueDatasetCleanupUseCase(
        lambda: FakeUow((artifact,), (station,)),
        queue,
        lambda: client,
    )

    with pytest.raises(DatasetSelectionError, match="currently used"):
        await use_case.execute(artifact_ids=(artifact.id,))

    assert queue.calls == []


@pytest.mark.asyncio
async def test_queue_cleanup_rejects_untracked_live_truenas_mapping() -> None:
    station = make_station_for_live_mapping()
    artifact = make_artifact(station_id=station.station_id, current=True)
    client = FakeTrueNASReadClient("zvol/games/manual-image")
    queue = FakeQueue()
    use_case = QueueDatasetCleanupUseCase(
        lambda: FakeUow((artifact,), (station,)),
        queue,
        lambda: client,
    )

    with pytest.raises(DatasetSelectionError, match="not verified"):
        await use_case.execute(artifact_ids=(artifact.id,))

    assert queue.calls == []
