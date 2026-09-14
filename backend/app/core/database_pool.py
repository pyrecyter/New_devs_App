import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings

logger = logging.getLogger(__name__)


def to_async_database_url(database_url: str) -> str:
    """Convert a sync Postgres URL to the SQLAlchemy asyncpg dialect."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    return database_url


class DatabasePool:
    def __init__(self):
        self.engine = None
        self.session_factory = None
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the shared async connection pool once."""
        if self.session_factory:
            return

        async with self._lock:
            if self.session_factory:
                return

            try:
                database_url = to_async_database_url(settings.database_url)

                self.engine = create_async_engine(
                    database_url,
                    pool_size=settings.database_pool_size,
                    max_overflow=settings.database_max_overflow,
                    pool_pre_ping=True,
                    pool_recycle=settings.database_pool_recycle,
                    echo=False,
                )

                self.session_factory = async_sessionmaker(
                    bind=self.engine,
                    class_=AsyncSession,
                    expire_on_commit=False,
                )

                logger.info("Database connection pool initialized")
            except Exception as e:
                logger.error(f"Database pool initialization failed: {e}")
                self.engine = None
                self.session_factory = None
                raise

    async def close(self):
        """Close database connections."""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Yield a database session from the shared pool."""
        if not self.session_factory:
            await self.initialize()
        if not self.session_factory:
            raise Exception("Database pool not initialized")

        async with self.session_factory() as session:
            yield session


db_pool = DatabasePool()


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a pooled session."""
    async with db_pool.get_session() as session:
        yield session
