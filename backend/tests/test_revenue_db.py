"""Integration tests against the seeded Docker Postgres (database/seed.sql).

Skipped automatically when localhost:5433 is unreachable (see conftest.py).
"""
import asyncio
from decimal import Decimal

import pytest

import app.core.database_pool as database_pool_module
from app.core.database_pool import DatabasePool
from app.services import reservations
from app.services.revenue_rules import PropertyNotFound
from tests.conftest import DB_HOST, DB_PORT

pytestmark = pytest.mark.db

LOCAL_DB_URL = f"postgresql://postgres:postgres@{DB_HOST}:{DB_PORT}/propertyflow"


def run_with_local_db(monkeypatch, coro_factory):
    """Point the revenue service at the local seeded DB, run, then dispose the pool.

    A fresh pool per test: an async engine is bound to the event loop of the
    asyncio.run() call that created its connections.
    """
    pool = DatabasePool(LOCAL_DB_URL)
    monkeypatch.setattr(database_pool_module, "db_pool", pool)
    monkeypatch.setattr(reservations, "db_pool", pool, raising=False)

    async def runner():
        try:
            return await coro_factory()
        finally:
            await pool.close()

    return asyncio.run(runner())


def test_sunset_prop_001_all_time_total_comes_from_db_not_mock(monkeypatch):
    result = run_with_local_db(
        monkeypatch, lambda: reservations.calculate_total_revenue("prop-001", "tenant-a")
    )

    # Mock data said 1000.00; the real seed has res-tz-1 (1250) + 3 x ~333.33.
    assert result["total"] == "2250.00"
    assert result["count"] == 4


def test_ocean_prop_001_is_isolated_from_sunset_prop_001(monkeypatch):
    result = run_with_local_db(
        monkeypatch, lambda: reservations.calculate_total_revenue("prop-001", "tenant-b")
    )

    assert result["total"] == "0.00"
    assert result["count"] == 0


def test_ocean_cannot_read_sunset_only_property(monkeypatch):
    with pytest.raises(PropertyNotFound):
        run_with_local_db(
            monkeypatch, lambda: reservations.calculate_total_revenue("prop-002", "tenant-b")
        )


def test_sunset_march_uses_paris_local_month(monkeypatch):
    total = run_with_local_db(
        monkeypatch,
        lambda: reservations.calculate_monthly_revenue("prop-001", "tenant-a", 2024, 3),
    )

    # res-tz-1 checks in 2024-02-29 23:30 UTC = 2024-03-01 00:30 Paris -> March.
    # A UTC month would give 1000.00 (Sunset's complaint).
    assert total == Decimal("2250.00")
