"""Cache-aside layer for app/services/report_service.py — PHASE_4_PLAN.md
§6. A 60-second TTL in front of a normal indexed query, not a Celery
precompute job: at this repo's actual data volume a live GROUP BY runs
in single digits of milliseconds, so the cache exists to avoid
*repeating* that work on every dashboard poll, not because the query
itself is heavy. Deliberately no write-invalidation — see §6 for why.

The one place a bug here would leak data across tenants or roles is the
cache key, so scope_key is its own small, directly-testable function
rather than inlined string formatting at each call site.
"""

import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from app.core.redis import get_redis_client

REPORT_CACHE_TTL_SECONDS = 60


def scope_key(owner_ids: list[uuid.UUID] | None) -> str:
    """None (Admin, unrestricted) gets its own fixed sentinel — never
    confusable with any real owner_ids combination, since a real one is
    always a hash of concrete UUIDs."""
    if owner_ids is None:
        return "admin"
    joined = ",".join(sorted(str(i) for i in owner_ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


async def get_or_compute(
    tenant_id: uuid.UUID,
    report_type: str,
    owner_ids: list[uuid.UUID] | None,
    compute_fn: Callable[[], Awaitable[Any]],
) -> tuple[Any, str]:
    """Returns (value, cached_at_iso). compute_fn is only called on a
    cache miss."""
    key = f"report:{tenant_id}:{report_type}:{scope_key(owner_ids)}"
    redis = get_redis_client()
    try:
        cached = await redis.get(key)
        if cached is not None:
            envelope = json.loads(cached)
            return envelope["value"], envelope["cached_at"]

        value = await compute_fn()
        cached_at = datetime.now(UTC).isoformat()
        await redis.set(
            key, json.dumps({"value": value, "cached_at": cached_at}), ex=REPORT_CACHE_TTL_SECONDS
        )
        return value, cached_at
    finally:
        await redis.aclose()
