import logging
from decimal import Decimal
from typing import Any, Dict

from sqlalchemy import text

from app.core.database_pool import db_pool
from app.services.revenue_rules import (
    PropertyNotFound,
    RevenueUnavailable,
    month_bounds_utc,
    round_money,
)

logger = logging.getLogger(__name__)

# Properties are keyed by (id, tenant_id): this both checks ownership and
# returns the timezone used for month boundaries.
_PROPERTY_TIMEZONE = text(
    "SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id"
)

_TOTAL_REVENUE = text("""
    SELECT COALESCE(SUM(total_amount), 0) AS total_revenue,
           COUNT(*) AS reservation_count
    FROM reservations
    WHERE property_id = :property_id AND tenant_id = :tenant_id
""")

_MONTHLY_REVENUE = text("""
    SELECT SUM(total_amount) AS total
    FROM reservations
    WHERE property_id = :property_id
      AND tenant_id = :tenant_id
      AND check_in_date >= :start
      AND check_in_date < :end
""")


async def _property_timezone(session, property_id: str, tenant_id: str) -> str:
    result = await session.execute(
        _PROPERTY_TIMEZONE, {"property_id": property_id, "tenant_id": tenant_id}
    )
    row = result.fetchone()
    if row is None:
        raise PropertyNotFound(property_id)
    return row.timezone


async def calculate_monthly_revenue(
    property_id: str, tenant_id: str, year: int, month: int
) -> Decimal:
    """Revenue for one calendar month in the property's local timezone."""
    try:
        async with db_pool.get_session() as session:
            tz_name = await _property_timezone(session, property_id, tenant_id)
            start, end = month_bounds_utc(year, month, tz_name)
            result = await session.execute(
                _MONTHLY_REVENUE,
                {
                    "property_id": property_id,
                    "tenant_id": tenant_id,
                    "start": start,
                    "end": end,
                },
            )
            total = result.scalar()
    except PropertyNotFound:
        raise
    except Exception as exc:
        logger.exception(
            "Monthly revenue query failed for property=%s tenant=%s %04d-%02d",
            property_id, tenant_id, year, month,
        )
        raise RevenueUnavailable(str(exc)) from exc

    return round_money(Decimal(total or 0))


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """All-time revenue for a property owned by the tenant.

    Raises PropertyNotFound if the tenant does not own the property and
    RevenueUnavailable on any database error (never returns placeholder data).
    """
    try:
        async with db_pool.get_session() as session:
            await _property_timezone(session, property_id, tenant_id)
            result = await session.execute(
                _TOTAL_REVENUE, {"property_id": property_id, "tenant_id": tenant_id}
            )
            row = result.fetchone()
    except PropertyNotFound:
        raise
    except Exception as exc:
        logger.exception(
            "Revenue query failed for property=%s tenant=%s", property_id, tenant_id
        )
        raise RevenueUnavailable(str(exc)) from exc

    total = round_money(Decimal(row.total_revenue or 0))
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": str(total),
        "currency": "USD",
        "count": row.reservation_count,
    }
