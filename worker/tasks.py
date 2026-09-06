"""Dramatiq task boundaries for publish and retention jobs."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import dramatiq

from application.ports import DatasetCleanupTaskQueue, PublishTaskQueue


@dataclass(frozen=True, slots=True)
class PublishTaskPayload:
    """Trusted-minimal task input; full job state is loaded by the handler."""

    job_id: UUID
    correlation_id: UUID
    idempotency_key: str

    @classmethod
    def from_raw(
        cls, job_id: str, correlation_id: str, idempotency_key: str
    ) -> "PublishTaskPayload":
        if not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("invalid idempotency key")
        return cls(UUID(job_id), UUID(correlation_id), idempotency_key)


PublishTaskHandler = Callable[[PublishTaskPayload], None]
PublishTaskHandlerFactory = Callable[[], PublishTaskHandler]
DatasetCleanupTaskHandler = Callable[[tuple[UUID, ...]], None]
DatasetCleanupTaskHandlerFactory = Callable[[], DatasetCleanupTaskHandler]


class DramatiqPublishTaskQueue(PublishTaskQueue):
    """Queue adapter that serializes only the worker's minimal task payload."""

    def __init__(self, actor: dramatiq.Actor) -> None:
        self._actor = actor

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        self._actor.send(str(job_id), str(correlation_id), idempotency_key)


class DramatiqDatasetCleanupTaskQueue(DatasetCleanupTaskQueue):
    """Queue explicit dataset IDs for the existing cleanup worker actor."""

    def __init__(self, actor: dramatiq.Actor) -> None:
        self._actor = actor

    def enqueue(self, *, artifact_ids: tuple[UUID, ...]) -> None:
        self._actor.send([str(artifact_id) for artifact_id in artifact_ids])


def build_publish_actor(
    handler_factory: PublishTaskHandlerFactory,
    *,
    actor_name: str = "publish_job",
) -> dramatiq.Actor:
    """Build an actor whose handler factory runs fresh per delivered message."""

    @dramatiq.actor(actor_name=actor_name, max_retries=0)
    def publish_job(job_id: str, correlation_id: str, idempotency_key: str) -> None:
        payload = PublishTaskPayload.from_raw(job_id, correlation_id, idempotency_key)
        handler_factory()(payload)

    return publish_job


def build_dataset_cleanup_actor(
    handler_factory: DatasetCleanupTaskHandlerFactory,
    *,
    actor_name: str = "dataset_cleanup",
) -> dramatiq.Actor:
    """Build the scheduled/manual cleanup actor with validated artifact IDs."""

    @dramatiq.actor(actor_name=actor_name, max_retries=0)
    def dataset_cleanup(artifact_ids: list[str] | None = None) -> None:
        parsed_ids = (
            () if artifact_ids is None else tuple(UUID(artifact_id) for artifact_id in artifact_ids)
        )
        handler_factory()(parsed_ids)

    return dataset_cleanup
