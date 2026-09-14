import json

import pytest

from app.services import cache as cache_service
from app.services.cache import cached_entry_matches, get_revenue_summary, revenue_cache_key
from tests.conftest import FakeRedis


def test_cache_key_includes_tenant_and_period():
    sunset_key = revenue_cache_key("tenant-a", "prop-001", 2024, 3)
    ocean_key = revenue_cache_key("tenant-b", "prop-001", 2024, 3)
    april_key = revenue_cache_key("tenant-a", "prop-001", 2024, 4)

    assert sunset_key == "revenue:tenant:tenant-a:property:prop-001:year:2024:month:03"
    assert sunset_key != ocean_key
    assert sunset_key != april_key


def test_cached_entry_rejects_cross_tenant_payload():
    cached = {
        "tenant_id": "tenant-a",
        "property_id": "prop-001",
        "month": 3,
        "year": 2024,
        "total": "2250.00",
    }
    assert cached_entry_matches(cached, "tenant-a", "prop-001", 3, 2024)
    assert not cached_entry_matches(cached, "tenant-b", "prop-001", 3, 2024)


@pytest.mark.asyncio
async def test_cache_does_not_leak_sunset_totals_to_ocean(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(cache_service, "redis_client", fake_redis)

    calls = []

    async def fake_calculate(property_id, tenant_id, month, year):
        calls.append(tenant_id)
        if tenant_id == "tenant-a":
            return {
                "property_id": property_id,
                "tenant_id": tenant_id,
                "total": "2250.00",
                "currency": "USD",
                "count": 4,
                "month": month,
                "year": year,
            }
        return {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "total": "0.00",
            "currency": "USD",
            "count": 0,
            "month": month,
            "year": year,
        }

    monkeypatch.setattr(cache_service, "calculate_monthly_revenue", fake_calculate)

    sunset = await get_revenue_summary("prop-001", "tenant-a", 3, 2024)
    ocean = await get_revenue_summary("prop-001", "tenant-b", 3, 2024)
    sunset_again = await get_revenue_summary("prop-001", "tenant-a", 3, 2024)

    assert sunset["total"] == "2250.00"
    assert ocean["total"] == "0.00"
    assert ocean["tenant_id"] == "tenant-b"
    assert sunset_again["total"] == "2250.00"
    assert calls == ["tenant-a", "tenant-b"]
    assert json.loads(fake_redis.store[revenue_cache_key("tenant-a", "prop-001", 2024, 3)])["tenant_id"] == "tenant-a"
    assert json.loads(fake_redis.store[revenue_cache_key("tenant-b", "prop-001", 2024, 3)])["tenant_id"] == "tenant-b"
