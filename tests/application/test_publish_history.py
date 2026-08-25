from datetime import UTC, datetime
from uuid import uuid4

import pytest

from application.publish_queries import ListPublishJobsUseCase
from domain.publish import PublishJobHistory, PublishJobStatus


class FakeJobs:
    def __init__(self, jobs: tuple[PublishJobHistory, ...]) -> None:
        self.jobs = jobs
        self.limit: int | None = None

    async def list_recent(self, *, limit: int) -> tuple[PublishJobHistory, ...]:
        self.limit = limit
        return self.jobs[:limit]


class FakeUow:
    def __init__(self, jobs: FakeJobs) -> None:
        self.publish_jobs = jobs

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None


@pytest.mark.asyncio
async def test_history_query_bounds_limit_and_keeps_reason() -> None:
    job = PublishJobHistory(
        id=uuid4(),
        label="build-001",
        source_dataset="games/master-games",
        status=PublishJobStatus.COMPLETED,
        status_reason="dry_run_simulation",
        dry_run=True,
        created_at=datetime.now(UTC),
        completed_at=None,
    )
    jobs = FakeJobs((job,))

    result = await ListPublishJobsUseCase(lambda: FakeUow(jobs)).execute(limit=1000)

    assert result == (job,)
    assert jobs.limit == 100
