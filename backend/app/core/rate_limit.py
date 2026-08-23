"""Defense-in-depth rate limiting for the one fully public, unauthenticated
endpoint in this codebase (POST /webhooks/web) — API_CONVENTIONS.md §8
notes primary enforcement lives at the BFF, but this route bypasses the
BFF entirely (PHASE_2_PLAN.md §3), so it needs its own. Fixed-window
counter in Redis, keyed by the caller-supplied key (the embed key — see
app/webhooks/web.py) rather than IP, since a shared NAT shouldn't share
one tenant's quota with another's embedded form."""

import time

from app.core.errors import RATE_LIMITED, ApiError
from app.core.redis import get_redis_client


async def enforce_rate_limit(key: str, limit_per_minute: int) -> None:
    redis = get_redis_client()
    try:
        bucket = f"ratelimit:{key}:{int(time.time() // 60)}"
        count = await redis.incr(bucket)
        if count == 1:
            await redis.expire(bucket, 60)
        if count > limit_per_minute:
            raise ApiError(429, RATE_LIMITED, "Too many submissions — try again shortly")
    finally:
        await redis.aclose()
