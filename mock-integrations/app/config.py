from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Same values backend verifies against — PHASE_2_PLAN.md §4.4:
    # signing here with the real secret genuinely exercises backend's
    # verification code path instead of bypassing it.
    meta_app_secret: str = "dev-meta-app-secret"
    whatsapp_app_secret: str = "dev-whatsapp-app-secret"
    backend_base_url: str = "http://backend:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
