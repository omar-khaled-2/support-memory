import pytest
from app.config import Settings, get_settings


def test_settings_defaults():
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.rabbitmq_url.startswith("amqp://")
    assert settings.app_host == "0.0.0.0"
    assert settings.app_port == 8000


def test_get_settings_cached():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
