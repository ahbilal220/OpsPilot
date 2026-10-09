from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.evidence.models import EvidenceType


class EvidencePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incident_id: UUID
    investigation_id: UUID
    type: EvidenceType
    source: str
    source_reference: str | None
    tool_name: str
    query: dict[str, Any]
    content: str
    summary: str
    content_hash: str
    observed_at: datetime | None
    created_at: datetime
