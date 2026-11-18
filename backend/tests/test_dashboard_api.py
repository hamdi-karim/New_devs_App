"""API tests for GET /api/v1/dashboard/summary (no DB, no Redis, no Supabase).

A bare FastAPI app mounts only the dashboard router; auth, Redis and the
revenue calculator are replaced with in-memory fakes.
"""
import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import dashboard
from app.core.auth import authenticate_request
from app.services import cache, reservations
from app.services.revenue_rules import PropertyNotFound, RevenueUnavailable


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        self.store[key] = value


class FakeCalculator:
    """Async stand-in for calculate_total_revenue; records each call."""

    def __init__(self, totals=None, error=None):
        self.totals = totals or {}
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, property_id, tenant_id):
        self.calls.append((property_id, tenant_id))
        if self.error is not None:
            raise self.error
        total, count = self.totals[tenant_id]
        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": total,
            "currency": "USD",
            "count": count,
        }


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache, "redis_client", fake)
    return fake


def install_calculator(monkeypatch, calculator):
    monkeypatch.setattr(reservations, "calculate_total_revenue", calculator)


def make_client(tenant_id):
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1")
    app.dependency_overrides[authenticate_request] = lambda: SimpleNamespace(
        tenant_id=tenant_id
    )
    return TestClient(app)


def get_summary(tenant_id, property_id="prop-001"):
    return make_client(tenant_id).get(
        "/api/v1/dashboard/summary", params={"property_id": property_id}
    )


def test_tenants_sharing_a_property_id_get_their_own_totals(fake_redis, monkeypatch):
    calc = FakeCalculator(totals={"tenant-a": ("2250.00", 4), "tenant-b": ("1000.00", 3)})
    install_calculator(monkeypatch, calc)

    resp_a = get_summary("tenant-a")
    resp_b = get_summary("tenant-b")

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["total_revenue"] == 2250.0
    assert resp_b.json()["total_revenue"] == 1000.0
    assert calc.calls == [("prop-001", "tenant-a"), ("prop-001", "tenant-b")]


def test_second_request_by_same_tenant_is_served_from_cache(fake_redis, monkeypatch):
    calc = FakeCalculator(totals={"tenant-a": ("2250.00", 4)})
    install_calculator(monkeypatch, calc)

    first = get_summary("tenant-a")
    second = get_summary("tenant-a")

    assert first.json() == second.json()
    assert len(calc.calls) == 1


def test_user_without_tenant_is_forbidden(fake_redis, monkeypatch):
    calc = FakeCalculator(totals={})
    install_calculator(monkeypatch, calc)

    resp = get_summary(None)

    assert resp.status_code == 403
    assert calc.calls == []


def test_property_not_owned_by_tenant_is_404(fake_redis, monkeypatch):
    install_calculator(monkeypatch, FakeCalculator(error=PropertyNotFound("prop-001")))

    resp = get_summary("tenant-a")

    assert resp.status_code == 404


def test_revenue_unavailable_is_503_and_not_cached(fake_redis, monkeypatch):
    install_calculator(monkeypatch, FakeCalculator(error=RevenueUnavailable("db down")))

    resp = get_summary("tenant-a")

    assert resp.status_code == 503
    assert fake_redis.store == {}


def test_response_shape_and_money_conversion(fake_redis, monkeypatch):
    install_calculator(monkeypatch, FakeCalculator(totals={"tenant-a": ("2250.00", 4)}))

    resp = get_summary("tenant-a")

    assert resp.status_code == 200
    assert resp.json() == {
        "property_id": "prop-001",
        "total_revenue": 2250.0,
        "currency": "USD",
        "reservations_count": 4,
    }


# --- reservations service, without a database ---------------------------


class FailingSession:
    async def execute(self, *args, **kwargs):
        raise Exception("connection refused")


class FailingPool:
    @asynccontextmanager
    async def get_session(self):
        yield FailingSession()


def test_db_error_raises_revenue_unavailable_instead_of_mock_data(monkeypatch):
    monkeypatch.setattr(reservations, "db_pool", FailingPool())

    with pytest.raises(RevenueUnavailable):
        asyncio.run(reservations.calculate_total_revenue("prop-001", "tenant-a"))
