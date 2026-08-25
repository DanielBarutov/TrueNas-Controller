from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from application.dataset_cleanup import DatasetCleanupUseCase
from domain.publish import PublishArtifact, StorageArtifactStatus


class FakeArtifacts:
    def __init__(self, artifacts: tuple[PublishArtifact, ...]) -> None:
        self.artifacts = list(artifacts)
        self.deleted: list[tuple[object, datetime]] = []
        self.failed: list[tuple[object, str]] = []

    async def list_cleanup_candidates(self, *, before, limit):
        return tuple(self.artifacts[:limit])

    async def mark_deleted(self, artifact_id, deleted_at):
        self.deleted.append((artifact_id, deleted_at))

    async def mark_cleanup_failed(self, artifact_id, error):
        self.failed.append((artifact_id, error))


class FakeUnitOfWork:
    def __init__(self, artifacts: FakeArtifacts) -> None:
        self.publish_artifacts = artifacts
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None

    async def commit(self):
        self.commits += 1


class FakeWriteClient:
    def __init__(self, failing: bool = False) -> None:
        self.failing = failing
        self.deleted: list[str] = []

    async def delete_dataset(self, dataset: str) -> None:
        self.deleted.append(dataset)
        if self.failing:
            raise RuntimeError("remote delete failed")


def make_artifact() -> PublishArtifact:
    return PublishArtifact(
        id=uuid4(),
        job_id=uuid4(),
        station_id=uuid4(),
        source_dataset="games/master-games",
        dataset_name="games/master-games-pc1-job",
        snapshot_ref="games/master-games@snapshot",
        mapping_ref="zvol/games/master-games-pc1-job",
        created_at=datetime.now(UTC) - timedelta(days=31),
        status=StorageArtifactStatus.RETIRED,
    )


@pytest.mark.asyncio
async def test_cleanup_defaults_to_inventory_only_without_remote_delete() -> None:
    artifacts = FakeArtifacts((make_artifact(),))
    uow = FakeUnitOfWork(artifacts)
    client = FakeWriteClient()
    use_case = DatasetCleanupUseCase(
        lambda: uow,
        retention_days=30,
        batch_size=10,
        apply_enabled=False,
    )

    result = await use_case.execute(write_client=client, now=datetime.now(UTC))

    assert result.inspected == 1
    assert result.deleted == 0
    assert result.dry_run is True
    assert client.deleted == []
    assert artifacts.deleted == []


@pytest.mark.asyncio
async def test_cleanup_marks_remote_delete_and_database_state_atomically_per_item() -> None:
    artifact = make_artifact()
    artifacts = FakeArtifacts((artifact,))
    uow = FakeUnitOfWork(artifacts)
    client = FakeWriteClient()
    use_case = DatasetCleanupUseCase(
        lambda: uow,
        retention_days=30,
        batch_size=10,
        apply_enabled=True,
    )

    result = await use_case.execute(write_client=client, now=datetime.now(UTC))

    assert result.deleted == 1
    assert result.failed == 0
    assert client.deleted == [artifact.dataset_name]
    assert len(artifacts.deleted) == 1
    assert artifacts.deleted[0][0] == artifact.id
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_cleanup_persists_bounded_failure_for_retry() -> None:
    artifact = make_artifact()
    artifacts = FakeArtifacts((artifact,))
    uow = FakeUnitOfWork(artifacts)
    use_case = DatasetCleanupUseCase(
        lambda: uow,
        retention_days=30,
        batch_size=10,
        apply_enabled=True,
    )

    result = await use_case.execute(
        write_client=FakeWriteClient(failing=True),
        now=datetime.now(UTC),
    )

    assert result.deleted == 0
    assert result.failed == 1
    assert artifacts.failed == [(artifact.id, "remote delete failed")]
    assert uow.commits == 1
