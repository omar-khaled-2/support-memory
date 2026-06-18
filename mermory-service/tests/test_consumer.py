import pytest

from app.services.consumer import EventConsumer, get_consumer


def test_get_consumer_singleton():
    consumer1 = get_consumer()
    consumer2 = get_consumer()
    assert consumer1 is consumer2
    assert isinstance(consumer1, EventConsumer)


@pytest.mark.asyncio
async def test_consumer_initially_not_ready():
    consumer = EventConsumer(rabbitmq_url="amqp://invalid")
    assert not await consumer.is_ready()
