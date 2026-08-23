"""Dramatiq task boundary for publish jobs."""

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import dramatiq


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
