from uuid import UUID, uuid4

import pytest

from application.publish_commands import PublishJobNotFoundError
from application.publish_queries import GetPublishJobUseCase
from domain.publish import PublishJob, PublishTarget


class FakePublishJobs:
    def __init__(self, job: PublishJob | None) -> None:
        self.job = job

    async def get(self, job_id: UUID) -> PublishJob | None:
        if self.job is None or self.job.id != job_id:
            return None
        return self.job


class FakePublishTargets:
    def __init__(self, targets: tuple[PublishTarget, ...]) -> None:
        self.targets = targets

    async def list_for_job(self, job_id: UUID) -> tuple[PublishTarget, ...]:
        return tuple(target for target in self.targets if target.job_id == job_id)


class FakeUow:
    def __init__(self, job: PublishJob | None, targets: tuple[PublishTarget, ...]) -> None:
        self.publish_jobs = FakePublishJobs(job)
        self.publish_targets = FakePublishTargets(targets)

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None


def make_job() -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key="query-key",
        correlation_id=uuid4(),
        label="build",
        game_name="game",
    )


async def test_get_publish_job_loads_dynamic_targets() -> None:
    job = make_job()
    target = PublishTarget(id=uuid4(), job_id=job.id, station_id=uuid4(), progress_percent=25)
    use_case = GetPublishJobUseCase(lambda: FakeUow(job, (target,)))

    view = await use_case.execute(job.id)

    assert view.job == job
    assert view.targets == (target,)


async def test_get_publish_job_rejects_unknown_id() -> None:
    job = make_job()
    use_case = GetPublishJobUseCase(lambda: FakeUow(job, ()))

    with pytest.raises(PublishJobNotFoundError, match="publish job not found"):
        await use_case.execute(uuid4())
