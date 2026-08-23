"""Pure durable-outbox event types."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class OutboxEventStatus(StrEnum):
    """Lifecycle of one event handed from DB to a relay."""

    PENDING = "pending"
    DISPATCHED = "dispatched"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class OutboxEvent:
    """Secret-free event payload waiting for an external delivery attempt."""

    id: UUID
    aggregate_id: UUID
    event_type: str
    payload: dict[str, object]
    correlation_id: UUID
    status: OutboxEventStatus = OutboxEventStatus.PENDING
    attempts: int = 0
    available_at: datetime | None = None
    created_at: datetime | None = None
