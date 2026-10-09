"""Exercise every Phase 2 tool through the running frontend proxy."""

import http.cookiejar
import json
import subprocess
import time
import urllib.error
import urllib.request
from uuid import uuid4

ORIGIN = "http://localhost:3000"
email = f"phase2-smoke-{uuid4()}@example.com"
password = "phase-two-smoke-password"
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
    {"email": email, "password": password, "name": "Phase 2 smoke"},
)
subprocess.run(
    [
        "docker",
        "--context",
        "desktop-linux",
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
        "title": "Phase 2 live tool acceptance",
        "description": "Verify each read-only evidence source and the denial audit.",
        "severity": "high",
    },
)
incident_id = incident["id"]
request(f"/api/v1/incidents/{incident_id}/investigate", {})

for _ in range(40):
    detail = request(f"/api/v1/incidents/{incident_id}")
    if detail["incident"]["status"] == "investigating":
        break
    time.sleep(0.25)
else:
    raise AssertionError("investigation worker did not start")

calls = {
    "logs.search": {"service": "checkout-api", "contains": "ignore prior", "limit": 20},
    "metrics.query": {"query": "up"},
    "repository.search": {"query": "query_recommendations", "limit": 20},
    "repository.history": {"limit": 10},
    "deployments.history": {
        "service": "checkout-api",
        "environment": "demo",
        "limit": 20,
    },
    "database.diagnostics": {"diagnostic": "overview"},
}
for tool_name, arguments in calls.items():
    result = request(
        f"/api/v1/incidents/{incident_id}/tools/{tool_name}/execute",
        {"arguments": arguments},
    )
    assert result["success"] is True, tool_name

try:
    request(
        f"/api/v1/incidents/{incident_id}/tools/host.shell/execute",
        {"arguments": {"command": "id"}},
    )
    raise AssertionError("unknown tool was accepted")
except urllib.error.HTTPError as exc:
    assert exc.code == 403

evidence = request(f"/api/v1/incidents/{incident_id}/evidence")
assert {item["type"] for item in evidence} == {
    "log",
    "metric",
    "code",
    "git",
    "deployment",
    "database",
}
assert "demo-secret-token-value" not in json.dumps(evidence)
assert "[REDACTED]" in json.dumps(evidence)
executions = request(f"/api/v1/incidents/{incident_id}/tool-executions")
assert len(executions) == 7
assert [item["status"] for item in executions].count("completed") == 6
assert [item["status"] for item in executions].count("denied") == 1
detail = request(f"/api/v1/incidents/{incident_id}")
event_types = [item["event_type"] for item in detail["timeline"]]
assert event_types.count("tool.completed") == 6
assert event_types.count("evidence.created") == 6
assert event_types.count("tool.policy_denied") == 1
print("PASS: 6 typed tools, 6 evidence records, audit trail, redaction, policy denial")
