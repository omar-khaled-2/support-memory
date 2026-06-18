from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/ingest"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    publish_interval_seconds: float = 5.0

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
