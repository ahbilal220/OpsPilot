from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.agents.schemas import DiagnosisPublic
from app.audit.models import ActorType
from app.incidents.models import IncidentSource, IncidentStatus, Severity


class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    repository_url: HttpUrl | None = None
    default_branch: str = Field(default="main", min_length=1, max_length=120)
    environment: str = Field(default="local", min_length=1, max_length=80)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name", "default_branch", "environment")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ServiceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    repository_url: HttpUrl | None = None
    default_branch: str | None = Field(default=None, min_length=1, max_length=120)
    environment: str | None = Field(default=None, min_length=1, max_length=80)
    metadata: dict[str, Any] | None = None

    @field_validator("name", "default_branch", "environment")
    @classmethod
    def strip_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class ServicePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    repository_url: str | None
    default_branch: str
    environment: str
    metadata: dict[str, Any] = Field(validation_alias="service_metadata")
    created_at: datetime
    updated_at: datetime


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    severity: Severity
    service_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_nonempty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10000)
    severity: Severity | None = None
    service_id: UUID | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_nonempty(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class IncidentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str
    severity: Severity
    status: IncidentStatus
    source: IncidentSource
    service_id: UUID | None
    created_by: UUID
    started_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class InvestigationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID
    status: str
    current_node: str
    queue_task_id: str | None
    iteration_count: int
    tool_calls_count: int
    llm_cost_usd: Decimal
    started_at: datetime | None
    completed_at: datetime | None
    state_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TimelineEventPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    incident_id: UUID | None
    actor_type: ActorType
    actor_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class IncidentDetail(BaseModel):
    incident: IncidentPublic
    investigation: InvestigationPublic | None
    timeline: list[TimelineEventPublic]
    diagnosis: DiagnosisPublic | None = None
    remediation: None = None


class InvestigationAccepted(BaseModel):
    investigation_id: UUID
    incident_id: UUID
    status: str
    task_id: str | None
