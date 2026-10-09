"""Validate the running Compose stack through the frontend's same-origin API proxy."""
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
from uuid import uuid4

origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(origin + path, data=data, headers={
        "Content-Type": "application/json", "Origin": origin,
    })
    with client.open(req, timeout=10) as response:
        return json.load(response)


with client.open(origin, timeout=10) as response:
    assert b"OpsPilot" in response.read()
assert request("/api/v1/health")["status"] == "ok"
assert request("/api/v1/ready")["status"] == "ready"
credentials = {"email": f"smoke-{uuid4()}@example.com", "password": "smoke-test-password"}
assert request("/api/v1/auth/register", {**credentials, "name": "Smoke test"})["role"] == "viewer"
assert request("/api/v1/auth/login", credentials)["email"] == credentials["email"]
assert request("/api/v1/auth/me")["email"] == credentials["email"]
request("/api/v1/auth/logout", {})
try:
    request("/api/v1/auth/me")
    raise AssertionError("Logged-out session accepted")
except urllib.error.HTTPError as exc:
    assert exc.code == 401
print("PASS: frontend, health, readiness, registration, login, profile, logout")
