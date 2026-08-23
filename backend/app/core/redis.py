import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Lazy singleton, mirroring app/core/s3.py's pattern — for code
    running outside the FastAPI app lifecycle (app.state.redis), such as
    the seed-data connector runner (python -m app.connectors.seed_runner)."""
    global _client
    if _client is None:
        _client = redis.from_url(get_settings().redis_url)
    return _client
