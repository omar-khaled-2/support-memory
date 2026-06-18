from fastapi import APIRouter

from app.controllers.query_controller import answer_question
from app.schemas.query import QueryIn, QueryOut

router = APIRouter()


@router.post("/query", response_model=QueryOut)
async def query(payload: QueryIn):
    return await answer_question(payload.question, payload.entity_id)
