import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import generate_conflict_id, generate_fact_id, generate_snapshot_id
from app.models.memory import Conflict, Fact, Snapshot
from app.schemas.memory import EventIn, ProcessResult
from app.services.extractor import get_extractor


IDENTITY_ATTRIBUTES = {"email", "phone", "external_id", "customer_id", "user_id"}

# Attributes that should never be returned without explicit entity scoping.
SENSITIVE_ATTRIBUTES = {
    "sla",
    "entitlement",
    "entitlements",
    "internal_notes",
    "discount_rate",
    "payment_terms",
    "contract_value",
    "private_note",
}


def _reliability_to_confidence(reliability: str) -> float:
    return {"high": 1.0, "medium": 0.75, "low": 0.5}.get(reliability, 0.75)


def _source_weight(source: str) -> int:
    return get_settings().source_weight_map.get(source.strip().lower(), 0)


def _score_fact(fact: Fact) -> float:
    source_weight = _source_weight(fact.source)
    return fact.confidence + source_weight


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
    winner: str,
) -> Conflict:
    conflict = Conflict(
        conflict_id=generate_conflict_id(),
        entity_type=entity_type,
        entity_id=entity_id,
        attribute=attribute,
        description=(
            f"Contradiction for {entity_type}/{entity_id}::{attribute}: "
            f"'{old_value}' vs '{new_value}' (winner: {winner})"
        ),
    )
    db.add(conflict)
    return conflict


async def process_event(db: AsyncSession, event: EventIn) -> ProcessResult:
    facts = await _extract_facts_from_event(event)
    confidence = _reliability_to_confidence(event.reliability)
    conflict_count = 0

    incoming_weight = _source_weight(event.source)

    for fact_data in facts:
        existing = await _find_active_fact(
            db,
            fact_data["entity_type"],
            fact_data["entity_id"],
            fact_data["attribute"],
        )

        if existing and existing.value != fact_data["value"]:
            existing_score = _score_fact(existing)
            incoming_score = confidence + incoming_weight

            if incoming_score > existing_score:
                winner = f"{event.source} (higher authority)"
                await _record_conflict(
                    db,
                    existing.entity_type,
                    existing.entity_id,
                    existing.attribute,
                    existing.value,
                    fact_data["value"],
                    winner,
                )
                await _mark_superseded(db, existing)
            else:
                winner = f"{existing.source} (retained, higher or equal authority)"
                await _record_conflict(
                    db,
                    existing.entity_type,
                    existing.entity_id,
                    existing.attribute,
                    existing.value,
                    fact_data["value"],
                    winner,
                )
                conflict_count += 1
                continue

        fact = Fact(
            fact_id=generate_fact_id(),
            entity_type=fact_data["entity_type"],
            entity_id=fact_data["entity_id"],
            attribute=fact_data["attribute"],
            value=fact_data["value"],
            source_event_id=event.event_id,
            source=event.source,
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


async def process_events(
    db: AsyncSession, events: List[EventIn]
) -> List[ProcessResult]:
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
            "source": fact.source,
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
        fact.attribute: {
            "value": fact.value,
            "confidence": fact.confidence,
            "source": fact.source,
        }
        for fact in facts
        if fact.attribute not in SENSITIVE_ATTRIBUTES
    }

    warnings = []
    if any(fact.attribute in SENSITIVE_ATTRIBUTES for fact in facts):
        warnings.append(
            "Sensitive account-specific facts exist; use scoped endpoints to retrieve them."
        )

    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "beliefs": beliefs,
        "warnings": warnings,
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
        value_to_entities.setdefault(
            key, {"attribute": fact.attribute, "value": fact.value, "entities": set()}
        )
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


async def get_conflicts(
    db: AsyncSession, entity_id: Optional[str] = None, limit: int = 10
) -> List[Conflict]:
    query = select(Conflict)
    if entity_id:
        query = query.where(Conflict.entity_id == entity_id)
    result = await db.execute(query.order_by(Conflict.created_at.desc()).limit(limit))
    return list(result.scalars().all())


async def get_facts(
    db: AsyncSession,
    entity_id: Optional[str] = None,
    status: Optional[str] = None,
    include_sensitive: bool = False,
) -> List[Fact]:
    query = select(Fact)
    if entity_id:
        query = query.where(Fact.entity_id == entity_id)
    if status:
        query = query.where(Fact.status == status)
    if not include_sensitive:
        query = query.where(Fact.attribute.not_in(SENSITIVE_ATTRIBUTES))
    result = await db.execute(query.order_by(Fact.created_at.desc()))
    return list(result.scalars().all())


async def get_snapshots(
    db: AsyncSession, entity_id: Optional[str] = None
) -> List[Snapshot]:
    query = select(Snapshot)
    if entity_id:
        query = query.where(Snapshot.entity_id == entity_id)
    result = await db.execute(query.order_by(Snapshot.created_at.desc()))
    return list(result.scalars().all())


