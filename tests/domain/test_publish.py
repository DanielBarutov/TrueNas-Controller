from uuid import uuid4

import pytest

from domain.publish import PublishJob, PublishJobStatus


def make_job() -> PublishJob:
    return PublishJob(
        id=uuid4(),
        idempotency_key="job-key",
        correlation_id=uuid4(),
        label="build-001",
        game_name="game",
    )


def test_publish_job_allows_explicit_stage_order() -> None:
    job = make_job()
    job = job.transition(PublishJobStatus.PREFLIGHT)
    job = job.transition(PublishJobStatus.AWAITING_CONFIRMATION)
    job = job.transition(PublishJobStatus.PUBLISHING)
    job = job.transition(PublishJobStatus.SWITCHING)
    job = job.transition(PublishJobStatus.VERIFYING)
    job = job.transition(PublishJobStatus.COMPLETED)

    assert job.status is PublishJobStatus.COMPLETED


def test_publish_job_rejects_skipping_safety_stages() -> None:
    with pytest.raises(ValueError, match="illegal publish transition"):
        make_job().transition(PublishJobStatus.COMPLETED)
