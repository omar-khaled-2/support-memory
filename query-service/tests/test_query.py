import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _patch_controller_deps(monkeypatch):
    async def fake_facts():
        return [
            {
                "entity_id": "acct_api_9",
                "attribute": "account_name",
                "value": "Helios Apps",
                "status": "active",
            }
        ]

    async def fake_briefing(entity_id):
        return {
            "entity_id": entity_id,
            "entity_type": "account",
            "account_name": "Helios Apps",
            "active_plan": "Enterprise",
            "region": "Berlin",
            "tier": "Platinum",
            "warnings": ["Identity attribute shared with other entities"],
        }

    async def fake_beliefs(entity_id):
        return {
            "entity_id": entity_id,
            "entity_type": "account",
            "beliefs": {
                "account_name": "Helios Apps",
                "plan": "Enterprise",
                "region": "Berlin",
            },
            "warnings": [],
        }

    async def fake_llm(question, context):
        return "Helios is on the Enterprise plan in Berlin."

    monkeypatch.setattr(
        "app.controllers.query_controller.fetch_active_facts", fake_facts
    )
    monkeypatch.setattr(
        "app.controllers.query_controller.fetch_briefing", fake_briefing
    )
    monkeypatch.setattr("app.controllers.query_controller.fetch_beliefs", fake_beliefs)
    monkeypatch.setattr("app.controllers.query_controller.generate_answer", fake_llm)


@pytest.mark.asyncio
async def test_query_resolves_entity_and_returns_answer(client):
    response = await client.post(
        "/api/v1/query",
        json={"question": "What should the support rep know before calling Helios?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == "acct_api_9"
    assert "Helios" in data["answer"]
    assert "context" in data


@pytest.mark.asyncio
async def test_query_uses_explicit_entity_id(client):
    response = await client.post(
        "/api/v1/query",
        json={
            "question": "What is the plan?",
            "entity_id": "acct_api_9",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == "acct_api_9"


@pytest.mark.asyncio
async def test_query_returns_error_when_entity_unknown(client, monkeypatch):
    async def empty_facts():
        return []

    monkeypatch.setattr(
        "app.controllers.query_controller.fetch_active_facts", empty_facts
    )

    response = await client.post(
        "/api/v1/query",
        json={"question": "What should we know about UnknownCo?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] is None
    assert "Please provide an explicit entity_id" in data["answer"]
