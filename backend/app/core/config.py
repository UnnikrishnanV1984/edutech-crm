from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "info"

    # crm_app role — runtime queries only, no DDL, no BYPASSRLS.
    database_app_url: str
    redis_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
