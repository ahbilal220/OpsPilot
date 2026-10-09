from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ToolExecutionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    investigation_id: UUID
    tool_name: str
    risk_level: str
    input: dict[str, Any] = Field(validation_alias="input_data")
    output: dict[str, Any] | None = Field(validation_alias="output_data")
    status: str
    duration_ms: int | None
    error: str | None
    created_at: datetime
