from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.datasets import (
    DatasetSelectionError,
    ListDatasetsUseCase,
    QueueDatasetCleanupUseCase,
)
from domain.publish import PublishArtifact, StorageArtifactStatus


class FakeArtifacts:
    def __init__(self, artifacts: tuple[PublishArtifact, ...]) -> None:
        self.artifacts = artifacts

    async def list_all(self, *, include_deleted: bool = False):
        if include_deleted:
            return self.artifacts
        return tuple(artifact for artifact in self.artifacts if artifact.deleted_at is None)

    async def list_by_ids(self, artifact_ids):
        return tuple(artifact for artifact in self.artifacts if artifact.id in artifact_ids)


class FakeUow:
    def __init__(self, artifacts: tuple[PublishArtifact, ...]) -> None:
        self.publish_artifacts = FakeArtifacts(artifacts)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None


class FakeQueue:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def enqueue(self, *, artifact_ids):
        self.calls.append(artifact_ids)


def make_artifact(*, current: bool = False, deleted: bool = False) -> PublishArtifact:
    return PublishArtifact(
        id=uuid4(),
        job_id=uuid4(),
        station_id=uuid4(),
        source_dataset="games/master-games",
        dataset_name=f"games/clone-{uuid4().hex[:8]}",
        snapshot_ref="games/master-games@snapshot",
        mapping_ref="zvol/games/clone",
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
