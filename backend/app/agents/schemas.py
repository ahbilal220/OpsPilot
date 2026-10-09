from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: str
    affected_services: list[str] = Field(max_length=10)
    symptoms: list[str] = Field(max_length=20)
    initial_categories: list[str] = Field(max_length=10)
    scope_supported: bool
    scope_reason: str = Field(min_length=1, max_length=500)


class PlannedToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    arguments: dict[str, Any]
    purpose: str = Field(min_length=1, max_length=500)


class EvidencePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calls: list[PlannedToolCall] = Field(max_length=10)


class HypothesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1, max_length=4000)
    supporting_evidence_ids: list[UUID] = Field(min_length=1, max_length=50)
    contradicting_evidence_ids: list[UUID] = Field(default_factory=list, max_length=50)
    validation_plan: list[str] = Field(min_length=1, max_length=20)


class DiagnosisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_cause: str = Field(min_length=1, max_length=500)
    summary: str = Field(min_length=1, max_length=6000)
    evidence_ids: list[UUID] = Field(min_length=1, max_length=50)
    limitations: list[str] = Field(default_factory=list, max_length=20)


class ValidationResult(BaseModel):
    status: str
    confidence: Decimal = Field(ge=0, le=1)
    checks: dict[str, bool]
    supporting_evidence_ids: list[UUID]
    contradicting_evidence_ids: list[UUID]
    summary: str


class HypothesisPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investigation_id: UUID
    title: str
    description: str
    confidence: Decimal
    status: str
    supporting_evidence_ids: list[UUID]
    contradicting_evidence_ids: list[UUID]
    validation_plan: list[str]
    validation_result: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class DiagnosisPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    investigation_id: UUID
    root_cause: str
    summary: str
    confidence: Decimal
    evidence_ids: list[UUID]
    limitations: list[str]
    created_at: datetime


class InvestigationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: UUID
    investigation_id: UUID
    status: str = "running"
    current_node: str = "triage"
    incident_summary: str
    affected_services: list[str] = Field(default_factory=list)
    initial_categories: list[str] = Field(default_factory=list)
    evidence_ids: list[UUID] = Field(default_factory=list)
    hypothesis_ids: list[UUID] = Field(default_factory=list)
    selected_hypothesis_id: UUID | None = None
    tool_budget_remaining: int = Field(ge=0)
    model_budget_usd_remaining: Decimal = Field(ge=0)
    iteration_count: int = Field(default=0, ge=0)
    blockers: list[str] = Field(default_factory=list)
    scope_supported: bool = False
    planned_calls: list[PlannedToolCall] = Field(default_factory=list)
