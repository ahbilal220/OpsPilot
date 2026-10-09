import json
import logging
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import select, text

from app.auth.dependencies import require_roles
from app.auth.models import Role, User
from app.auth.security import COOKIE, password_hasher, session_key
from app.core.config import Settings
from app.telemetry.logging import JsonFormatter

ACCOUNT = {"email": "Engineer@example.com", "password": "a-long-test-password", "name": "Engineer"}


def test_render_postgres_url_uses_async_driver():
    settings = Settings(database_url="postgresql://user:password@example.test/opspilot")
    assert settings.database_url.get_secret_value().startswith("postgresql+asyncpg://")


async def register_login(client):
    response = await client.post("/api/v1/auth/register", json=ACCOUNT)
    assert response.status_code == 201
    response = await client.post(
        "/api/v1/auth/login", json={k: ACCOUNT[k] for k in ("email", "password")}
    )
    assert response.status_code == 200
    return response


async def test_health_readiness_and_request_id(client):
    http, app = client
    response = await http.get("/api/v1/health", headers={"X-Request-ID": "test-123"})
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"] == "test-123"
    assert (await http.get("/api/v1/ready")).status_code == 200
    assert (await http.get("/api/v1/health", headers={"X-Request-ID": "invalid id"})).headers[
        "X-Request-ID"
    ] != "invalid id"


async def test_auth_lifecycle_and_storage(client):
    http, app = client
    assert (await http.get("/api/v1/auth/me")).status_code == 401
    response = await register_login(http)
    assert response.json()["role"] == "viewer"
    assert response.json()["email"] == "engineer@example.com"
    assert "password" not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    token = http.cookies[COOKIE]
    assert token not in app.state.redis.values
    assert app.state.redis.ttls[session_key(token)] == 3600
    async with app.state.session_factory() as db:
        user = await db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        assert password_hasher.verify(ACCOUNT["password"], user.password_hash)
    assert (await http.get("/api/v1/auth/me")).status_code == 200
    assert (await http.post("/api/v1/auth/logout")).status_code == 200
    http.cookies.set(COOKIE, token)
    assert (await http.get("/api/v1/auth/me")).status_code == 401


async def test_session_rotation_expiration_and_deleted_user(client):
    http, app = client
    await register_login(http)
    old_token = http.cookies[COOKIE]
    await http.post("/api/v1/auth/login", json={k: ACCOUNT[k] for k in ("email", "password")})
    assert session_key(old_token) not in app.state.redis.values
    token = http.cookies[COOKIE]
    await app.state.redis.delete(
        session_key(token)
    )  # Redis expiry has the same missing-key behavior.
    assert (await http.get("/api/v1/auth/me")).status_code == 401
    await app.state.redis.set(session_key(token), str(uuid4()), ex=60)
    assert (await http.get("/api/v1/auth/me")).status_code == 401