async def get_pre_call_briefing(db: AsyncSession, entity_id: str) -> Dict[str, Any]:
    beliefs_result = await get_beliefs(db, entity_id)
    beliefs = beliefs_result["beliefs"]

    snapshots = await get_snapshots(db, entity_id)
    latest_snapshot = snapshots[0] if snapshots else None

    conflicts = await get_conflicts(db, entity_id, limit=5)
    last_conflict_at = None
    if conflicts:
        last_conflict_at = conflicts[0].created_at.isoformat()

    ambiguities = await detect_ambiguous_identities(db)
    entity_ambiguities = [
        a
        for a in ambiguities
        if any(e["entity_id"] == entity_id for e in a["entities"])
    ]

    warnings = list(beliefs_result.get("warnings", []))
    if entity_ambiguities:
        warnings.append(
            "Identity attribute shared with other entities; do not auto-merge."
        )

    return {
        "entity_id": entity_id,
        "entity_type": beliefs_result["entity_type"],
        "account_name": beliefs.get("account_name", {}).get("value"),
        "active_plan": beliefs.get("plan", {}).get("value"),
        "region": beliefs.get("region", {}).get("value"),
        "tier": beliefs.get("tier", {}).get("value"),
        "last_conflict_at": last_conflict_at,
        "ambiguous_identities": entity_ambiguities,
        "warnings": warnings,
        "beliefs": beliefs,
        "snapshot_id": latest_snapshot.snapshot_id if latest_snapshot else None,
    }


async def build_digest(
    db: AsyncSession, entity_id: str, since_snapshot_id: Optional[str] = None
) -> Dict[str, Any]:
    snapshots = await get_snapshots(db, entity_id)
    if not snapshots:
        return {
            "entity_id": entity_id,
            "current_snapshot_id": None,
            "previous_snapshot_id": None,
            "previous_generated_at": None,
            "changes": [],
            "added": [],
            "removed": [],
            "new_conflicts": [],
        }

    def _snapshot_generated_at(snap: Snapshot) -> str:
        try:
            return json.loads(snap.context_json).get("generated_at", "")
        except Exception:
            return ""

    snapshots = sorted(
        snapshots,
        key=lambda s: _snapshot_generated_at(s),
        reverse=True,
    )

    current_snapshot = snapshots[0]
    previous_snapshot = None
    if since_snapshot_id:
        for snap in snapshots:
            if snap.snapshot_id == since_snapshot_id:
                previous_snapshot = snap
                break
    if not previous_snapshot and len(snapshots) > 1:
        previous_snapshot = snapshots[1]

    current_context = json.loads(current_snapshot.context_json)
    current_beliefs = current_context.get("beliefs", {})

    previous_beliefs: Dict[str, Any] = {}
    previous_generated_at: Optional[str] = None
    if previous_snapshot:
        previous_context = json.loads(previous_snapshot.context_json)
        previous_beliefs = previous_context.get("beliefs", {})
        previous_generated_at = previous_context.get("generated_at")

    changes: List[Dict[str, Any]] = []
    added: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []

    current_attrs = set(current_beliefs.keys())
    previous_attrs = set(previous_beliefs.keys())

    for attr in current_attrs & previous_attrs:
        old_value = str(previous_beliefs[attr].get("value"))
        new_value = str(current_beliefs[attr].get("value"))
        if old_value != new_value:
            changes.append(
                {
                    "attribute": attr,
                    "old_value": old_value,
                    "new_value": new_value,
                    "source": current_beliefs[attr].get("source"),
                }
            )

    for attr in current_attrs - previous_attrs:
        added.append(
            {
                "attribute": attr,
                "old_value": None,
                "new_value": str(current_beliefs[attr].get("value")),
                "source": current_beliefs[attr].get("source"),
            }
        )

    for attr in previous_attrs - current_attrs:
        removed.append(
            {
                "attribute": attr,
                "old_value": str(previous_beliefs[attr].get("value")),
                "new_value": None,
                "source": previous_beliefs[attr].get("source"),
            }
        )

    new_conflicts: List[Conflict] = []
    if previous_snapshot:
        all_conflicts = await get_conflicts(db, entity_id)
        new_conflicts = [
            c for c in all_conflicts if c.created_at > previous_snapshot.created_at
        ]

    return {
        "entity_id": entity_id,
        "current_snapshot_id": current_snapshot.snapshot_id,
        "previous_snapshot_id": previous_snapshot.snapshot_id if previous_snapshot else None,
        "previous_generated_at": previous_generated_at,
        "changes": changes,
        "added": added,
        "removed": removed,
        "new_conflicts": [
            {
                "conflict_id": c.conflict_id,
                "attribute": c.attribute,
                "description": c.description,
                "created_at": c.created_at.isoformat(),
            }
            for c in new_conflicts
        ],
    }
