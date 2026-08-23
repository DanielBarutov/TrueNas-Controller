"""SQLAlchemy enrollment-token repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.enrollment import EnrollmentToken
from repository.models import EnrollmentTokenRecord, StationRecord


class SqlAlchemyEnrollmentTokenRepository:
    """Persist and atomically consume one-time token digests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: EnrollmentToken) -> None:
        station_pk = await self._session.scalar(
            select(StationRecord.id).where(StationRecord.station_id == token.station_id)
        )
        if station_pk is None:
            raise ValueError("station not found")
        self._session.add(
            EnrollmentTokenRecord(
                id=token.id,
                station_id=station_pk,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
                revoked_at=token.revoked_at,
            )
        )

    async def consume(self, token_hash: str, now: datetime) -> EnrollmentToken | None:
        statement = (
            select(EnrollmentTokenRecord, StationRecord)
            .join(StationRecord, EnrollmentTokenRecord.station_id == StationRecord.id)
            .where(EnrollmentTokenRecord.token_hash == token_hash)
            .with_for_update()
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None

        record, station = row
        token = EnrollmentToken(
            id=record.id,
            station_id=station.station_id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            used_at=record.used_at,
            revoked_at=record.revoked_at,
        )
        if not token.is_usable(now):
            return None
        record.used_at = now
        return token
