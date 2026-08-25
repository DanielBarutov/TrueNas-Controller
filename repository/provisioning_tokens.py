"""SQLAlchemy provisioning-token repository."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.provisioning import ProvisioningToken
from repository.models import ProvisioningTokenRecord


class SqlAlchemyProvisioningTokenRepository:
    """Persist and atomically consume operator-issued token digests."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: ProvisioningToken) -> None:
        self._session.add(
            ProvisioningTokenRecord(
                id=token.id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
                revoked_at=token.revoked_at,
            )
        )

    async def consume(self, token_hash: str, now: datetime) -> ProvisioningToken | None:
        statement = (
            select(ProvisioningTokenRecord)
            .where(ProvisioningTokenRecord.token_hash == token_hash)
            .with_for_update()
        )
        record = await self._session.scalar(statement)
        if record is None:
            return None

        token = ProvisioningToken(
            id=record.id,
            token_hash=record.token_hash,
            expires_at=record.expires_at,
            used_at=record.used_at,
            revoked_at=record.revoked_at,
        )
        if not token.is_usable(now):
            return None
        record.used_at = now
        return token
