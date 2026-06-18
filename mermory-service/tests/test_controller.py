import pytest

from app.controllers.memory_controller import (
    _extract_facts_from_event,
    _extract_facts_from_payload,
    _reliability_to_confidence,
    build_snapshot,
    detect_ambiguous_identities,
    get_beliefs,
    get_conflicts,
    get_facts,
    process_event,
)
from app.schemas.memory import EventIn


def test_reliability_to_confidence():
    assert _reliability_to_confidence("high") == 1.0
    assert _reliability_to_confidence("medium") == 0.75
    assert _reliability_to_confidence("low") == 0.5
    assert _reliability_to_confidence("unknown") == 0.75


def test_extract_facts_from_payload():
    event = EventIn(
        event_id="evt-1",
        entity_type="account",
        entity_id="acct_1",
        payload={"plan": "Starter", "region": "Cairo"},
        reliability="high",
    )
    facts = _extract_facts_from_payload(event)
    assert len(facts) == 2
    assert {f["attribute"] for f in facts} == {"plan", "region"}


@pytest.mark.asyncio
async def test_extract_facts_from_event_without_api_key():
    event = EventIn(
        event_id="evt-1",
        entity_type="account",
        entity_id="acct_1",
        payload={"plan": "Starter"},
        text="The account is on the Starter plan.",
        reliability="high",
    )
    facts = await _extract_facts_from_event(event)
    assert len(facts) == 1
    assert facts[0]["attribute"] == "plan"
    assert facts[0]["value"] == "Starter"


@pytest.mark.asyncio
async def test_process_event_extracts_facts(db_session):
    event = EventIn(
        event_id="evt-1001",
        entity_type="account",
        entity_id="acct_helios_269",
        payload={"plan": "Starter"},
        reliability="high",
    )
    result = await process_event(db_session, event)
    assert result.event_id == "evt-1001"
    assert result.facts_extracted == 1
    assert result.conflicts_detected == 0
    assert result.snapshot_id is not None

    facts = await get_facts(db_session, entity_id="acct_helios_269")
    assert len(facts) == 1
    assert facts[0].attribute == "plan"
    assert facts[0].value == "Starter"
    assert facts[0].status == "active"


@pytest.mark.asyncio
async def test_process_event_detects_contradiction(db_session):
    event1 = EventIn(
        event_id="evt-1001",
        entity_type="account",
        entity_id="acct_1",
        payload={"region": "Cairo"},
        reliability="high",
    )
    event2 = EventIn(
        event_id="evt-1002",
        entity_type="account",
        entity_id="acct_1",
        payload={"region": "Alexandria"},
        reliability="high",
    )
    await process_event(db_session, event1)
    result = await process_event(db_session, event2)

    assert result.conflicts_detected == 1

    facts = await get_facts(db_session, entity_id="acct_1")
    assert len(facts) == 2
    assert any(f.status == "superseded" for f in facts)
    assert any(f.status == "active" and f.value == "Alexandria" for f in facts)

    conflicts = await get_conflicts(db_session, entity_id="acct_1")
    assert len(conflicts) == 1
    assert "Cairo" in conflicts[0].description
    assert "Alexandria" in conflicts[0].description


@pytest.mark.asyncio
async def test_build_snapshot_aggregates_active_facts(db_session):
    event = EventIn(
        event_id="evt-1003",
        entity_type="account",
        entity_id="acct_2",
        payload={"plan": "Pro", "region": "Berlin"},
        reliability="medium",
    )
    await process_event(db_session, event)
    snapshot = await build_snapshot(db_session, "acct_2")

    assert snapshot.entity_id == "acct_2"
    assert "Pro" in snapshot.context_json
    assert "Berlin" in snapshot.context_json


@pytest.mark.asyncio
async def test_get_beliefs_returns_active_facts(db_session):
    event = EventIn(
        event_id="evt-1004",
        entity_type="account",
        entity_id="acct_3",
        payload={"plan": "Enterprise"},
        reliability="high",
    )
    await process_event(db_session, event)
    beliefs = await get_beliefs(db_session, "acct_3")

    assert beliefs["entity_id"] == "acct_3"
    assert beliefs["entity_type"] == "account"
    assert beliefs["beliefs"]["plan"]["value"] == "Enterprise"
    assert beliefs["beliefs"]["plan"]["confidence"] == 1.0


@pytest.mark.asyncio
async def test_detect_ambiguous_identities(db_session):
    event1 = EventIn(
        event_id="evt-1005",
        entity_type="account",
        entity_id="acct_a",
        payload={"email": "user@example.com"},
        reliability="high",
    )
    event2 = EventIn(
        event_id="evt-1006",
        entity_type="account",
        entity_id="acct_b",
        payload={"email": "user@example.com"},
        reliability="high",
    )
    await process_event(db_session, event1)
    await process_event(db_session, event2)

    ambiguities = await detect_ambiguous_identities(db_session)
    assert len(ambiguities) == 1
    assert ambiguities[0]["attribute"] == "email"
    assert ambiguities[0]["entity_count"] == 2


@pytest.mark.asyncio
async def test_detect_ambiguous_identities_empty(db_session):
    ambiguities = await detect_ambiguous_identities(db_session)
    assert ambiguities == []


@pytest.mark.asyncio
async def test_process_event_no_payload_creates_empty_snapshot(db_session):
    event = EventIn(
        event_id="evt-1007",
        entity_type="account",
        entity_id="acct_4",
        payload={},
        reliability="low",
    )
    result = await process_event(db_session, event)
    assert result.facts_extracted == 0
    assert result.snapshot_id is None


@pytest.mark.asyncio
async def test_get_facts_filter_by_status(db_session):
    event1 = EventIn(
        event_id="evt-1008",
        entity_type="account",
        entity_id="acct_5",
        payload={"region": "Cairo"},
        reliability="high",
    )
    event2 = EventIn(
        event_id="evt-1009",
        entity_type="account",
        entity_id="acct_5",
        payload={"region": "Alexandria"},
        reliability="high",
    )
    await process_event(db_session, event1)
    await process_event(db_session, event2)

    active = await get_facts(db_session, entity_id="acct_5", status="active")
    superseded = await get_facts(db_session, entity_id="acct_5", status="superseded")
    assert len(active) == 1
    assert len(superseded) == 1
