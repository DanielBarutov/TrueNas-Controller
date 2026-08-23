"""Composition boundary between Dramatiq messages and application ports."""

import asyncio
from collections.abc import Callable

from application.ports import PublishTaskExecutor, UnitOfWorkFactory
from domain.publish import PublishJob
from worker.tasks import PublishTaskPayload


class PublishTaskStateError(ValueError):
    """Raised when a worker message cannot be matched to durable state."""


PublishTaskExecutorFactory = Callable[[], PublishTaskExecutor]


class PublishTaskApplicationHandler:
    """Reload a publish job before handing it to the next-stage executor."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        executor_factory: PublishTaskExecutorFactory,
    ) -> None:
        self._uow_factory = uow_factory
        self._executor_factory = executor_factory

    def __call__(self, payload: PublishTaskPayload) -> None:
        """Synchronous Dramatiq boundary around the async application flow."""

        asyncio.run(self.handle(payload))

    async def handle(self, payload: PublishTaskPayload) -> None:
        """Load state in a short transaction and execute after it is closed."""

        async with self._uow_factory() as uow:
            job = await uow.publish_jobs.get(payload.job_id)
            if job is None:
                raise PublishTaskStateError("publish job not found")
            self._validate_payload(job, payload)
            targets = await uow.publish_targets.list_for_job(job.id)

        executor = self._executor_factory()
        await executor.execute(job, targets, correlation_id=payload.correlation_id)

    @staticmethod
    def _validate_payload(job: PublishJob, payload: PublishTaskPayload) -> None:
        if job.idempotency_key != payload.idempotency_key:
            raise PublishTaskStateError("task idempotency key does not match publish job")
        if job.correlation_id != payload.correlation_id:
            raise PublishTaskStateError("task correlation ID does not match publish job")


__all__ = [
    "PublishTaskApplicationHandler",
    "PublishTaskExecutorFactory",
    "PublishTaskStateError",
]
