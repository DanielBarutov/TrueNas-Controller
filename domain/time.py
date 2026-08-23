"""Timezone normalization shared by pure domain models."""

from datetime import UTC, datetime


def ensure_utc(value: datetime) -> datetime:
    """Treat naive persistence timestamps as UTC and normalize aware values."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
