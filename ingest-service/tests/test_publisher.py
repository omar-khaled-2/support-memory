from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.publisher import EventPublisher, get_publisher, publish_outbox


@pytest.mark.asyncio
async def test_publisher_connect_and_publish():
    publisher = EventPublisher(rabbitmq_url="amqp://test")
    mock_exchange = AsyncMock()
    mock_channel = AsyncMock()
    mock_channel.declare_exchange = AsyncMock(return_value=mock_exchange)
    mock_connection = AsyncMock()
    mock_connection.is_closed = False

    with patch("aio_pika.connect_robust", new_callable=AsyncMock, return_value=mock_connection):
        await publisher.connect()
        publisher.channel = mock_channel
        publisher.exchange = mock_exchange
        publisher._ready = True
        await publisher.publish({"entity_type": "account", "event_id": "evt-1"})

    mock_exchange.publish.assert_awaited_once()
    assert await publisher.is_ready()


@pytest.mark.asyncio
async def test_publisher_not_ready_when_closed():
    publisher = EventPublisher(rabbitmq_url="amqp://test")
    publisher._ready = True
    publisher.connection = MagicMock()
    publisher.connection.is_closed = True
    assert not await publisher.is_ready()


@pytest.mark.asyncio
async def test_publish_raises_when_not_connected():
    publisher = EventPublisher(rabbitmq_url="amqp://test")
    publisher._ready = False
    with pytest.raises(RuntimeError):
        await publisher.publish({"entity_type": "account"})


def test_get_publisher_singleton():
    p1 = get_publisher()
    p2 = get_publisher()
    assert p1 is p2


@pytest.mark.asyncio
async def test_publish_outbox_publishes_unpublished_events():
    import asyncio
    from datetime import datetime, timezone

    from app.models import Event
    from tests.conftest import TestingSessionLocal, init_test_db

    await init_test_db()

    event = Event(
        event_id="evt-outbox",
        idempotency_key="idem-outbox",
        occurred_at=datetime.now(timezone.utc),
        source="test",
        actor="test",
        entity_type="account",
        entity_id="acct_1",
        reliability="medium",
        text="outbox test",
        payload={},
        raw_body={"event_id": "evt-outbox", "entity_type": "account"},
        published_at=None,
    )
    async with TestingSessionLocal() as session:
        session.add(event)
        await session.commit()

    publisher = EventPublisher(rabbitmq_url="amqp://test")
    publisher._ready = True
    publisher.exchange = AsyncMock()
    publisher.connection = MagicMock()
    publisher.connection.is_closed = False

    original_sleep = asyncio.sleep
    call_count = 0

    async def fake_sleep(delay):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            raise asyncio.CancelledError()
        return await original_sleep(0)

    with patch("asyncio.sleep", fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await publish_outbox(publisher, TestingSessionLocal)

    publisher.exchange.publish.assert_awaited_once()
