import pytest

from app.controllers.memory_controller import (
    SENSITIVE_ATTRIBUTES,
    _extract_facts_from_event,
    _extract_facts_from_payload,
    _reliability_to_confidence,
    _source_weight,
    build_digest,
    build_snapshot,
    detect_ambiguous_identities,
    get_beliefs,
    get_conflicts,
    get_facts,
    get_pre_call_briefing,
    process_event,
)
from app.schemas.memory import EventIn


def test_reliability_to_confidence():
    assert _reliability_to_confidence("high") == 1.0
    assert _reliability_to_confidence("medium") == 0.75
    assert _reliability_to_confidence("low") == 0.5
    assert _reliability_to_confidence("unknown") == 0.75


def test_source_weight_defaults():
    assert _source_weight("billing") > _source_weight("chat")
    assert _source_weight("unknown") == 0


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
        source="crm",
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
    assert facts[0].source == "crm"


@pytest.mark.asyncio
async def test_process_event_detects_contradiction(db_session):
    event1 = EventIn(
        event_id="evt-1001",
        entity_type="account",
        entity_id="acct_1",
        payload={"region": "Cairo"},
        reliability="high",
        source="support",
    )
    event2 = EventIn(
        event_id="evt-1002",
        entity_type="account",
        entity_id="acct_1",
        payload={"region": "Alexandria"},
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event1)
    result = await process_event(db_session, event2)

    assert result.conflicts_detected == 0

    facts = await get_facts(db_session, entity_id="acct_1")
    assert any(f.status == "superseded" and f.value == "Cairo" for f in facts)
    assert any(f.status == "active" and f.value == "Alexandria" for f in facts)

    conflicts = await get_conflicts(db_session, entity_id="acct_1")
    assert len(conflicts) == 1
    assert "billing" in conflicts[0].description


@pytest.mark.asyncio
async def test_process_event_retains_higher_authority_fact(db_session):
    event1 = EventIn(
        event_id="evt-1001",
        entity_type="account",
        entity_id="acct_retained",
        payload={"plan": "Enterprise"},
        reliability="high",
        source="billing",
    )
    event2 = EventIn(
        event_id="evt-1002",
        entity_type="account",
        entity_id="acct_retained",
        payload={"plan": "Starter"},
        reliability="high",
        source="chat",
    )
    await process_event(db_session, event1)
    result = await process_event(db_session, event2)

    assert result.conflicts_detected == 1

    facts = await get_facts(db_session, entity_id="acct_retained")
    assert any(f.status == "active" and f.value == "Enterprise" for f in facts)
    assert not any(f.value == "Starter" for f in facts)


@pytest.mark.asyncio
async def test_build_snapshot_aggregates_active_facts(db_session):
    event = EventIn(
        event_id="evt-1003",
        entity_type="account",
        entity_id="acct_2",
        payload={"plan": "Pro", "region": "Berlin"},
        reliability="medium",
        source="crm",
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
        source="billing",
    )
    await process_event(db_session, event)
    beliefs = await get_beliefs(db_session, "acct_3")

    assert beliefs["entity_id"] == "acct_3"
    assert beliefs["entity_type"] == "account"
    assert beliefs["beliefs"]["plan"]["value"] == "Enterprise"
    assert beliefs["beliefs"]["plan"]["confidence"] == 1.0
    assert beliefs["beliefs"]["plan"]["source"] == "billing"


@pytest.mark.asyncio
async def test_sensitive_attributes_hidden_by_default(db_session):
    event = EventIn(
        event_id="evt-sens",
        entity_type="account",
        entity_id="acct_sensitive",
        payload={"sla": "platinum", "plan": "Pro"},
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event)
    facts = await get_facts(db_session, entity_id="acct_sensitive")
    assert {f.attribute for f in facts} == {"plan"}

    beliefs = await get_beliefs(db_session, "acct_sensitive")
    assert "sla" not in beliefs["beliefs"]
    assert "Sensitive account-specific facts exist" in beliefs["warnings"][0]


