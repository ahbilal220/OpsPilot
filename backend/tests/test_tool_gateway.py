import asyncio
import shutil
import subprocess
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select

from app.auth.models import Role, User
from app.evidence.models import Evidence
from app.investigations.models import Investigation
from app.investigations.tasks import mark_investigation_started
from app.tools.adapters.prometheus import MetricsInput, PrometheusMetricsTool
from app.tools.adapters.repository import GitHistoryInput, GitHistoryTool, RepositorySearchTool
from app.tools.contracts import AdapterResult, EvidenceDraft, ToolContext, ToolDefinition, ToolRisk
from app.tools.gateway import ToolGateway
from app.tools.models import ToolExecution
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolRegistry

ACCOUNT = {
    "email": "phase-two@example.com",
    "password": "phase-two-password",
    "name": "Phase Two Engineer",
}


async def prepare_investigation(http, app, role: Role = Role.engineer) -> tuple[str, UUID]:
    assert (await http.post("/api/v1/auth/register", json=ACCOUNT)).status_code == 201
    async with app.state.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == ACCOUNT["email"]))
        assert user is not None
        user.role = Role.engineer
        await session.commit()
    assert (
        await http.post(
            "/api/v1/auth/login",
            json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]},
        )
    ).status_code == 200
    incident = await http.post(
        "/api/v1/incidents",
        json={
            "title": "N+1 diagnostic fixture",
            "description": "Checkout latency and query count increased.",
            "severity": "high",
        },
    )
    assert incident.status_code == 201
    incident_id = incident.json()["id"]
    dispatched: list[UUID] = []

    def enqueue(identifier: UUID) -> str:
        dispatched.append(identifier)
        return "phase-two-task"

    app.state.enqueue_investigation = enqueue
    assert (await http.post(f"/api/v1/incidents/{incident_id}/investigate")).status_code == 202
    assert (await mark_investigation_started(dispatched[0]))["status"] == "started"
    if role != Role.engineer:
        async with app.state.session_factory() as session:
            user = await session.scalar(select(User).where(User.email == ACCOUNT["email"]))
            assert user is not None
            user.role = role
            await session.commit()
    return incident_id, dispatched[0]


