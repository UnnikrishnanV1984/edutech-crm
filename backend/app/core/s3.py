import boto3
from botocore.client import Config

from app.core.config import get_settings

_client = None


def get_s3_client():
    """Lazy singleton — boto3 client construction does no network I/O, but
    building it fresh per-request would be wasteful. Presigned-URL
    generation itself is a local HMAC computation, not a network call, so
    this is safe to use from async route handlers without a thread pool."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _client
