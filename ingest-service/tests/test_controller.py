import pytest
from app.controllers.event_controller import _canonical_hash


def test_canonical_hash_is_stable():
    payload = {"b": 2, "a": 1}
    h1 = _canonical_hash(payload)
    h2 = _canonical_hash({"a": 1, "b": 2})
    assert h1 == h2
    assert len(h1) == 64


@pytest.mark.asyncio
async def test_get_event_by_id_found(db_session):
    from app.controllers.event_controller import ingest_events
    from app.schemas import EventIn

    events = [
        EventIn(
            idempotency_key="idem-found",
            occurred_at="2026-04-01T09:00:00Z",
            source="crm",
            actor="system",
            entity_type="account",
            entity_id="acct_1",
            reliability="medium",
            text="test",
        )
    ]
    results = await ingest_events(events, db_session)
    event_id = results[0].event_id

    from app.controllers.event_controller import get_event_by_id
    event = await get_event_by_id(event_id, db_session)
    assert event is not None
    assert event.event_id == event_id


@pytest.mark.asyncio
async def test_get_event_by_id_not_found(db_session):
    from app.controllers.event_controller import get_event_by_id
    event = await get_event_by_id("evt-missing", db_session)
    assert event is None
