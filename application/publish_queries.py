"""Application read queries for publish job status."""

from dataclasses import dataclass
from uuid import UUID

from application.ports import UnitOfWorkFactory
from application.publish_commands import PublishJobNotFoundError
from domain.publish import PublishArtifact, PublishJob, PublishJobHistory, PublishTarget


@dataclass(frozen=True, slots=True)
class PublishJobView:
    """Durable job plus its materialized targets for a read model."""

    job: PublishJob
    targets: tuple[PublishTarget, ...]
    artifacts: tuple[PublishArtifact, ...] = ()


class GetPublishJobUseCase:
    """Load one publish job and its target rows in a fresh read transaction."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, job_id: UUID) -> PublishJobView:
        async with self._uow_factory() as uow:
            job = await uow.publish_jobs.get(job_id)
            if job is None:
                raise PublishJobNotFoundError("publish job not found")
            targets = await uow.publish_targets.list_for_job(job.id)
            artifacts = await uow.publish_artifacts.list_for_job(job.id)
            return PublishJobView(job, targets, artifacts)


class ListPublishJobsUseCase:
    """Return recent durable jobs as the operator's update history."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, *, limit: int = 10) -> tuple[PublishJobHistory, ...]:
        bounded_limit = max(1, min(limit, 100))
        async with self._uow_factory() as uow:
            return await uow.publish_jobs.list_recent(limit=bounded_limit)
