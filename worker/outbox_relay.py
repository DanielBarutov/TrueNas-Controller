"""Dramatiq outbox relay without holding a DB transaction around queue IO."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from application.ports import PublishTaskQueue, UnitOfWorkFactory
from domain.outbox import OutboxEvent


@dataclass(frozen=True, slots=True)
class OutboxRelayResult:
    """Counts from one bounded relay poll."""

    claimed: int
    dispatched: int
    failed: int


class PublishOutboxRelay:
    """Lease events, send outside the DB transaction, and record the outcome."""

    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        queue: PublishTaskQueue,
        *,
        worker_id: str,
        batch_size: int = 10,
        max_attempts: int = 5,
        lease_seconds: int = 60,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be blank")
        if batch_size < 1 or max_attempts < 1 or lease_seconds < 1:
            raise ValueError("batch_size, max_attempts and lease_seconds must be positive")
        self._uow_factory = uow_factory
        self._queue = queue
        self._worker_id = worker_id
        self._batch_size = batch_size
        self._max_attempts = max_attempts
        self._lease_for = timedelta(seconds=lease_seconds)

    async def run_once(self, *, now: datetime | None = None) -> OutboxRelayResult:
        relay_time = now or datetime.now(UTC)
        async with self._uow_factory() as uow:
            events = await uow.outbox_events.claim_pending(
                limit=self._batch_size,
                worker_id=self._worker_id,
                now=relay_time,
                lease_for=self._lease_for,
            )
            await uow.commit()

        dispatched = 0
        failed = 0
        for event in events:
            try:
                self._send(event)
            except Exception:
                failed += 1
                async with self._uow_factory() as uow:
                    await uow.outbox_events.mark_failed(
                        event.id,
                        error="outbox delivery failed",
                        retry_at=relay_time + self._retry_delay(event.attempts),
                        max_attempts=self._max_attempts,
                    )
                    await uow.commit()
            else:
                dispatched += 1
                async with self._uow_factory() as uow:
                    await uow.outbox_events.mark_dispatched(event.id, relay_time)
                    await uow.commit()
        return OutboxRelayResult(len(events), dispatched, failed)

    def _send(self, event: OutboxEvent) -> None:
        if event.event_type != "publish.dispatch":
            raise ValueError("unsupported outbox event type")
        payload = event.payload
        required = {"job_id", "correlation_id", "idempotency_key"}
        if set(payload) != required or any(not isinstance(payload[key], str) for key in required):
            raise ValueError("invalid publish outbox payload")
        job_id = UUID(payload["job_id"])
        correlation_id = UUID(payload["correlation_id"])
        if job_id != event.aggregate_id or correlation_id != event.correlation_id:
            raise ValueError("outbox payload identity mismatch")
        self._queue.enqueue(
            job_id=job_id,
            correlation_id=correlation_id,
            idempotency_key=payload["idempotency_key"],
        )

    @staticmethod
    def _retry_delay(attempts: int) -> timedelta:
        return timedelta(seconds=2 ** min(attempts + 1, 8))
