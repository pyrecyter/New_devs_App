import json
import logging
import os
from typing import Any, Dict, Optional

import redis.asyncio as redis

from app.services.reservations import calculate_monthly_revenue

logger = logging.getLogger(__name__)

redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

CACHE_TTL_SECONDS = 300


def revenue_cache_key(tenant_id: str, property_id: str, year: int, month: int) -> str:
    return f"revenue:tenant:{tenant_id}:property:{property_id}:year:{year}:month:{month:02d}"


def _decode_cached(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    return data if isinstance(data, dict) else None


def cached_entry_matches(
    cached: Dict[str, Any],
    tenant_id: str,
    property_id: str,
    month: int,
    year: int,
) -> bool:
    return (
        cached.get("tenant_id") == tenant_id
        and cached.get("property_id") == property_id
        and int(cached.get("month", -1)) == month
        and int(cached.get("year", -1)) == year
    )


async def get_revenue_summary(
    property_id: str,
    tenant_id: str,
    month: int,
    year: int,
) -> Dict[str, Any]:
    """
    Fetch a monthly revenue summary with a tenant-scoped cache key.
    """
    cache_key = revenue_cache_key(tenant_id, property_id, year, month)

    try:
        cached = _decode_cached(await redis_client.get(cache_key))
        if cached and cached_entry_matches(cached, tenant_id, property_id, month, year):
            return cached
    except Exception as exc:
        logger.warning(f"Revenue cache read failed for {cache_key}: {exc}")

    result = await calculate_monthly_revenue(property_id, tenant_id, month, year)

    try:
        await redis_client.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(result))
    except Exception as exc:
        logger.warning(f"Revenue cache write failed for {cache_key}: {exc}")

    return result
