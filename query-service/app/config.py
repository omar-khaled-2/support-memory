from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_host: str = "0.0.0.0"
    app_port: int = 8002
    memory_service_url: str = "http://memory:8001/api/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"
    openai_temperature: float = 0.0

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
