from uuid import UUID, uuid4

import pytest

from application.publish_dispatch import DispatchPublishJobUseCase, PublishDispatchStateError
from domain.publish import PublishJob, PublishJobStatus, PublishTarget


class Store:
    def __init__(self, job: PublishJob, target: PublishTarget) -> None:
        self.job = job
        self.targets = [target]
        self.events = []
        self.closed = False

    def factory(self) -> "FakeUow":
        self.closed = False
        return FakeUow(self)


class FakeJobs:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def get(self, job_id: UUID) -> PublishJob | None:
        return self._store.job if self._store.job.id == job_id else None

    async def update(self, job: PublishJob) -> None:
        self._store.job = job


class FakeTargets:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def list_for_job(self, job_id: UUID) -> tuple[PublishTarget, ...]:
        return tuple(target for target in self._store.targets if target.job_id == job_id)


class FakeOutbox:
    def __init__(self, store: Store) -> None:
        self._store = store

    async def add(self, event) -> None:
        self._store.events.append(event)


class FakeUow:
    def __init__(self, store: Store) -> None:
        self.publish_jobs = FakeJobs(store)
        self.publish_targets = FakeTargets(store)
        self.outbox_events = FakeOutbox(store)
        self._store = store

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        self._store.closed = True

    async def commit(self) -> None:
        return None


def make_store(
    *,
    status: PublishJobStatus = PublishJobStatus.AWAITING_CONFIRMATION,
    confirmation: bool | None = True,
    preflight_status: str | None = "pass",
) -> Store:
    job = PublishJob(
        id=uuid4(),
        idempotency_key="dispatch-key",
        correlation_id=uuid4(),
        label="build",
        source_dataset="game",
        status=status,
        client_confirmation=confirmation,
    )
    target = PublishTarget(
        id=uuid4(),
        job_id=job.id,
        station_id=uuid4(),
        preflight_status=preflight_status,
    )
    return Store(job, target)


async def test_dispatch_commits_publishing_before_queue_call() -> None:
    store = make_store()

    result = await DispatchPublishJobUseCase(store.factory).execute(job_id=store.job.id)

    assert result.job.status is PublishJobStatus.PUBLISHING
    assert store.closed is True
    assert len(store.events) == 1
    assert store.events[0].event_type == "publish.dispatch"
    assert store.events[0].payload == {
        "job_id": str(store.job.id),
        "correlation_id": str(store.job.correlation_id),
        "idempotency_key": "dispatch-key",
    }


@pytest.mark.parametrize(
    ("status", "confirmation", "preflight_status", "message"),
    [
        (
            PublishJobStatus.PREFLIGHT,
            True,
            "pass",
            "must await confirmation",
        ),
        (
            PublishJobStatus.AWAITING_CONFIRMATION,
            False,
            "pass",
            "explicit operator confirmation",
        ),
        (
            PublishJobStatus.AWAITING_CONFIRMATION,
            True,
            "unknown",
            "passing preflight",
        ),
    ],
)
async def test_dispatch_rejects_unsafe_job(
    status: PublishJobStatus,
    confirmation: bool | None,
    preflight_status: str | None,
    message: str,
) -> None:
    store = make_store(
        status=status,
        confirmation=confirmation,
        preflight_status=preflight_status,
    )

    with pytest.raises(PublishDispatchStateError, match=message):
        await DispatchPublishJobUseCase(store.factory).execute(job_id=store.job.id)

    assert store.events == []