async def test_catalog_tool_execution_audit_evidence_and_redaction(client):
    http, app = client
    incident_id, investigation_id = await prepare_investigation(http, app)
    catalog = await http.get("/api/v1/tools")
    assert catalog.status_code == 200
    assert {item["name"] for item in catalog.json()} == {
        "database.diagnostics",
        "deployments.history",
        "logs.search",
        "metrics.query",
        "repository.history",
        "repository.search",
    }

    response = await http.post(
        f"/api/v1/incidents/{incident_id}/tools/logs.search/execute",
        json={"arguments": {"service": "checkout-api", "contains": "ignore prior"}},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["evidence_ids"]
    assert "demo-secret-token-value" not in response.text
    assert "[REDACTED]" in response.text

    evidence = await http.get(f"/api/v1/incidents/{incident_id}/evidence?type=log")
    assert evidence.status_code == 200
    assert len(evidence.json()) == 1
    assert evidence.json()[0]["content_hash"]
    executions = await http.get(f"/api/v1/incidents/{incident_id}/tool-executions")
    assert executions.status_code == 200
    assert executions.json()[0]["status"] == "completed"
    async with app.state.session_factory() as session:
        investigation = await session.get(Investigation, investigation_id)
        assert investigation is not None
        assert investigation.tool_calls_count == 1
        stored = await session.scalar(select(Evidence))
        assert stored is not None
        assert "demo-secret-token-value" not in stored.content


async def test_gateway_denies_unknown_and_wrong_workflow_state(client):
    http, app = client
    incident_id, _ = await prepare_investigation(http, app)
    unknown = await http.post(
        f"/api/v1/incidents/{incident_id}/tools/host.shell/execute",
        json={"arguments": {"command": "id"}},
    )
    assert unknown.status_code == 403
    await http.post(f"/api/v1/incidents/{incident_id}/cancel")
    denied = await http.post(
        f"/api/v1/incidents/{incident_id}/tools/logs.search/execute",
        json={"arguments": {"service": "checkout-api"}},
    )
    assert denied.status_code == 403
    async with app.state.session_factory() as session:
        records = list(
            await session.scalars(select(ToolExecution).order_by(ToolExecution.created_at))
        )
        assert [record.status for record in records] == ["denied", "denied"]


async def test_viewer_cannot_invoke_tools(client):
    http, app = client
    incident_id, _ = await prepare_investigation(http, app, Role.viewer)
    response = await http.post(
        f"/api/v1/incidents/{incident_id}/tools/logs.search/execute",
        json={"arguments": {"service": "checkout-api"}},
    )
    assert response.status_code == 403


async def test_prometheus_adapter_encodes_query_and_normalizes_output():
    requested: list[str] = []

    def fetcher(url: str, timeout: float):
        requested.append(url)
        assert timeout == 6.0
        return {
            "status": "success",
            "data": {"resultType": "vector", "result": [{"value": [1, "2"]}]},
        }

    tool = PrometheusMetricsTool("http://prometheus:9090", fetcher)
    context = ToolContext(
        incident_id=UUID(int=1),
        investigation_id=UUID(int=2),
        actor_id="test",
        allowed_tools=frozenset({"metrics.query"}),
    )
    result = await tool.execute(context, MetricsInput(query="rate(http_requests_total[5m])"))
    assert result.data["status"] == "success"
    assert "%5B5m%5D" in requested[0]


async def test_repository_tools_are_read_only_and_path_constrained(tmp_path: Path):
    if shutil.which("git") is None:
        raise AssertionError("git is required for the repository adapter contract test")
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "service.py").write_text(
        "for item in items:\n    query(item)\n", encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "config", "user.name", "Fixture"], check=True)
    subprocess.run(
        ["git", "-C", str(repository), "config", "user.email", "fixture@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repository), "add", "service.py"], check=True)
    subprocess.run(["git", "-C", str(repository), "commit", "-qm", "Add query loop"], check=True)
    context = ToolContext(
        incident_id=UUID(int=1),
        investigation_id=UUID(int=2),
        actor_id="test",
        allowed_tools=frozenset({"repository.search", "repository.history"}),
    )
    search = RepositorySearchTool(repository)
    result = await search.execute(context, search.input_model(query="query"))
    assert result.data["matches"][0]["path"] == "service.py"
    history = GitHistoryTool(repository)
    commits = await history.execute(context, GitHistoryInput(limit=5))
    assert commits.data["commits"][0]["subject"] == "Add query loop"

    response = search.input_model.model_validate
    try:
        response({"query": "secret", "path": "../.env"})
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal should fail validation")


class EmptyInput(BaseModel):
    pass


class SlowTool:
    input_model = EmptyInput
    definition = ToolDefinition(
        name="fixture.slow",
        description="Timeout fixture",
        risk=ToolRisk.read,
        read_only=True,
        timeout_seconds=1,
        input_schema=EmptyInput.model_json_schema(),
        output_schema={},
    )

    async def execute(self, context: ToolContext, arguments: BaseModel) -> AdapterResult:
        await asyncio.sleep(2)
        return AdapterResult(
            summary="late",
            data={},
            evidence=[EvidenceDraft(type="log", source="fixture", summary="late", content={})],
        )


async def test_gateway_timeout_is_safe_and_audited(client):
    http, app = client
    incident_id, investigation_id = await prepare_investigation(http, app)
    registry = ToolRegistry()
    registry.register(SlowTool())
    gateway = ToolGateway(registry, ToolPolicy())
    context = ToolContext(
        incident_id=UUID(incident_id),
        investigation_id=investigation_id,
        actor_id="test",
        allowed_tools=frozenset({"fixture.slow"}),
    )
    async with app.state.session_factory() as session:
        result = await gateway.execute(session, context, "fixture.slow", {})
        assert result.success is False
        execution = await session.scalar(
            select(ToolExecution).where(ToolExecution.tool_name == "fixture.slow")
        )
        assert execution is not None
        assert execution.status == "failed"
        assert execution.error == "TimeoutError: tool execution failed"


def test_policy_blocks_mutating_tool_even_if_named_as_allowed():
    definition = ToolDefinition(
        name="fixture.write",
        description="Must remain disabled",
        risk=ToolRisk.external_write,
        read_only=False,
        timeout_seconds=1,
        input_schema={},
        output_schema={},
    )
    context = ToolContext(
        incident_id=UUID(int=1),
        investigation_id=UUID(int=2),
        actor_id="test",
        allowed_tools=frozenset({"fixture.write"}),
    )
    assert ToolPolicy().evaluate(definition, context).allowed is False
