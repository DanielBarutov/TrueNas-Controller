"""SQLAlchemy engine and session-factory construction."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import Pool


def create_engine(
    database_url: str,
    *,
    echo: bool = False,
    poolclass: type[Pool] | None = None,
) -> AsyncEngine:
    """Create an engine; callers own its lifecycle and must dispose it.

    ``NullPool`` is useful for embedded async workers that bridge synchronous
    Dramatiq callbacks into short-lived event loops. It prevents an asyncpg
    connection created by one loop from being reused by another loop.
    """

    kwargs: dict[str, object] = {"echo": echo, "pool_pre_ping": True}
    if poolclass is not None:
        kwargs["poolclass"] = poolclass
    return create_async_engine(database_url, **kwargs)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a factory that yields independent sessions."""

    return async_sessionmaker(engine, expire_on_commit=False)
