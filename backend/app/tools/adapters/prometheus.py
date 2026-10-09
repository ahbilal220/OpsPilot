import asyncio
import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.evidence.models import EvidenceType
from app.tools.contracts import (
    AdapterResult,
    EvidenceDraft,
    RetryPolicy,
    ToolContext,
    ToolDefinition,
    ToolRisk,
)

MetricsFetcher = Callable[[str, float], dict[str, Any]]


class MetricsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500)
    time: float | None = Field(default=None, ge=0)

    @field_validator("query")
    @classmethod
    def single_line_query(cls, value: str) -> str:
        if "\n" in value or "\r" in value or "\x00" in value:
            raise ValueError("query must be a single line")
        return value


class MetricsOutput(BaseModel):
    status: str
    result_type: str | None
    result: Any


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("Prometheus returned a non-success status")
        body = response.read(1_000_001)
    if len(body) > 1_000_000:
        raise RuntimeError("Prometheus response exceeded the configured limit")
    payload = json.loads(body)
    if not isinstance(payload, dict):
        raise RuntimeError("Prometheus returned an invalid response")
    return payload


class PrometheusMetricsTool:
    input_model = MetricsInput

    def __init__(self, base_url: str, fetcher: MetricsFetcher = fetch_json) -> None:
        parsed = urllib.parse.urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            raise ValueError("Prometheus URL must be a fixed HTTP(S) origin without credentials")
        self._base_url = base_url.rstrip("/")
        self._fetcher = fetcher
        self.definition = ToolDefinition(
            name="metrics.query",
            description="Execute a read-only instant PromQL query against configured Prometheus.",
            risk=ToolRisk.read,
            read_only=True,
            timeout_seconds=8,
            retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=0.1),
            input_schema=MetricsInput.model_json_schema(),
            output_schema=MetricsOutput.model_json_schema(),
        )

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        query = MetricsInput.model_validate(arguments)
        parameters: dict[str, str] = {"query": query.query}
        if query.time is not None:
            parameters["time"] = str(query.time)
        url = f"{self._base_url}/api/v1/query?{urllib.parse.urlencode(parameters)}"
        payload = await asyncio.to_thread(self._fetcher, url, 6.0)
        raw_data = payload.get("data")
        data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
        output = MetricsOutput(
            status=str(payload.get("status", "unknown")),
            result_type=str(data.get("resultType")) if data.get("resultType") else None,
            result=data.get("result", []),
        )
        return AdapterResult(
            summary=f"Prometheus query completed with status {output.status}.",
            data=output.model_dump(mode="json"),
            evidence=[
                EvidenceDraft(
                    type=EvidenceType.metric,
                    source="prometheus",
                    source_reference=(
                        f"prometheus://query/{urllib.parse.quote(query.query, safe='')}"
                    ),
                    summary=f"Prometheus returned {output.result_type or 'unknown'} data.",
                    content=output.model_dump(mode="json"),
                )
            ],
        )
