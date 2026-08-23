import redis.asyncio as redis

from app.core.config import get_settings


def get_redis_client() -> redis.Redis:
    """A fresh client per call, not a cached singleton like app/core/s3.py's
    boto3 client — redis.asyncio connections are bound to the event loop
    that first uses them, and this is called from short-lived script
    contexts (app/connectors/seed_runner.py, and each pytest-asyncio test
    gets its own event loop) where a process-wide singleton would end up
    reused across loops and break. from_url() does no I/O until the first
    command, so this is cheap."""
    return redis.from_url(get_settings().redis_url)
