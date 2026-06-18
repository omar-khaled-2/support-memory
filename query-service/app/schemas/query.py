from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class QueryIn(BaseModel):
    question: str = Field(..., min_length=1)
    entity_id: Optional[str] = None


class QueryOut(BaseModel):
    question: str
    entity_id: Optional[str] = None
    answer: str
    context: Dict[str, Any] = Field(default_factory=dict)
