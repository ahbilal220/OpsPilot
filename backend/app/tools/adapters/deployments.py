import asyncio
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.evidence.models import EvidenceType
from app.tools.contracts import (
    AdapterResult,
    EvidenceDraft,
    ToolContext,
    ToolDefinition,
    ToolRisk,
)


class DeploymentsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    environment: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    limit: int = Field(default=20, ge=1, le=100)


class DeploymentsOutput(BaseModel):
    deployments: list[dict[str, Any]]
    matched: int


class DeploymentHistoryTool:
    input_model = DeploymentsInput

    def __init__(self, fixture_root: Path) -> None:
        self._path = (fixture_root / "deployments.json").resolve()
        self.definition = ToolDefinition(
            name="deployments.history",
            description="Read deployment history from the fixed demo deployment dataset.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=5,
            input_schema=DeploymentsInput.model_json_schema(),
            output_schema=DeploymentsOutput.model_json_schema(),
        )

    def _load(self) -> list[dict[str, Any]]:
        data = json.loads(self._path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Deployment fixture must contain a list")
        return [item for item in data if isinstance(item, dict)]

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = DeploymentsInput.model_validate(arguments)
        deployments = await asyncio.to_thread(self._load)
        matched = [
            item
            for item in deployments
            if item.get("service") == query.service
            and (query.environment is None or item.get("environment") == query.environment)
        ][: query.limit]
        output = DeploymentsOutput(deployments=matched, matched=len(matched))
        return AdapterResult(
            summary=f"Found {len(matched)} deployments for {query.service}.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.deployment,
                    source="demo-deployments",
                    source_reference="fixture://deployments.json",
                    summary=f"{len(matched)} deployment records matched for {query.service}.",
                    content=output.model_dump(mode="json"),
                )
            ],
        )
