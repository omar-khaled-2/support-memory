import pytest

from app.services.llm_client import generate_answer
from app.config import Settings


class _FakeMessage:
    content = " LLM answer "


class _FakeChoice:
    message = _FakeMessage()


class _FakeCompletion:
    choices = [_FakeChoice()]


class _FakeCompletions:
    async def create(self, *args, **kwargs):
        return _FakeCompletion()


class _FakeOpenAI:
    def __init__(self, *args, **kwargs):
        self.chat = type("Chat", (), {"completions": _FakeCompletions()})()


@pytest.mark.asyncio
async def test_generate_answer_with_openai(monkeypatch):
    monkeypatch.setattr("app.services.llm_client.AsyncOpenAI", _FakeOpenAI)
    monkeypatch.setattr(
        "app.services.llm_client.get_settings",
        lambda: Settings(openai_api_key="sk-test"),
    )

    answer = await generate_answer("What is the plan?", {"briefing": {}})
    assert answer == "LLM answer"


@pytest.mark.asyncio
async def test_generate_answer_fallback_without_key(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_client.get_settings",
        lambda: Settings(openai_api_key=""),
    )

    context = {
        "briefing": {
            "account_name": "Helios",
            "active_plan": "Enterprise",
            "region": "Berlin",
            "tier": "Platinum",
            "warnings": ["Shared identity"],
        },
        "beliefs": {"plan": "Enterprise"},
        "warnings": ["Low confidence"],
    }
    answer = await generate_answer("What should I know?", context)
    assert "Helios" in answer
    assert "Enterprise" in answer
    assert "Berlin" in answer
    assert "Shared identity" in answer
    assert "Low confidence" in answer


@pytest.mark.asyncio
async def test_generate_answer_fallback_empty_context(monkeypatch):
    monkeypatch.setattr(
        "app.services.llm_client.get_settings",
        lambda: Settings(openai_api_key=""),
    )

    answer = await generate_answer("What should I know?", {})
    assert answer == "No relevant context found."
