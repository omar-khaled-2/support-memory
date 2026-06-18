from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Reliability(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class EventIn(BaseModel):
    event_id: Optional[str] = Field(default=None, min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    occurred_at: datetime
    source: str = Field(..., min_length=1)
    actor: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    related_entity_ids: List[str] = Field(default_factory=list)
    reliability: Reliability
    text: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class EventResult(BaseModel):
    event_id: str
    idempotency_key: str
    status: str


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    idempotency_key: str
    occurred_at: datetime
    received_at: datetime
    source: str
    actor: str
    entity_type: str
    entity_id: str
    related_entity_ids: List[str]
    reliability: str
    text: str
    payload: Dict[str, Any]
