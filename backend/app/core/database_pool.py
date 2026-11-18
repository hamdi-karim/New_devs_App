from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import logging
from ..config import settings

logger = logging.getLogger(__name__)


def to_async_dsn(url: str) -> str:
    """Convert a sync Postgres URL (postgresql:// or postgres://) to the asyncpg dialect."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


class DatabasePool:
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = to_async_dsn(database_url or settings.database_url)
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        """Initialize database connection pool (idempotent)"""
        if self.engine is not None:
            return
        try:
            # The async engine uses AsyncAdaptedQueuePool by default; QueuePool is not asyncio-compatible.
            self.engine = create_async_engine(
                self.database_url,
                pool_size=20,  # Number of connections to maintain
                max_overflow=30,  # Additional connections when needed
                pool_pre_ping=True,  # Validate connections
                pool_recycle=3600,  # Recycle connections every hour
                echo=False  # Set to True for SQL debugging
            )

            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            logger.info("✅ Database connection pool initialized")

        except Exception as e:
            logger.error(f"❌ Database pool initialization failed: {e}")
            self.engine = None
            self.session_factory = None
            raise

    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Get database session from pool"""
        if self.session_factory is None:
            await self.initialize()
        async with self.session_factory() as session:
            yield session

# Global database pool instance
db_pool = DatabasePool()

async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Dependency to get database session"""
    async with db_pool.get_session() as session:
        yield session
