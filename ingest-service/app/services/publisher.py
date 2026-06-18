import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import aio_pika

from app.config import get_settings


class EventPublisher:
    def __init__(self, rabbitmq_url: Optional[str] = None):
        self.rabbitmq_url = rabbitmq_url or get_settings().rabbitmq_url
        self.connection: Optional[aio_pika.RobustConnection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.exchange: Optional[aio_pika.Exchange] = None
        self._ready = False

    async def connect(self):
        try:
            self.connection = await aio_pika.connect_robust(self.rabbitmq_url)
            self.channel = await self.connection.channel()
            self.exchange = await self.channel.declare_exchange(
                "events", aio_pika.ExchangeType.TOPIC, durable=True
            )
            self._ready = True
        except Exception:
            self._ready = False
            raise

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
        self._ready = False

    async def publish(self, event: dict):
        if not self._ready or not self.exchange:
            raise RuntimeError("Publisher not connected")
        routing_key = f"event.{event.get('entity_type', 'unknown')}"
        message = aio_pika.Message(
            body=json.dumps(event).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self.exchange.publish(message, routing_key=routing_key)

    async def is_ready(self) -> bool:
        return self._ready and self.connection is not None and not self.connection.is_closed


_publisher: Optional[EventPublisher] = None


def get_publisher() -> EventPublisher:
    global _publisher
    if _publisher is None:
        _publisher = EventPublisher()
    return _publisher


async def publish_outbox(publisher: EventPublisher, session_factory):
    from sqlalchemy import select
    from app.models import Event

    while True:
        await asyncio.sleep(get_settings().publish_interval_seconds)
        try:
            if not await publisher.is_ready():
                continue

            async with session_factory() as session:
                result = await session.execute(
                    select(Event).where(Event.published_at.is_(None)).order_by(Event.received_at).limit(100)
                )
                events = result.scalars().all()
                for event in events:
                    await publisher.publish(event.raw_body)
                    event.published_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception:
            pass
