from uuid import UUID, uuid4

import pytest

from application.publish_dispatch import DispatchPublishJobUseCase, PublishDispatchStateError
from domain.publish import PublishJob, PublishJobStatus, PublishTarget


class Store:
    def __init__(self, job: PublishJob, target: PublishTarget) -> None:
        self.job = job
        self.targets = [target]
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


class FakeUow:
    def __init__(self, store: Store) -> None:
        self.publish_jobs = FakeJobs(store)
        self.publish_targets = FakeTargets(store)
        self._store = store

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        self._store.closed = True

    async def commit(self) -> None:
        return None


class FakeQueue:
    def __init__(self, store: Store) -> None:
        self._store = store
        self.calls: list[tuple[UUID, UUID, str]] = []

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        assert self._store.closed is True
        self.calls.append((job_id, correlation_id, idempotency_key))


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
        game_name="game",
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
    queue = FakeQueue(store)

    result = await DispatchPublishJobUseCase(store.factory, queue).execute(job_id=store.job.id)

    assert result.job.status is PublishJobStatus.PUBLISHING
    assert queue.calls == [(store.job.id, store.job.correlation_id, "dispatch-key")]


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
    queue = FakeQueue(store)

    with pytest.raises(PublishDispatchStateError, match=message):
        await DispatchPublishJobUseCase(store.factory, queue).execute(job_id=store.job.id)

    assert queue.calls == []
