import asyncio
import json
from typing import Optional

import aio_pika

from app.config import get_settings
from app.controllers.memory_controller import process_event
from app.db import async_session_maker
from app.schemas.memory import EventIn


class EventConsumer:
    def __init__(self, rabbitmq_url: Optional[str] = None):
        self.rabbitmq_url = rabbitmq_url or get_settings().rabbitmq_url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self.queue: Optional[aio_pika.Queue] = None
        self._ready = False

    async def connect(self):
        self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(
            "events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        self.queue = await self.channel.declare_queue("memory_service", durable=True)
        await self.queue.bind(self.exchange, routing_key="event.#")
        self._ready = True

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        self._ready = False

    async def is_ready(self) -> bool:
        return self._ready and self.connection is not None and not self.connection.is_closed

    async def handle_message(self, message: aio_pika.IncomingMessage):
        async with message.process():
            try:
                body = json.loads(message.body.decode("utf-8"))
                event = EventIn(
                    event_id=body.get("event_id", "unknown"),
                    entity_type=body.get("entity_type", "unknown"),
                    entity_id=body.get("entity_id", "unknown"),
                    payload=body.get("payload", {}),
                    reliability=body.get("reliability", "medium"),
                    text=body.get("text", ""),
                )
                async with async_session_maker() as session:
                    await process_event(session, event)
            except Exception:
                pass

    async def consume(self):
        if not self._ready or not self.queue:
            raise RuntimeError("Consumer not connected")
        await self.queue.consume(self.handle_message)


_consumer: Optional[EventConsumer] = None


def get_consumer() -> EventConsumer:
    global _consumer
    if _consumer is None:
        _consumer = EventConsumer()
    return _consumer


async def run_consumer(consumer: EventConsumer):
    while True:
        try:
            if not await consumer.is_ready():
                await consumer.connect()
                await consumer.consume()
            await asyncio.sleep(get_settings().consume_interval_seconds)
        except Exception:
            await asyncio.sleep(get_settings().consume_interval_seconds)
