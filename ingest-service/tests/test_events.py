import pytest
from httpx import AsyncClient


BASE_EVENT = {
    "idempotency_key": "idem-1001",
    "occurred_at": "2026-04-01T09:00:00Z",
    "source": "crm",
    "actor": "system",
    "entity_type": "account",
    "entity_id": "acct_helios_269",
    "related_entity_ids": [],
    "reliability": "medium",
    "text": "Account created: Helios Apps",
    "payload": {"account_name": "Helios Apps"},
}


@pytest.mark.asyncio
async def test_create_event(client: AsyncClient):
    response = await client.post("/api/v1/events", json=[BASE_EVENT])
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["status"] == "created"
    assert data[0]["idempotency_key"] == "idem-1001"
    assert data[0]["event_id"].startswith("evt-")


@pytest.mark.asyncio
async def test_duplicate_event(client: AsyncClient):
    await client.post("/api/v1/events", json=[BASE_EVENT])
    response = await client.post("/api/v1/events", json=[BASE_EVENT])
    assert response.status_code == 200
    data = response.json()
    assert data[0]["status"] == "duplicate"


@pytest.mark.asyncio
async def test_conflict_event(client: AsyncClient):
    await client.post("/api/v1/events", json=[BASE_EVENT])
    conflict_event = {**BASE_EVENT, "entity_id": "acct_other_269", "payload": {"different": True}}
    response = await client.post("/api/v1/events", json=[conflict_event])
    assert response.status_code == 200
    data = response.json()
    assert data[0]["status"] == "conflict"


@pytest.mark.asyncio
async def test_get_event(client: AsyncClient):
    create_response = await client.post("/api/v1/events", json=[BASE_EVENT])
    event_id = create_response.json()[0]["event_id"]

    response = await client.get(f"/api/v1/events/{event_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == event_id
    assert data["idempotency_key"] == "idem-1001"


@pytest.mark.asyncio
async def test_get_event_not_found(client: AsyncClient):
    response = await client.get("/api/v1/events/evt-missing")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_batch_mixed_results(client: AsyncClient):
    events = [
        BASE_EVENT,
        {**BASE_EVENT, "idempotency_key": "idem-new", "entity_id": "acct_new"},
        {**BASE_EVENT, "idempotency_key": "idem-new", "entity_id": "acct_conflict", "payload": {"x": 1}},
    ]
    response = await client.post("/api/v1/events", json=events)
    assert response.status_code == 200
    data = response.json()
    assert data[0]["status"] == "created"
    assert data[1]["status"] == "created"
    assert data[2]["status"] == "conflict"


@pytest.mark.asyncio
async def test_validation_rejects_missing_field(client: AsyncClient):
    invalid = {**BASE_EVENT}
    del invalid["source"]
    response = await client.post("/api/v1/events", json=[invalid])
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_validation_rejects_invalid_reliability(client: AsyncClient):
    invalid = {**BASE_EVENT, "reliability": "critical"}
    response = await client.post("/api/v1/events", json=[invalid])
    assert response.status_code == 422
