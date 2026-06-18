import pytest
from httpx import Request, Response

from app.services.memory_client import fetch_active_facts, fetch_beliefs, fetch_briefing


class _FakeClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, *args, **kwargs):
        return self._response


def _response(payload):
    return Response(200, json=payload, request=Request("GET", "http://memory"))


@pytest.mark.asyncio
async def test_fetch_active_facts(monkeypatch):
    payload = [
        {
            "entity_id": "acct_1",
            "attribute": "account_name",
            "value": "Helios",
            "status": "active",
        }
    ]
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *args, **kwargs: _FakeClient(_response(payload)),
    )

    facts = await fetch_active_facts()
    assert facts == payload


@pytest.mark.asyncio
async def test_fetch_briefing(monkeypatch):
    payload = {
        "entity_id": "acct_1",
        "account_name": "Helios",
        "active_plan": "Enterprise",
    }
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *args, **kwargs: _FakeClient(_response(payload)),
    )

    briefing = await fetch_briefing("acct_1")
    assert briefing == payload


@pytest.mark.asyncio
async def test_fetch_beliefs(monkeypatch):
    payload = {
        "entity_id": "acct_1",
        "beliefs": {"plan": "Enterprise"},
        "warnings": [],
    }
    monkeypatch.setattr(
        "httpx.AsyncClient",
        lambda *args, **kwargs: _FakeClient(_response(payload)),
    )

    beliefs = await fetch_beliefs("acct_1")
    assert beliefs == payload
