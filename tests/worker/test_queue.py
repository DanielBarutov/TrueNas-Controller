from uuid import uuid4

from worker.tasks import DramatiqPublishTaskQueue


class SpyActor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def send(self, job_id: str, correlation_id: str, idempotency_key: str) -> None:
        self.calls.append((job_id, correlation_id, idempotency_key))


def test_dramatiq_queue_serializes_only_minimal_payload() -> None:
    actor = SpyActor()
    queue = DramatiqPublishTaskQueue(actor)  # type: ignore[arg-type]
    job_id, correlation_id = uuid4(), uuid4()

    queue.enqueue(
        job_id=job_id,
        correlation_id=correlation_id,
        idempotency_key="queue-key",
    )

    assert actor.calls == [(str(job_id), str(correlation_id), "queue-key")]