async def test_wrong_password_and_unknown_user_same_error(client):
    http, _ = client
    await http.post("/api/v1/auth/register", json=ACCOUNT)
    payload = {"email": ACCOUNT["email"], "password": "wrong-long-password"}
    wrong = await http.post("/api/v1/auth/login", json=payload)
    unknown = await http.post(
        "/api/v1/auth/login", json={**payload, "email": "unknown@example.com"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


@pytest.mark.parametrize(
    "extra", [{"role": "admin"}, {"password": "short"}, {"email": "bad"}, {"name": "   "}]
)
async def test_registration_validation(client, extra):
    http, _ = client
    response = await http.post("/api/v1/auth/register", json={**ACCOUNT, **extra})
    assert response.status_code == 422
    assert ACCOUNT["password"] not in response.text
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_duplicate_and_disabled_registration(client):
    http, app = client
    assert (await http.post("/api/v1/auth/register", json=ACCOUNT)).status_code == 201
    assert (
        await http.post("/api/v1/auth/register", json={**ACCOUNT, "email": "engineer@example.com"})
    ).status_code == 409
    app.state.settings.registration_enabled = False
    assert (await http.post("/api/v1/auth/register", json=ACCOUNT)).status_code == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null", ""])
async def test_csrf_denied(client, origin):
    http, _ = client
    for path in ("register", "login", "logout"):
        assert (
            await http.post(f"/api/v1/auth/{path}", json=ACCOUNT, headers={"Origin": origin})
        ).status_code == 403


async def test_swagger_origin_is_trusted(client):
    http, app = client
    response = await http.post(
        "/api/v1/auth/register",
        json=ACCOUNT,
        headers={"Origin": app.state.settings.api_origin},
    )
    assert response.status_code == 201


@pytest.mark.parametrize("origin", ["http://127.0.0.1:3000", "http://127.0.0.1:8000"])
async def test_configured_loopback_aliases_are_trusted(client, origin):
    http, app = client
    app.state.settings.additional_trusted_origins = "http://127.0.0.1:3000,http://127.0.0.1:8000"
    response = await http.post(
        "/api/v1/auth/register",
        json={**ACCOUNT, "email": f"{origin[-4:]}@example.com"},
        headers={"Origin": origin},
    )
    assert response.status_code == 201


async def test_authorization(client):
    http, app = client
    from fastapi import Depends

    @app.get("/api/v1/test-admin", dependencies=[Depends(require_roles(Role.admin))])
    async def admin():
        return {"ok": True}

    assert (await http.get("/api/v1/test-admin")).status_code == 401
    await register_login(http)
    assert (await http.get("/api/v1/test-admin")).status_code == 403
    async with app.state.session_factory() as db:
        user = await db.scalar(select(User))
        user.role = Role.admin
        await db.commit()
    assert (await http.get("/api/v1/test-admin")).status_code == 200


async def test_dependency_failure_and_liveness(client):
    http, app = client

    async def unavailable(*args, **kwargs):
        raise RedisConnectionError("secret-redis-url")

    app.state.redis.ping = unavailable
    app.state.redis.eval = unavailable
    assert (await http.get("/api/v1/health")).status_code == 200
    assert (await http.get("/api/v1/ready")).status_code == 503
    response = await http.post(
        "/api/v1/auth/login", json={k: ACCOUNT[k] for k in ("email", "password")}
    )
    assert response.status_code == 503
    assert "secret-redis-url" not in response.text


async def test_readiness_checks_schema(client):
    http, app = client
    async with app.state.engine.begin() as conn:
        await conn.execute(text("DELETE FROM alembic_version"))
    assert (await http.get("/api/v1/ready")).status_code == 503


async def test_rate_limit(client):
    http, app = client
    app.state.redis.attempts = 20
    assert (await http.post("/api/v1/auth/login", json=ACCOUNT)).status_code == 429


async def test_error_envelope_and_unexpected_exception(client):
    http, app = client

    @app.get("/api/v1/test-error")
    async def fail():
        raise RuntimeError("sensitive-password")

    response = await http.get("/api/v1/test-error")
    assert response.status_code == 500
    assert "sensitive-password" not in response.text
    assert response.headers["X-Request-ID"]
    assert (await http.get("/missing")).json()["error"]["code"] == "HTTP_404"


def test_safe_config_defaults_and_logging(monkeypatch):
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    monkeypatch.delenv("REGISTRATION_ENABLED", raising=False)
    settings = Settings(_env_file=None)
    assert settings.cookie_secure
    assert not settings.registration_enabled
    record = logging.LogRecord("opspilot.auth", logging.INFO, "", 0, "auth.logged_in", (), None)
    record.password = "secret"
    record.actor_id = "user-id"
    data = json.loads(JsonFormatter().format(record))
    assert {
        "timestamp",
        "request_id",
        "incident_id",
        "investigation_id",
        "trace_id",
        "component",
        "event",
        "level",
    } <= data.keys()
    assert "secret" not in json.dumps(data)
    assert data["actor_id"] == "user-id"
