import hashlib
import json
from datetime import datetime, timezone
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import generate_event_id
from app.models import Conflict, Event, ProcessedKey
from app.schemas import EventIn, EventResult
from app.services.publisher import get_publisher


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def ingest_events(events: List[EventIn], db: AsyncSession) -> List[EventResult]:
    results: List[EventResult] = []

    for incoming in events:
        payload_hash = _canonical_hash(incoming.model_dump(exclude={"idempotency_key"}))

        existing_key = await db.execute(
            select(ProcessedKey).where(ProcessedKey.idempotency_key == incoming.idempotency_key)
        )
        processed = existing_key.scalar_one_or_none()

        if processed:
            if processed.payload_hash == payload_hash:
                results.append(
                    EventResult(
                        event_id=processed.event_id or "unknown",
                        idempotency_key=incoming.idempotency_key,
                        status="duplicate",
                    )
                )
                continue

            conflict = Conflict(
                idempotency_key=incoming.idempotency_key,
                attempted_event_id=incoming.event_id or generate_event_id(),
                attempted_payload_hash=payload_hash,
                existing_event_id=processed.event_id,
            )
            db.add(conflict)
            await db.commit()
            results.append(
                EventResult(
                    event_id=conflict.attempted_event_id,
                    idempotency_key=incoming.idempotency_key,
                    status="conflict",
                )
            )
            continue

        event_id = incoming.event_id or generate_event_id()
        raw_body = incoming.model_dump(mode="json")
        raw_body["event_id"] = event_id

        event = Event(
            event_id=event_id,
            idempotency_key=incoming.idempotency_key,
            occurred_at=incoming.occurred_at,
            source=incoming.source,
            actor=incoming.actor,
            entity_type=incoming.entity_type,
            entity_id=incoming.entity_id,
            related_entity_ids=incoming.related_entity_ids,
            reliability=incoming.reliability.value,
            text=incoming.text,
            payload=incoming.payload,
            raw_body=raw_body,
        )
        db.add(event)
        await db.flush()

        processed_key = ProcessedKey(
            idempotency_key=incoming.idempotency_key,
            event_id=event_id,
            payload_hash=payload_hash,
        )
        db.add(processed_key)
        await db.commit()

        publisher = get_publisher()
        if await publisher.is_ready():
            try:
                await publisher.publish(raw_body)
                event.published_at = datetime.now(timezone.utc)
                await db.commit()
            except Exception:
                pass

        results.append(
            EventResult(
                event_id=event_id,
                idempotency_key=incoming.idempotency_key,
                status="created",
            )
        )

    return results


async def get_event_by_id(event_id: str, db: AsyncSession) -> Event:
    result = await db.execute(select(Event).where(Event.event_id == event_id))
    return result.scalar_one_or_none()
