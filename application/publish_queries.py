"""Application read queries for publish job status."""

from dataclasses import dataclass
from uuid import UUID

from application.ports import UnitOfWorkFactory
from application.publish_commands import PublishJobNotFoundError
from domain.publish import PublishJob, PublishTarget


@dataclass(frozen=True, slots=True)
class PublishJobView:
    """Durable job plus its materialized targets for a read model."""

    job: PublishJob
    targets: tuple[PublishTarget, ...]


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
            return PublishJobView(job, targets)
