"""Application commands for creating and enqueueing publish jobs."""

from dataclasses import dataclass
from uuid import UUID, uuid4

from application.ports import PublishTaskQueue, UnitOfWorkFactory
from domain.publish import PublishJob, PublishTarget


class PublishDraftValidationError(ValueError):
    """Raised when a draft request violates an application invariant."""


class PublishIdempotencyConflictError(PublishDraftValidationError):
    """Raised when a key is reused with a different request shape."""


class PublishJobNotFoundError(ValueError):
    """Raised when enqueue references a job absent from durable state."""


class PublishTaskPayloadMismatchError(ValueError):
    """Raised when enqueue data does not match the durable job."""


@dataclass(frozen=True, slots=True)
class PublishJobDraft:
    """Created job and materialized targets returned by the draft command."""

    job: PublishJob
    targets: tuple[PublishTarget, ...]


class CreatePublishJobUseCase:
    """Validate station selection and atomically persist a draft job."""

    def __init__(self, uow_factory: UnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        label: str,
        source_dataset: str,
        station_ids: tuple[UUID, ...],
        idempotency_key: str,
        correlation_id: UUID,
        description: str | None = None,
        dry_run: bool = True,
        allow_hot_switch: bool = False,
        operator_id: UUID | None = None,
    ) -> PublishJobDraft:
        self._validate_request(label, source_dataset, station_ids, idempotency_key)

        async with self._uow_factory() as uow:
            existing = await uow.publish_jobs.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                existing_targets = await uow.publish_targets.list_for_job(existing.id)
                if self._same_request(
                    existing,
                    existing_targets,
                    label=label,
                    source_dataset=source_dataset,
                    station_ids=station_ids,
                    correlation_id=correlation_id,
                    description=description,
                    dry_run=dry_run,
                    allow_hot_switch=allow_hot_switch,
                    operator_id=operator_id,
                ):
                    return PublishJobDraft(existing, existing_targets)
                raise PublishIdempotencyConflictError(
                    "idempotency key is already used by another publish request"
                )

            for station_id in station_ids:
                station = await uow.stations.get(station_id)
                if station is None:
                    raise PublishDraftValidationError(f"station not found: {station_id}")
                if not station.enabled or station.deleted_at is not None:
                    raise PublishDraftValidationError(f"station is disabled: {station_id}")

            job = PublishJob(
                id=uuid4(),
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                label=label,
                source_dataset=source_dataset,
                dry_run=dry_run,
                allow_hot_switch=allow_hot_switch,
                description=description,
                operator_id=operator_id,
            )
            targets = tuple(
                PublishTarget(id=uuid4(), job_id=job.id, station_id=station_id)
                for station_id in station_ids
            )
            await uow.publish_jobs.add(job)
            await uow.publish_targets.add_many(targets)
            await uow.commit()
            return PublishJobDraft(job, targets)

    @staticmethod
    def _validate_request(
        label: str,
        source_dataset: str,
        station_ids: tuple[UUID, ...],
        idempotency_key: str,
    ) -> None:
        if not label.strip():
            raise PublishDraftValidationError("label must not be blank")
        if not source_dataset.strip():
            raise PublishDraftValidationError("source_dataset must not be blank")
        if not station_ids:
            raise PublishDraftValidationError("at least one station is required")
        if len(set(station_ids)) != len(station_ids):
            raise PublishDraftValidationError("station selection must be unique")
        if not idempotency_key or len(idempotency_key) > 200:
            raise PublishDraftValidationError("invalid idempotency key")

    @staticmethod
    def _same_request(
        job: PublishJob,
        targets: tuple[PublishTarget, ...],
        *,
        label: str,
        source_dataset: str,
        station_ids: tuple[UUID, ...],
        correlation_id: UUID,
        description: str | None,
        dry_run: bool,
        allow_hot_switch: bool,
        operator_id: UUID | None,
    ) -> bool:
        return (
            job.label == label
            and job.source_dataset == source_dataset
            and job.description == description
            and job.dry_run == dry_run
            and job.allow_hot_switch == allow_hot_switch
            and job.operator_id == operator_id
            and job.correlation_id == correlation_id
            and {target.station_id for target in targets} == set(station_ids)
        )


class EnqueuePublishJobUseCase:
    """Enqueue a verified minimal task payload after a short state read."""

    def __init__(self, uow_factory: UnitOfWorkFactory, queue: PublishTaskQueue) -> None:
        self._uow_factory = uow_factory
        self._queue = queue

    async def execute(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        async with self._uow_factory() as uow:
            job = await uow.publish_jobs.get(job_id)
            if job is None:
                raise PublishJobNotFoundError("publish job not found")
            if job.correlation_id != correlation_id:
                raise PublishTaskPayloadMismatchError("correlation ID does not match publish job")
            if job.idempotency_key != idempotency_key:
                raise PublishTaskPayloadMismatchError("idempotency key does not match publish job")

        self._queue.enqueue(
            job_id=job_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
