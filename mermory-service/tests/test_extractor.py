import json

import pytest

from app.services.extractor import LLMFactExtractor, get_extractor


def test_get_extractor_singleton():
    extractor1 = get_extractor()
    extractor2 = get_extractor()
    assert extractor1 is extractor2
    assert isinstance(extractor1, LLMFactExtractor)


def test_extractor_without_api_key_returns_empty():
    extractor = LLMFactExtractor(api_key="")
    assert extractor.api_key == ""


@pytest.mark.asyncio
async def test_extractor_parses_json_response():
    extractor = LLMFactExtractor(api_key="test-key", model="test-model")

    class FakeChoice:
        message = type("Message", (), {"content": '[{"attribute": "plan", "value": "Starter", "confidence": 0.9}]'})()

    class FakeCompletion:
        choices = [FakeChoice()]

    async def fake_create(*args, **kwargs):
        return FakeCompletion()

    extractor._client = type("FakeClient", (), {
        "chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": fake_create
            })()
        })()
    })()

    facts = await extractor.extract_facts(
        entity_type="account",
        entity_id="acct_1",
        payload={},
        text="The plan is Starter.",
    )

    assert len(facts) == 1
    assert facts[0]["attribute"] == "plan"
    assert facts[0]["value"] == "Starter"
    assert facts[0]["confidence"] == 0.9


@pytest.mark.asyncio
async def test_extractor_strips_code_blocks():
    extractor = LLMFactExtractor(api_key="test-key")

    class FakeChoice:
        message = type("Message", (), {"content": '```json\n[{"attribute": "region", "value": "Cairo", "confidence": 0.8}]\n```'})()

    class FakeCompletion:
        choices = [FakeChoice()]

    async def fake_create(*args, **kwargs):
        return FakeCompletion()

    extractor._client = type("FakeClient", (), {
        "chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": fake_create
            })()
        })()
    })()

    facts = await extractor.extract_facts(
        entity_type="account",
        entity_id="acct_1",
        payload={},
        text="Region is Cairo.",
    )

    assert len(facts) == 1
    assert facts[0]["attribute"] == "region"


@pytest.mark.asyncio
async def test_extractor_ignores_invalid_json():
    extractor = LLMFactExtractor(api_key="test-key")

    class FakeChoice:
        message = type("Message", (), {"content": "not valid json"})()

    class FakeCompletion:
        choices = [FakeChoice()]

    async def fake_create(*args, **kwargs):
        return FakeCompletion()

    extractor._client = type("FakeClient", (), {
        "chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": fake_create
            })()
        })()
    })()

    facts = await extractor.extract_facts(
        entity_type="account",
        entity_id="acct_1",
        payload={},
        text="...",
    )
    assert facts == []


@pytest.mark.asyncio
async def test_extractor_skips_facts_missing_required_fields():
    extractor = LLMFactExtractor(api_key="test-key")

    class FakeChoice:
        message = type("Message", (), {"content": '[{"attribute": "plan"}, {"attribute": "region", "value": "Cairo"}]'})()

    class FakeCompletion:
        choices = [FakeChoice()]

    async def fake_create(*args, **kwargs):
        return FakeCompletion()

    extractor._client = type("FakeClient", (), {
        "chat": type("Chat", (), {
            "completions": type("Completions", (), {
                "create": fake_create
            })()
        })()
    })()

    facts = await extractor.extract_facts(
        entity_type="account",
        entity_id="acct_1",
        payload={},
        text="...",
    )
    assert len(facts) == 1
    assert facts[0]["attribute"] == "region"
