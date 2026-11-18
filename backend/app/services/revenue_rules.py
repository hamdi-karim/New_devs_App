"""Framework-free revenue rules (no FastAPI, DB or Redis imports).

Decisions behind these rules are documented in the README.
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

CENT = Decimal("0.01")


class PropertyNotFound(Exception):
    """The property does not exist for this tenant (maps to HTTP 404)."""


class RevenueUnavailable(Exception):
    """Revenue could not be computed, e.g. the database is down (maps to HTTP 503)."""


def round_money(amount: Decimal) -> Decimal:
    """Round a monetary total to cents, half-up (e.g. 0.005 -> 0.01).

    Applied once to the final total, never per row, and always on Decimal
    (no float arithmetic before rounding).
    """
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def revenue_cache_key(tenant_id: str, property_id: str) -> str:
    """Cache key for a revenue summary: `revenue:v2:{tenant_id}:{property_id}`.

    Property IDs are only unique per tenant, so the tenant must be part of the
    key. The `v2` prefix orphans the old tenant-less `revenue:{property_id}` keys.
    """
    return f"revenue:v2:{tenant_id}:{property_id}"


def month_bounds_utc(year: int, month: int, tz_name: str) -> tuple[datetime, datetime]:
    """Half-open [start, end) bounds of a calendar month in the property's
    local timezone, returned as timezone-aware UTC datetimes.

    Example: March 2024 in Europe/Paris -> (2024-02-29 23:00Z, 2024-03-31 22:00Z);
    the end reflects the DST switch on 2024-03-31.
    """
    tz = ZoneInfo(tz_name)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)
    start = datetime(year, month, 1, tzinfo=tz)
    end = datetime(next_year, next_month, 1, tzinfo=tz)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
