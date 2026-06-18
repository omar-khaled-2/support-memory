from typing import Optional

from fastapi import APIRouter

from app.controllers.query_controller import answer_question
from app.schemas.query import QueryIn, QueryOut
from app.services.memory_client import fetch_digest

router = APIRouter()


@router.post("/query", response_model=QueryOut)
async def query(payload: QueryIn):
    return await answer_question(payload.question, payload.entity_id)


@router.get("/entities/{entity_id}/digest")
async def digest(entity_id: str, since_snapshot_id: Optional[str] = None):
    return await fetch_digest(entity_id, since_snapshot_id)
