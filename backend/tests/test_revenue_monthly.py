from datetime import timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.database_pool import to_async_database_url
from app.services.reservations import (
    PropertyNotFoundError,
    calculate_monthly_revenue,
    month_bounds,
)
from tests.conftest import FakePool


def test_month_bounds_are_half_open():
    start, end = month_bounds(2024, 3)
    assert start.isoformat() == "2024-03-01"
    assert end.isoformat() == "2024-04-01"


def test_res_tz_1_is_march_in_paris(seed_check_in_boundary):
    local = seed_check_in_boundary.astimezone(ZoneInfo("Europe/Paris"))
    assert (local.year, local.month, local.day) == (2024, 3, 1)
    assert seed_check_in_boundary.astimezone(timezone.utc).month == 2


def test_async_database_url_uses_asyncpg():
    assert (
        to_async_database_url("postgresql://postgres:postgres@db:5432/propertyflow")
        == "postgresql+asyncpg://postgres:postgres@db:5432/propertyflow"
    )


@pytest.mark.asyncio
async def test_march_2024_paris_includes_timezone_boundary(monkeypatch, sunset_march_row):
    pool = FakePool(sunset_march_row)
    monkeypatch.setattr("app.services.reservations.db_pool", pool)

    result = await calculate_monthly_revenue("prop-001", "tenant-a", 3, 2024)

    assert result["total"] == "2250.00"
    assert result["count"] == 4
    assert result["tenant_id"] == "tenant-a"
    assert pool.captured["params"]["tenant_id"] == "tenant-a"
    assert pool.captured["params"]["month_start"].isoformat() == "2024-03-01"
    assert pool.captured["params"]["month_end"].isoformat() == "2024-04-01"
    assert "AT TIME ZONE" in pool.captured["query"]


@pytest.mark.asyncio
async def test_ocean_overlapping_property_id_is_isolated(monkeypatch, ocean_prop001_row):
    pool = FakePool(ocean_prop001_row)
    monkeypatch.setattr("app.services.reservations.db_pool", pool)

    result = await calculate_monthly_revenue("prop-001", "tenant-b", 3, 2024)

    assert result["tenant_id"] == "tenant-b"
    assert result["total"] == "0.00"
    assert result["count"] == 0
    assert pool.captured["params"]["tenant_id"] == "tenant-b"


@pytest.mark.asyncio
async def test_unknown_property_raises(monkeypatch):
    pool = FakePool(None)
    monkeypatch.setattr("app.services.reservations.db_pool", pool)

    with pytest.raises(PropertyNotFoundError):
        await calculate_monthly_revenue("prop-unknown", "tenant-a", 3, 2024)
