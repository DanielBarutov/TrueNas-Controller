from datetime import UTC, datetime
from uuid import UUID, uuid4

from domain.outbox import OutboxEvent, OutboxEventStatus
from worker.outbox_relay import PublishOutboxRelay

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


class FakeOutbox:
    def __init__(self, events: list[OutboxEvent]) -> None:
        self.events = events

    async def claim_pending(
        self,
        *,
        limit: int,
        worker_id: str,
        now: datetime,
        lease_for,
    ):
        claimed = [
            event
            for event in self.events
            if event.status is OutboxEventStatus.PENDING
            and (event.available_at is None or event.available_at <= now)
        ][:limit]
        return tuple(claimed)

    async def mark_dispatched(self, event_id: UUID, dispatched_at: datetime) -> None:
        for index, event in enumerate(self.events):
            if event.id == event_id:
                self.events[index] = OutboxEvent(
                    id=event.id,
                    aggregate_id=event.aggregate_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    status=OutboxEventStatus.DISPATCHED,
                    attempts=event.attempts,
                    available_at=event.available_at,
                    created_at=event.created_at,
                )
                return
        raise ValueError("event not found")

    async def mark_failed(
        self,
        event_id: UUID,
        *,
        error: str,
        retry_at: datetime,
        max_attempts: int,
    ) -> None:
        for index, event in enumerate(self.events):
            if event.id == event_id:
                attempts = event.attempts + 1
                self.events[index] = OutboxEvent(
                    id=event.id,
                    aggregate_id=event.aggregate_id,
                    event_type=event.event_type,
                    payload=event.payload,
                    correlation_id=event.correlation_id,
                    status=(
                        OutboxEventStatus.FAILED
                        if attempts >= max_attempts
                        else OutboxEventStatus.PENDING
                    ),
                    attempts=attempts,
                    available_at=retry_at,
                    created_at=event.created_at,
                )
                return
        raise ValueError("event not found")


class FakeUow:
    def __init__(self, outbox: FakeOutbox) -> None:
        self.outbox_events = outbox

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def commit(self) -> None:
        return None


class FakeQueue:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[UUID, UUID, str]] = []

    def enqueue(
        self,
        *,
        job_id: UUID,
        correlation_id: UUID,
        idempotency_key: str,
    ) -> None:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.calls.append((job_id, correlation_id, idempotency_key))


def make_event(*, valid: bool = True) -> OutboxEvent:
    job_id, correlation_id = uuid4(), uuid4()
    return OutboxEvent(
        id=uuid4(),
        aggregate_id=job_id,
        event_type="publish.dispatch",
        payload={
            "job_id": str(job_id) if valid else "bad-job",
            "correlation_id": str(correlation_id),
            "idempotency_key": "outbox-key",
        },
        correlation_id=correlation_id,
        available_at=NOW,
    )


def make_relay(outbox: FakeOutbox, queue: FakeQueue, *, max_attempts: int = 3):
    return PublishOutboxRelay(
        lambda: FakeUow(outbox),
        queue,
        worker_id="relay-1",
        max_attempts=max_attempts,
    )


async def test_relay_sends_minimal_payload_and_marks_dispatched() -> None:
    outbox = FakeOutbox([make_event()])
    queue = FakeQueue()

    result = await make_relay(outbox, queue).run_once(now=NOW)

    assert result.claimed == 1
    assert result.dispatched == 1
    assert result.failed == 0
    assert outbox.events[0].status is OutboxEventStatus.DISPATCHED
    assert queue.calls == [
        (
            UUID(outbox.events[0].payload["job_id"]),
            UUID(outbox.events[0].payload["correlation_id"]),
            "outbox-key",
        )
    ]


async def test_relay_failure_schedules_retry_without_losing_event() -> None:
    outbox = FakeOutbox([make_event()])
    queue = FakeQueue(fail=True)

    result = await make_relay(outbox, queue, max_attempts=3).run_once(now=NOW)

    assert result.failed == 1
    assert outbox.events[0].status is OutboxEventStatus.PENDING
    assert outbox.events[0].attempts == 1
    assert outbox.events[0].available_at is not None


async def test_invalid_payload_is_failed_without_queue_call() -> None:
    outbox = FakeOutbox([make_event(valid=False)])
    queue = FakeQueue()

    result = await make_relay(outbox, queue, max_attempts=1).run_once(now=NOW)

    assert result.failed == 1
    assert outbox.events[0].status is OutboxEventStatus.FAILED
    assert queue.calls == []
