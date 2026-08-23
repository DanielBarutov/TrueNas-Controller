"""SQLAlchemy engine and session-factory construction."""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str, *, echo: bool = False) -> AsyncEngine:
    """Create an engine; callers own its lifecycle and must dispose it."""

    return create_async_engine(database_url, echo=echo, pool_pre_ping=True)


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create a factory that yields independent sessions."""

    return async_sessionmaker(engine, expire_on_commit=False)
