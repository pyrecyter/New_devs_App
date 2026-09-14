from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from sqlalchemy import text

from app.core.database_pool import db_pool

MONEY_QUANT = Decimal("0.01")


class PropertyNotFoundError(Exception):
    """Raised when a property does not belong to the requesting tenant."""


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return a half-open [start, end) local-date interval for a reporting month."""
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def quantize_money(value: Any) -> Decimal:
    """Convert an exact numeric value to a two-decimal currency amount."""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, float):
        raise TypeError("Refusing to convert float to money; use Decimal or str")
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def format_money(value: Any) -> str:
    return str(quantize_money(value))


async def calculate_monthly_revenue(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
) -> Dict[str, Any]:
    """
    Aggregate reservation revenue for one property in a tenant-local month.

    Month boundaries are evaluated in the property's timezone so a UTC check-in
    that falls on the 1st locally (e.g. Paris) is included in that month.
    """
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")

    start_date, end_date = month_bounds(year, month)

    await db_pool.initialize()

    async with db_pool.get_session() as session:
        query = text(
            """
            SELECT
                p.id AS property_id,
                p.timezone AS timezone,
                COALESCE(SUM(r.total_amount), 0) AS total_revenue,
                COUNT(r.id) AS reservation_count
            FROM properties p
            LEFT JOIN reservations r
              ON r.property_id = p.id
             AND r.tenant_id = p.tenant_id
             AND (r.check_in_date AT TIME ZONE p.timezone) >= :month_start
             AND (r.check_in_date AT TIME ZONE p.timezone) < :month_end
            WHERE p.id = :property_id
              AND p.tenant_id = :tenant_id
            GROUP BY p.id, p.timezone
            """
        )

        result = await session.execute(
            query,
            {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "month_start": start_date,
                "month_end": end_date,
            },
        )
        row = result.fetchone()

    if row is None:
        raise PropertyNotFoundError(
            f"Property {property_id} was not found for tenant {tenant_id}"
        )

    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "total": format_money(row.total_revenue),
        "currency": "USD",
        "count": int(row.reservation_count or 0),
        "month": month,
        "year": year,
        "timezone": row.timezone,
    }


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """Backward-compatible wrapper around the monthly aggregator."""
    if month is None or year is None:
        today = date.today()
        month = month or today.month
        year = year or today.year
    return await calculate_monthly_revenue(property_id, tenant_id, month, year)
