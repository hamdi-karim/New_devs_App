import json
import os
from typing import Any, Dict

import redis.asyncio as redis

from app.services import reservations
from app.services.revenue_rules import revenue_cache_key

# Initialize Redis client (typically configured centrally).
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

REVENUE_CACHE_TTL_SECONDS = 300


async def get_revenue_summary(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """Revenue summary for one tenant's property, cached for 5 minutes.

    The key includes the tenant because property IDs are only unique per
    tenant. Exceptions from the calculator propagate, so errors are never cached.
    """
    cache_key = revenue_cache_key(tenant_id, property_id)

    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    result = await reservations.calculate_total_revenue(property_id, tenant_id)

    await redis_client.setex(cache_key, REVENUE_CACHE_TTL_SECONDS, json.dumps(result))
    return result
