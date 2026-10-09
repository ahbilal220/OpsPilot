import enum
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.models import EvidenceType


class ToolRisk(enum.StrEnum):
    pure = "pure"
    read = "read"
    sandbox_write = "sandbox_write"
    external_write = "external_write"
    production_critical = "production_critical"


class RetryPolicy(BaseModel):
    max_attempts: int = Field(default=1, ge=1, le=3)
    backoff_seconds: float = Field(default=0, ge=0, le=5)


class ToolDefinition(BaseModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,119}$")
    description: str = Field(min_length=1, max_length=500)
    risk: ToolRisk
    read_only: bool
    timeout_seconds: int = Field(ge=1, le=30)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]


class ToolContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    incident_id: UUID
    investigation_id: UUID
    actor_id: str = Field(min_length=1, max_length=100)
    allowed_tools: frozenset[str]


class EvidenceDraft(BaseModel):
    type: EvidenceType
    source: str = Field(min_length=1, max_length=120)
    source_reference: str | None = Field(default=None, max_length=2000)
    summary: str = Field(min_length=1, max_length=2000)
    content: Any
    observed_at: datetime | None = None


class AdapterResult(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    data: dict[str, Any]
    evidence: list[EvidenceDraft] = Field(min_length=1, max_length=20)


class ToolResult(BaseModel):
    execution_id: UUID
    success: bool
    summary: str
    data: dict[str, Any]
    evidence_ids: list[UUID]


class ToolInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolAdapter(Protocol):
    @property
    def definition(self) -> ToolDefinition: ...

    @property
    def input_model(self) -> type[BaseModel]: ...

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult: ...
