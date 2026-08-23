"""Pure enrollment token model."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from domain.time import ensure_utc


@dataclass(frozen=True, slots=True)
class EnrollmentToken:
    """One-time token represented only by its digest in persistence."""

    id: UUID
    station_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None

    def is_usable(self, now: datetime) -> bool:
        """Return whether the token may be atomically claimed now."""

        return (
            self.used_at is None
            and self.revoked_at is None
            and ensure_utc(now) < ensure_utc(self.expires_at)
        )
