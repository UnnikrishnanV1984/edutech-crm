import os

# Set required env vars before any app module is imported, so
# get_settings() doesn't fail during collection.
os.environ.setdefault("DATABASE_APP_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "warning")
