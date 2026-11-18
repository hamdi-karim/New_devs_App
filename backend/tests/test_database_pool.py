import asyncio

import pytest
from sqlalchemy import text

from app.config import settings
from app.core.database_pool import DatabasePool, to_async_dsn

TEST_DB_URL = "postgresql://postgres:postgres@localhost:5433/propertyflow"


def test_to_async_dsn_postgresql_scheme():
    assert (
        to_async_dsn("postgresql://u:p@h:5432/db")
        == "postgresql+asyncpg://u:p@h:5432/db"
    )


def test_to_async_dsn_postgres_scheme():
    assert (
        to_async_dsn("postgres://u:p@h:5432/db")
        == "postgresql+asyncpg://u:p@h:5432/db"
    )


def test_to_async_dsn_already_asyncpg_unchanged():
    url = "postgresql+asyncpg://u:p@h:5432/db"
    assert to_async_dsn(url) == url


def test_default_pool_uses_settings_database_url():
    pool = DatabasePool()
    assert pool.database_url == to_async_dsn(settings.database_url)
    assert pool.database_url.startswith("postgresql+asyncpg://")


@pytest.mark.db
def test_get_session_queries_seeded_reservations():
    async def run():
        pool = DatabasePool(TEST_DB_URL)
        try:
            async with pool.get_session() as session:
                result = await session.execute(text("select count(*) from reservations"))
                return result.scalar()
        finally:
            await pool.close()

    assert asyncio.run(run()) == 17


@pytest.mark.db
def test_initialize_is_idempotent():
    async def run():
        pool = DatabasePool(TEST_DB_URL)
        try:
            await pool.initialize()
            first = pool.engine
            await pool.initialize()
            return first, pool.engine
        finally:
            await pool.close()

    first, second = asyncio.run(run())
    assert first is not None
    assert first is second
