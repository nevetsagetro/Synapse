from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Synapse"
    database_url: str = "sqlite:///./synapse.db"
    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    frontend_port: int = 3000
    gemini_api_key: str | None = None

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
