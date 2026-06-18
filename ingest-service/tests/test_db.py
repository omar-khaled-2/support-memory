from app.db import generate_event_id


def test_generate_event_id():
    event_id = generate_event_id()
    assert event_id.startswith("evt-")
    assert len(event_id) > 4
