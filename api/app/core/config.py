"""Single source of truth for environment configuration.

Every environment variable the app reads must be declared here and
documented in `.env.example` at the repo root.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    debug: bool = True

    # Data layer
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "greenroom"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    jwt_secret_key: str = "dev-secret-change-me-32-bytes-min!!"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # LLM / embeddings / search providers (Section 6 interfaces)
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    tavily_api_key: str = ""

    # LLM tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = False

    # Outbound channels (added post-Phase-0-plan per PLAN.md Section 7 addendum)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_sms_number: str = ""

    # CORS
    cors_allow_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
