import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import generate_conflict_id, generate_fact_id, generate_snapshot_id
from app.models.memory import Conflict, Fact, Snapshot
from app.schemas.memory import EventIn, ProcessResult
from app.services.extractor import get_extractor


IDENTITY_ATTRIBUTES = {"email", "phone", "external_id", "customer_id", "user_id"}


def _reliability_to_confidence(reliability: str) -> float:
    return {"high": 1.0, "medium": 0.75, "low": 0.5}.get(reliability, 0.75)


def _extract_facts_from_payload(event: EventIn) -> List[Dict[str, Any]]:
    facts = []
    for attribute, raw_value in event.payload.items():
        facts.append(
            {
                "entity_type": event.entity_type,
                "entity_id": event.entity_id,
                "attribute": attribute,
                "value": str(raw_value),
            }
        )
    return facts


async def _extract_facts_from_event(event: EventIn) -> List[Dict[str, Any]]:
    payload_facts = _extract_facts_from_payload(event)
    payload_attributes = {f["attribute"] for f in payload_facts}

    extractor = get_extractor()
    if not extractor.api_key:
        return payload_facts

    try:
        llm_facts = await extractor.extract_facts(
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            payload=event.payload,
            text=event.text or "",
        )
    except Exception:
        return payload_facts

    combined = {f["attribute"]: f for f in payload_facts}
    for fact in llm_facts:
        if fact["attribute"] not in payload_attributes:
            combined[fact["attribute"]] = fact
    return list(combined.values())


async def _find_active_fact(
    db: AsyncSession, entity_type: str, entity_id: str, attribute: str
) -> Optional[Fact]:
    result = await db.execute(
        select(Fact)
        .where(
            Fact.entity_type == entity_type,
            Fact.entity_id == entity_id,
            Fact.attribute == attribute,
            Fact.status == "active",
        )
        .order_by(Fact.created_at.desc())
    )
    return result.scalars().first()


async def _mark_superseded(db: AsyncSession, fact: Fact):
    fact.status = "superseded"
    fact.superseded_at = datetime.now(timezone.utc)
    db.add(fact)


async def _record_conflict(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
    attribute: str,
    old_value: str,
    new_value: str,
) -> Conflict:
    conflict = Conflict(
        conflict_id=generate_conflict_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        attribute=attribute,
        description=(
            f"Contradiction for {entity_type}/{entity_id}::{attribute}: "
            f"'{old_value}' vs '{new_value}'"
        ),
    )
    db.add(conflict)
    return conflict


async def process_event(db: AsyncSession, event: EventIn) -> ProcessResult:
    facts = await _extract_facts_from_event(event)
    confidence = _reliability_to_confidence(event.reliability)
    conflict_count = 0

    for fact_data in facts:
        existing = await _find_active_fact(
            db,
            fact_data["entity_type"],
            fact_data["entity_id"],
            fact_data["attribute"],
        )

        if existing and existing.value != fact_data["value"]:
            await _record_conflict(
                db,
                existing.entity_type,
                existing.entity_id,
                existing.attribute,
                existing.value,
                fact_data["value"],
            )
            await _mark_superseded(db, existing)
            conflict_count += 1

        fact = Fact(
            fact_id=generate_fact_id(),
            entity_type=fact_data["entity_type"],
            entity_id=fact_data["entity_id"],
            attribute=fact_data["attribute"],
            value=fact_data["value"],
            source_event_id=event.event_id,
            confidence=confidence,
            status="active",
        )
        db.add(fact)

    await db.commit()

    snapshot_id = None
    if facts:
        snapshot = await build_snapshot(db, event.entity_id)
        snapshot_id = snapshot.snapshot_id

    return ProcessResult(
        event_id=event.event_id,
        facts_extracted=len(facts),
        conflicts_detected=conflict_count,
        snapshot_id=snapshot_id,
    )


async def process_events(db: AsyncSession, events: List[EventIn]) -> List[ProcessResult]:
    results = []
    for event in events:
        result = await process_event(db, event)
        results.append(result)
    return results


async def build_snapshot(db: AsyncSession, entity_id: str) -> Snapshot:
    result = await db.execute(
        select(Fact).where(
            Fact.entity_id == entity_id,
            Fact.status == "active",
        )
    )
    facts = result.scalars().all()

    entity_type = facts[0].entity_type if facts else "unknown"
    beliefs: Dict[str, Any] = {}
    for fact in facts:
        beliefs[fact.attribute] = {
            "value": fact.value,
            "confidence": fact.confidence,
            "source_event_id": fact.source_event_id,
            "fact_id": fact.fact_id,
        }

    context = {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "beliefs": beliefs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    snapshot = Snapshot(
        snapshot_id=generate_snapshot_id(),
        entity_id=entity_id,
        context_json=json.dumps(context),
    )
    db.add(snapshot)
    await db.commit()
    return snapshot


async def get_beliefs(db: AsyncSession, entity_id: str) -> Dict[str, Any]:
    result = await db.execute(
        select(Fact).where(
            Fact.entity_id == entity_id,
            Fact.status == "active",
        )
    )
    facts = result.scalars().all()

    entity_type = facts[0].entity_type if facts else "unknown"
    beliefs = {
        fact.attribute: {"value": fact.value, "confidence": fact.confidence}
        for fact in facts
    }

    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "beliefs": beliefs,
    }


async def detect_ambiguous_identities(db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(Fact).where(
            Fact.attribute.in_(IDENTITY_ATTRIBUTES),
            Fact.status == "active",
        )
    )
    facts = result.scalars().all()

    value_to_entities: Dict[str, Dict[str, Any]] = {}
    for fact in facts:
        key = f"{fact.attribute}:{fact.value}"
        value_to_entities.setdefault(key, {"attribute": fact.attribute, "value": fact.value, "entities": set()})
        value_to_entities[key]["entities"].add((fact.entity_type, fact.entity_id))

    ambiguities = []
    for entry in value_to_entities.values():
        if len(entry["entities"]) > 1:
            ambiguities.append(
                {
                    "attribute": entry["attribute"],
                    "value": entry["value"],
                    "entity_count": len(entry["entities"]),
                    "entities": [
                        {"entity_type": et, "entity_id": ei}
                        for et, ei in entry["entities"]
                    ],
                }
            )

    return ambiguities


async def get_conflicts(db: AsyncSession, entity_id: Optional[str] = None) -> List[Conflict]:
    query = select(Conflict)
    if entity_id:
        query = query.where(Conflict.entity_id == entity_id)
    result = await db.execute(query.order_by(Conflict.created_at.desc()))
    return list(result.scalars().all())


async def get_facts(
    db: AsyncSession, entity_id: Optional[str] = None, status: Optional[str] = None
) -> List[Fact]:
    query = select(Fact)
    if entity_id:
        query = query.where(Fact.entity_id == entity_id)
    if status:
        query = query.where(Fact.status == status)
    result = await db.execute(query.order_by(Fact.created_at.desc()))
    return list(result.scalars().all())


async def get_snapshots(db: AsyncSession, entity_id: Optional[str] = None) -> List[Snapshot]:
    query = select(Snapshot)
    if entity_id:
        query = query.where(Snapshot.entity_id == entity_id)
    result = await db.execute(query.order_by(Snapshot.created_at.desc()))
    return list(result.scalars().all())
