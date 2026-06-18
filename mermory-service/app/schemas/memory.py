from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    event_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)
    reliability: str = Field(default="medium")
    text: str = Field(default="")
    occurred_at: Optional[datetime] = Field(default=None)


class FactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    fact_id: str
    entity_type: str
    entity_id: str
    attribute: str
    value: str
    source_event_id: str
    confidence: float
    status: str
    created_at: datetime
    superseded_at: Optional[datetime] = None


class ConflictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conflict_id: str
    entity_type: str
    entity_id: str
    attribute: str
    description: str
    created_at: datetime


class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    snapshot_id: str
    entity_id: str
    context_json: str
    created_at: datetime


class BeliefOut(BaseModel):
    entity_id: str
    entity_type: str
    beliefs: Dict[str, Any]
    snapshot_id: Optional[str] = None


class ProcessResult(BaseModel):
    event_id: str
    facts_extracted: int
    conflicts_detected: int
    snapshot_id: Optional[str] = None
