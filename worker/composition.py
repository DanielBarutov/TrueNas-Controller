"""Composition boundary between Dramatiq messages and application ports."""

import asyncio
from collections.abc import Callable
import logging

from application.dataset_cleanup import DatasetCleanupUseCase
from application.ports import (
    PublishTaskExecutor,
    TrueNASWriteClient,
    UnitOfWorkFactory,
)
from domain.publish import PublishJob
from worker.tasks import PublishTaskPayload


class PublishTaskStateError(ValueError):
    """Raised when a worker message cannot be matched to durable state."""


PublishTaskExecutorFactory = Callable[[], PublishTaskExecutor]
TrueNASWriteClientFactory = Callable[[], TrueNASWriteClient]


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


class DatasetCleanupApplicationHandler:
    """Run one bounded retention pass behind the Dramatiq sync boundary."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        *,
        retention_days: int,
        batch_size: int,
        apply_enabled: bool,
        write_client_factory: TrueNASWriteClientFactory | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._retention_days = retention_days
        self._batch_size = batch_size
        self._apply_enabled = apply_enabled
        self._write_client_factory = write_client_factory

    def __call__(self) -> None:
        asyncio.run(self.handle())

    async def handle(self) -> None:
        write_client = None
        if self._apply_enabled:
            if self._write_client_factory is None:
                raise ValueError("TrueNAS write client factory is required for cleanup apply")
            write_client = self._write_client_factory()
        try:
            result = await DatasetCleanupUseCase(
                self._uow_factory,
                retention_days=self._retention_days,
                batch_size=self._batch_size,
                apply_enabled=self._apply_enabled,
            ).execute(write_client=write_client)
            logging.getLogger(__name__).info(
                "dataset cleanup pass: inspected=%s deleted=%s failed=%s dry_run=%s",
                result.inspected,
                result.deleted,
                result.failed,
                result.dry_run,
            )
        finally:
            if write_client is not None:
                await write_client.close()


__all__ = [
    "DatasetCleanupApplicationHandler",
    "PublishTaskApplicationHandler",
    "PublishTaskExecutorFactory",
    "PublishTaskStateError",
]
