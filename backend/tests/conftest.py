import os

# Set required env vars before any app module is imported, so
# get_settings() doesn't fail during collection.
os.environ.setdefault("DATABASE_APP_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("LOG_LEVEL", "warning")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_BUCKET", "crm-documents-test")
os.environ.setdefault("S3_ACCESS_KEY", "test-access-key")
os.environ.setdefault("S3_SECRET_KEY", "test-secret-key")
os.environ.setdefault("INTEGRATION_CREDENTIALS_KEY", "test-integration-credentials-key")
os.environ.setdefault("META_APP_SECRET", "test-meta-app-secret")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-whatsapp-app-secret")
os.environ.setdefault("META_GRAPH_API_BASE_URL", "http://localhost:8010/meta")
os.environ.setdefault("WHATSAPP_API_BASE_URL", "http://localhost:8010/whatsapp")
os.environ.setdefault("GOOGLE_ADS_API_BASE_URL", "http://localhost:8010/google")
