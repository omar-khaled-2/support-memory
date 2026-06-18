from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/memory"
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    consume_interval_seconds: float = 5.0
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-nano"
    openai_temperature: float = 0.0
    source_weights: str = "billing=3,salesforce=3,crm=2,support=1,chat=0"

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def source_weight_map(self) -> dict:
        weights = {}
        for token in self.source_weights.split(","):
            if "=" in token:
                source, weight = token.split("=", 1)
                try:
                    weights[source.strip()] = int(weight.strip())
                except ValueError:
                    continue
        return weights


@lru_cache
def get_settings() -> Settings:
    return Settings()
