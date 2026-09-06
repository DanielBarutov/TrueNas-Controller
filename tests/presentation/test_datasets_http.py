from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from application.datasets import ListDatasetsUseCase, QueueDatasetCleanupUseCase
from domain.publish import PublishArtifact, StorageArtifactStatus
from presentation.http import create_app

TEST_PASSWORD = "test-password"


class FakeStationQuery:
    async def execute(self, *, include_disabled: bool = False):
        return []


class FakeArtifacts:
    def __init__(self, artifacts):
        self.artifacts = tuple(artifacts)

    async def list_all(self, *, include_deleted=False):
        return tuple(
            artifact
            for artifact in self.artifacts
            if include_deleted or artifact.deleted_at is None
        )

    async def list_by_ids(self, artifact_ids):
        return tuple(artifact for artifact in self.artifacts if artifact.id in artifact_ids)


class FakeUow:
    def __init__(self, artifacts):
        self.publish_artifacts = FakeArtifacts(artifacts)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return None


class FakeQueue:
    def __init__(self):
        self.calls = []

    def enqueue(self, *, artifact_ids):
        self.calls.append(artifact_ids)


def make_artifact(*, current=False):
    return PublishArtifact(
        id=uuid4(),
        job_id=uuid4(),
        station_id=uuid4(),
        source_dataset="games/master-games",
        dataset_name="games/clone-pc1",
        snapshot_ref="games/master-games@snapshot",
        mapping_ref="zvol/games/clone-pc1",
        created_at=datetime.now(UTC),
        status=StorageArtifactStatus.CURRENT if current else StorageArtifactStatus.RETIRED,
        is_current=current,
    )


def make_client(artifacts, queue):
    return TestClient(
        create_app(
            FakeStationQuery(),
            list_datasets=ListDatasetsUseCase(lambda: FakeUow(artifacts)),
            queue_dataset_cleanup=QueueDatasetCleanupUseCase(lambda: FakeUow(artifacts), queue),
        )
    )


def test_dataset_routes_list_inventory_and_queue_selected_ids(monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    artifact = make_artifact()
    queue = FakeQueue()
    client = make_client((artifact,), queue)

    response = client.get("/api/v1/datasets", auth=("admin", TEST_PASSWORD))
    assert response.status_code == 200
    assert response.json()[0]["dataset_name"] == artifact.dataset_name

    response = client.post(
        "/api/v1/datasets/delete",
        json={"artifact_ids": [str(artifact.id)]},
        auth=("admin", TEST_PASSWORD),
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted", "artifact_ids": [str(artifact.id)]}
    assert queue.calls == [(artifact.id,)]


def test_dataset_delete_route_rejects_current_artifact(monkeypatch):
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", TEST_PASSWORD)
    artifact = make_artifact(current=True)
    client = make_client((artifact,), FakeQueue())

    response = client.post(
        "/api/v1/datasets/delete",
        json={"artifact_ids": [str(artifact.id)]},
        auth=("admin", TEST_PASSWORD),
    )

    assert response.status_code == 422
