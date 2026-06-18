from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EventIn(BaseModel):
    event_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)
    source: str = Field(default="unknown")
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
    source: str
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


class PreCallBriefingOut(BaseModel):
    entity_id: str
    entity_type: str
    account_name: Optional[str] = None
    active_plan: Optional[str] = None
    region: Optional[str] = None
    tier: Optional[str] = None
    last_conflict_at: Optional[str] = None
    ambiguous_identities: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    beliefs: Dict[str, Any] = Field(default_factory=dict)


class BeliefOut(BaseModel):
    entity_id: str
    entity_type: str
    beliefs: Dict[str, Any]
    snapshot_id: Optional[str] = None
    ambiguous_identities: List[Dict[str, Any]] = Field(default_factory=list)
    recent_conflicts: List[Any] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ProcessResult(BaseModel):
    event_id: str
    facts_extracted: int
    conflicts_detected: int
    snapshot_id: Optional[str] = None
