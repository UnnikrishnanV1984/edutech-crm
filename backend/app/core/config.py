from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "info"

    # crm_app role — runtime queries only, no DDL, no BYPASSRLS.
    database_app_url: str
    redis_url: str

    # S3/MinIO — presigned URLs only, the backend never proxies file bytes.
    s3_endpoint: str
    s3_bucket: str
    s3_access_key: str
    s3_secret_key: str

    # Lead-capture integrations (PHASE_2_PLAN.md). Base URLs default to the
    # local mock-integrations service — swapping to a real platform is a
    # config change only, same principle as s3_endpoint/MinIO above.
    integration_credentials_key: str
    meta_graph_api_base_url: str = "http://mock-integrations:8000/meta"
    meta_app_secret: str = "dev-meta-app-secret"
    meta_webhook_verify_token: str = "dev-meta-verify-token"
    whatsapp_api_base_url: str = "http://mock-integrations:8000/whatsapp"
    whatsapp_app_secret: str = "dev-whatsapp-app-secret"
    whatsapp_webhook_verify_token: str = "dev-whatsapp-verify-token"
    google_ads_api_base_url: str = "http://mock-integrations:8000/google"
    google_oauth_client_id: str = "dev-google-client-id"
    google_oauth_client_secret: str = "dev-google-client-secret"
    web_form_rate_limit_per_minute: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
