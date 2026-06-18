import pytest


@pytest.mark.asyncio
async def test_process_events_endpoint(client):
    response = await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2001",
                "entity_type": "account",
                "entity_id": "acct_api_1",
                "payload": {"plan": "Starter"},
                "reliability": "high",
            }
        ],
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["event_id"] == "evt-2001"
    assert data[0]["facts_extracted"] == 1


@pytest.mark.asyncio
async def test_read_beliefs_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2002",
                "entity_type": "account",
                "entity_id": "acct_api_2",
                "payload": {"plan": "Pro"},
                "reliability": "high",
            }
        ],
    )
    response = await client.get("/api/v1/entities/acct_api_2/beliefs")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == "acct_api_2"
    assert data["beliefs"]["plan"]["value"] == "Pro"


@pytest.mark.asyncio
async def test_create_snapshot_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2003",
                "entity_type": "account",
                "entity_id": "acct_api_3",
                "payload": {"region": "Cairo"},
                "reliability": "medium",
            }
        ],
    )
    response = await client.post("/api/v1/entities/acct_api_3/snapshots")
    assert response.status_code == 200
    data = response.json()
    assert data["entity_id"] == "acct_api_3"
    assert "Cairo" in data["context_json"]


@pytest.mark.asyncio
async def test_read_snapshots_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2004",
                "entity_type": "account",
                "entity_id": "acct_api_4",
                "payload": {"plan": "Enterprise"},
                "reliability": "high",
            }
        ],
    )
    await client.post("/api/v1/entities/acct_api_4/snapshots")
    response = await client.get("/api/v1/entities/acct_api_4/snapshots")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_read_facts_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2005",
                "entity_type": "account",
                "entity_id": "acct_api_5",
                "payload": {"tier": "premium"},
                "reliability": "high",
            }
        ],
    )
    response = await client.get("/api/v1/facts?entity_id=acct_api_5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["attribute"] == "tier"


@pytest.mark.asyncio
async def test_read_conflicts_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2006",
                "entity_type": "account",
                "entity_id": "acct_api_6",
                "payload": {"region": "Cairo"},
                "reliability": "high",
            },
            {
                "event_id": "evt-2007",
                "entity_type": "account",
                "entity_id": "acct_api_6",
                "payload": {"region": "Alexandria"},
                "reliability": "high",
            },
        ],
    )
    response = await client.get("/api/v1/conflicts?entity_id=acct_api_6")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1


@pytest.mark.asyncio
async def test_read_ambiguities_endpoint(client):
    await client.post(
        "/api/v1/events/process",
        json=[
            {
                "event_id": "evt-2008",
                "entity_type": "account",
                "entity_id": "acct_api_7",
                "payload": {"email": "shared@example.com"},
                "reliability": "high",
            },
            {
                "event_id": "evt-2009",
                "entity_type": "account",
                "entity_id": "acct_api_8",
                "payload": {"email": "shared@example.com"},
                "reliability": "high",
            },
        ],
    )
    response = await client.get("/api/v1/ambiguities")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["entity_count"] == 2