@pytest.mark.asyncio
async def test_sensitive_attributes_visible_when_scoped(db_session):
    event = EventIn(
        event_id="evt-sens-scoped",
        entity_type="account",
        entity_id="acct_sensitive_scoped",
        payload={"sla": "platinum", "plan": "Pro"},
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event)
    facts = await get_facts(
        db_session, entity_id="acct_sensitive_scoped", include_sensitive=True
    )
    assert {f.attribute for f in facts} == {"plan", "sla"}


@pytest.mark.asyncio
async def test_detect_ambiguous_identities(db_session):
    event1 = EventIn(
        event_id="evt-1005",
        entity_type="account",
        entity_id="acct_a",
        payload={"email": "user@example.com"},
        reliability="high",
        source="crm",
    )
    event2 = EventIn(
        event_id="evt-1006",
        entity_type="account",
        entity_id="acct_b",
        payload={"email": "user@example.com"},
        reliability="high",
        source="crm",
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
        source="chat",
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
        source="chat",
    )
    event2 = EventIn(
        event_id="evt-1009",
        entity_type="account",
        entity_id="acct_5",
        payload={"region": "Alexandria"},
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event1)
    await process_event(db_session, event2)

    active = await get_facts(db_session, entity_id="acct_5", status="active")
    superseded = await get_facts(db_session, entity_id="acct_5", status="superseded")
    assert len(active) == 1
    assert len(superseded) == 1


@pytest.mark.asyncio
async def test_pre_call_briefing(db_session):
    event = EventIn(
        event_id="evt-brief",
        entity_type="account",
        entity_id="acct_brief",
        payload={
            "account_name": "Helios Apps",
            "plan": "Enterprise",
            "region": "Berlin",
            "tier": "Platinum",
            "email": "shared@example.com",
        },
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event)

    event2 = EventIn(
        event_id="evt-brief-2",
        entity_type="account",
        entity_id="acct_brief_2",
        payload={"email": "shared@example.com"},
        reliability="high",
        source="crm",
    )
    await process_event(db_session, event2)

    briefing = await get_pre_call_briefing(db_session, "acct_brief")
    assert briefing["entity_id"] == "acct_brief"
    assert briefing["account_name"] == "Helios Apps"
    assert briefing["active_plan"] == "Enterprise"
    assert briefing["region"] == "Berlin"
    assert briefing["tier"] == "Platinum"
    assert len(briefing["ambiguous_identities"]) == 1
    assert any("do not auto-merge" in w for w in briefing["warnings"])


@pytest.mark.asyncio
async def test_sensitive_attributes_constant_covers_expected_values():
    assert "sla" in SENSITIVE_ATTRIBUTES
    assert "entitlement" in SENSITIVE_ATTRIBUTES
    assert "internal_notes" in SENSITIVE_ATTRIBUTES


@pytest.mark.asyncio
async def test_build_digest_no_snapshots(db_session):
    digest = await build_digest(db_session, "acct_no_snapshots")
    assert digest["entity_id"] == "acct_no_snapshots"
    assert digest["current_snapshot_id"] is None
    assert digest["changes"] == []
    assert digest["added"] == []
    assert digest["removed"] == []


@pytest.mark.asyncio
async def test_build_digest_detects_changes_and_added_facts(db_session):
    event1 = EventIn(
        event_id="evt-digest-1",
        entity_type="account",
        entity_id="acct_digest",
        payload={"plan": "Starter", "region": "Cairo"},
        reliability="high",
        source="crm",
    )
    await process_event(db_session, event1)

    event2 = EventIn(
        event_id="evt-digest-2",
        entity_type="account",
        entity_id="acct_digest",
        payload={"plan": "Enterprise", "seats": 42},
        reliability="high",
        source="billing",
    )
    await process_event(db_session, event2)

    digest = await build_digest(db_session, "acct_digest")
    assert digest["current_snapshot_id"] is not None
    assert digest["previous_snapshot_id"] is not None

    changes = {c["attribute"]: c for c in digest["changes"]}
    assert "plan" in changes
    assert changes["plan"]["old_value"] == "Starter"
    assert changes["plan"]["new_value"] == "Enterprise"

    added = {a["attribute"]: a for a in digest["added"]}
    assert "seats" in added
    assert added["seats"]["new_value"] == "42"

    removed = {r["attribute"]: r for r in digest["removed"]}
    assert "region" not in removed
    assert "plan" not in removed
