"""Exercise the complete Phase 3 investigation through the frontend proxy."""

import http.cookiejar
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from decimal import Decimal
from uuid import uuid4

ORIGIN = "http://localhost:3000"
DOCKER_CONTEXT = os.environ.get("DOCKER_CONTEXT", "desktop-linux")
email = f"phase3-smoke-{uuid4()}@example.com"
password = "phase-three-smoke-password"
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        ORIGIN + path,
        data=data,
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
    )
    with client.open(req, timeout=15) as response:
        return json.load(response)


request(
    "/api/v1/auth/register",
    {"email": email, "password": password, "name": "Phase 3 smoke"},
)
subprocess.run(
    [
        "docker",
        "--context",
        DOCKER_CONTEXT,
        "compose",
        "exec",
        "-T",
        "api",
        "python",
        "-m",
        "app.auth.cli",
        "set-role",
        email,
        "engineer",
    ],
    check=True,
    capture_output=True,
    text=True,
)
request("/api/v1/auth/login", {"email": email, "password": password})
incident = request(
    "/api/v1/incidents",
    {
        "title": "Checkout recommendation latency regression",
        "description": (
            "Checkout p95 latency and database queries per request increased "
            "after the latest recommendation deployment."
        ),
        "severity": "high",
    },
)
incident_id = incident["id"]
request(f"/api/v1/incidents/{incident_id}/investigate", {})

detail = None
for _ in range(120):
    detail = request(f"/api/v1/incidents/{incident_id}")
    if detail["investigation"]["status"] in {
        "completed",
        "inconclusive",
        "failed",
        "cancelled",
    }:
        break
    time.sleep(0.25)
else:
    raise AssertionError("Phase 3 investigation did not reach a terminal state")

assert detail is not None
investigation = detail["investigation"]
assert investigation["status"] == "completed", investigation
assert investigation["current_node"] == "diagnosis_ready"
assert investigation["iteration_count"] <= 12
assert investigation["tool_calls_count"] == 6
assert Decimal(investigation["llm_cost_usd"]) <= Decimal("0.25")
assert detail["incident"]["status"] == "diagnosis_ready"
assert detail["remediation"] is None

evidence = request(f"/api/v1/incidents/{incident_id}/evidence")
evidence_ids = {item["id"] for item in evidence}
assert len(evidence) == 6
assert {item["type"] for item in evidence} == {
    "log",
    "metric",
    "code",
    "git",
    "deployment",
    "database",
}
assert "demo-secret-token-value" not in json.dumps(evidence)

hypotheses = request(f"/api/v1/incidents/{incident_id}/hypotheses")
assert len(hypotheses) == 1
hypothesis = hypotheses[0]
assert hypothesis["status"] == "supported"
assert Decimal(hypothesis["confidence"]) >= Decimal("0.75")
assert set(hypothesis["supporting_evidence_ids"]).issubset(evidence_ids)
assert hypothesis["validation_result"]["checks"] == {
    "latency_elevated": True,
    "query_count_elevated": True,
    "query_inside_loop": True,
    "recent_change_correlated": True,
}

diagnosis = request(f"/api/v1/incidents/{incident_id}/diagnosis")
assert diagnosis == detail["diagnosis"]
assert diagnosis["root_cause"] == "N+1 database queries in the recommendation loader"
assert Decimal(diagnosis["confidence"]) >= Decimal("0.75")
assert set(diagnosis["evidence_ids"]).issubset(evidence_ids)

model_executions = request(f"/api/v1/incidents/{incident_id}/model-executions")
assert len(model_executions) == 4
assert all(item["success"] for item in model_executions)
assert {item["provider"] for item in model_executions} == {"fixture"}

event_types = [item["event_type"] for item in detail["timeline"]]
for event_type in (
    "triage.completed",
    "investigation.plan_created",
    "hypothesis.created",
    "validation.completed",
    "hypothesis.updated",
    "diagnosis.ready",
):
    assert event_type in event_types
assert event_types.count("tool.completed") == 6
assert event_types.count("evidence.created") == 6

print(
    "PASS: bounded Phase 3 graph, 6-source evidence, supported hypothesis, "
    "cited N+1 diagnosis"
)
