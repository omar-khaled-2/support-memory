from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers.memory_controller import (
    build_snapshot,
    detect_ambiguous_identities,
    get_beliefs,
    get_conflicts,
    get_facts,
    get_pre_call_briefing,
    get_snapshots,
    process_events,
)
from app.db import get_db
from app.schemas.memory import (
    BeliefOut,
    ConflictOut,
    EventIn,
    FactOut,
    PreCallBriefingOut,
    ProcessResult,
    SnapshotOut,
)

router = APIRouter()


@router.post("/events/process", response_model=List[ProcessResult])
async def process_events_endpoint(
    events: List[EventIn],
    db: AsyncSession = Depends(get_db),
):
    return await process_events(db, events)


@router.get("/entities/{entity_id}/briefing", response_model=PreCallBriefingOut)
async def read_briefing(entity_id: str, db: AsyncSession = Depends(get_db)):
    briefing = await get_pre_call_briefing(db, entity_id)
    return PreCallBriefingOut(**briefing)


@router.get("/entities/{entity_id}/beliefs", response_model=BeliefOut)
async def read_beliefs(entity_id: str, db: AsyncSession = Depends(get_db)):
    beliefs = await get_beliefs(db, entity_id)
    ambiguities = await detect_ambiguous_identities(db)
    entity_ambiguities = [
        a
        for a in ambiguities
        if any(e["entity_id"] == entity_id for e in a["entities"])
    ]
    conflicts = await get_conflicts(db, entity_id)
    warnings = list(beliefs.get("warnings", []))
    if entity_ambiguities:
        warnings.append(
            "Identity attribute shared with other entities; do not auto-merge."
        )
    return BeliefOut(
        entity_id=beliefs["entity_id"],
        entity_type=beliefs["entity_type"],
        beliefs=beliefs["beliefs"],
        ambiguous_identities=entity_ambiguities,
        recent_conflicts=conflicts,
        warnings=warnings,
    )


@router.post("/entities/{entity_id}/snapshots", response_model=SnapshotOut)
async def create_snapshot(entity_id: str, db: AsyncSession = Depends(get_db)):
    return await build_snapshot(db, entity_id)


@router.get("/entities/{entity_id}/snapshots", response_model=List[SnapshotOut])
async def read_snapshots(entity_id: str, db: AsyncSession = Depends(get_db)):
    return await get_snapshots(db, entity_id)


@router.get("/facts", response_model=List[FactOut])
async def read_facts(
    entity_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_facts(db, entity_id, status)


@router.get("/conflicts", response_model=List[ConflictOut])
async def read_conflicts(
    entity_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    return await get_conflicts(db, entity_id)


@router.get("/ambiguities")
async def read_ambiguities(db: AsyncSession = Depends(get_db)):
    return await detect_ambiguous_identities(db)
