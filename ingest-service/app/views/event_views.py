from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.controllers import get_event_by_id, ingest_events
from app.db import get_db
from app.schemas import EventIn, EventOut, EventResult

router = APIRouter()


@router.post("/events", response_model=List[EventResult])
async def create_events(
    events: List[EventIn],
    db: AsyncSession = Depends(get_db),
):
    return await ingest_events(events, db)


@router.get("/events/{event_id}", response_model=EventOut)
async def read_event(event_id: str, db: AsyncSession = Depends(get_db)):
    event = await get_event_by_id(event_id, db)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event
