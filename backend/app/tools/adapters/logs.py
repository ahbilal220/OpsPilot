import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.models import EvidenceType
from app.tools.contracts import (
    AdapterResult,
    EvidenceDraft,
    RetryPolicy,
    ToolContext,
    ToolDefinition,
    ToolRisk,
)


class LogsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    contains: str | None = Field(default=None, min_length=1, max_length=200)
    limit: int = Field(default=50, ge=1, le=200)


class LogsOutput(BaseModel):
    records: list[dict[str, Any]]
    matched: int


class DemoLogsTool:
    input_model = LogsInput

    def __init__(self, fixture_root: Path) -> None:
        self._path = (fixture_root / "logs.json").resolve()
        self.definition = ToolDefinition(
            name="logs.search",
            description="Search the fixed demo log dataset by service and literal text.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=5,
            retry_policy=RetryPolicy(max_attempts=1),
            input_schema=LogsInput.model_json_schema(),
            output_schema=LogsOutput.model_json_schema(),
        )

    def _load(self) -> list[dict[str, Any]]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Log fixture must contain a list")
        return [item for item in data if isinstance(item, dict)]

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = LogsInput.model_validate(arguments)
        records = await asyncio.to_thread(self._load)
        needle = query.contains.casefold() if query.contains else None
        matched = [
            record
            for record in records
            if str(record.get("service", "")) == query.service
            and (needle is None or needle in json.dumps(record).casefold())
        ][: query.limit]
        observed_values = [record.get("timestamp") for record in matched]
        observed_at = None
        for value in reversed(observed_values):
            if isinstance(value, str):
                try:
                    observed_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
                    break
                except ValueError:
                    continue
        output = LogsOutput(records=matched, matched=len(matched))
        return AdapterResult(
            summary=f"Found {len(matched)} demo log records for {query.service}.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.log,
                    source="demo-logs",
                    source_reference="fixture://logs.json",
                    summary=f"{len(matched)} log records matched for {query.service}.",
                    content=output.model_dump(mode="json"),
                    observed_at=observed_at,
                )
            ],
        )
