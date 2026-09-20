"""Lazy asynchronous SQLAlchemy database boundary."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Own the async engine and explicit transaction boundaries.

    Constructing this object performs no network I/O. The first ping or session
    opens the external connection.
    """

    def __init__(self, url: str, connect_timeout_seconds: float = 5.0) -> None:
        self._url = url
        self._connect_timeout_seconds = connect_timeout_seconds
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            self._engine = create_async_engine(
                self._url,
                pool_pre_ping=True,
                connect_args={"timeout": self._connect_timeout_seconds},
            )
        return self._engine

    @property
    def is_initialized(self) -> bool:
        """Report whether SQLAlchemy resources have been allocated."""

        return self._engine is not None

    def _sessions(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                bind=self.engine,
                expire_on_commit=False,
                autoflush=False,
            )
        return self._session_factory

    async def ping(self) -> None:
        async with self.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[AsyncSession]:
        """Provide one atomic unit of work with rollback on failure."""

        async with self._sessions()() as session, session.begin():
            yield session

    async def dispose(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()


def build_database(url: str | None, connect_timeout_seconds: float) -> Database | None:
    if url is None:
        return None
    return Database(url=url, connect_timeout_seconds=connect_timeout_seconds)
