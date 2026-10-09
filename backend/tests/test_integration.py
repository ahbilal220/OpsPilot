"""Run against disposable, migrated PostgreSQL and Redis: RUN_INTEGRATION=1 pytest."""

import asyncio
import os
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.agents.graph import InvestigationGraph
from app.agents.models import Diagnosis, Hypothesis
from app.auth.models import Role, User
from app.auth.security import COOKIE, session_key
from app.core.config import Settings
from app.incidents.models import IncidentStatus
from app.investigations.tasks import mark_investigation_started
from app.main import create_app
from app.providers.bootstrap import build_model_router

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="requires PostgreSQL and Redis"),
]


async def test_real_services_login_logout_and_expiry():
    settings = Settings(cookie_secure=False, registration_enabled=True)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": settings.frontend_origin},
        ) as http:
            assert (await http.get("/api/v1/ready")).status_code == 200
            credentials = {"email": f"{uuid4()}@example.com", "password": "integration-password"}
            response = await http.post(
                "/api/v1/auth/register", json={**credentials, "name": "Integration"}
            )
            assert response.status_code == 201
            assert (await http.post("/api/v1/auth/login", json=credentials)).status_code == 200
            token = http.cookies[COOKIE]
            assert await app.state.redis.ttl(session_key(token)) > 0
            assert (await http.get("/api/v1/auth/me")).status_code == 200
            assert (await http.post("/api/v1/auth/logout")).status_code == 200
            assert await app.state.redis.get(session_key(token)) is None
            assert (await http.post("/api/v1/auth/login", json=credentials)).status_code == 200
            await app.state.redis.expire(session_key(http.cookies[COOKIE]), 1)
            await asyncio.sleep(1.1)
            assert (await http.get("/api/v1/auth/me")).status_code == 401


async def test_real_incident_queue_and_worker_start():
    settings = Settings(cookie_secure=False, registration_enabled=True)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        task_id = f"integration-{uuid4()}"
        app.state.enqueue_investigation = lambda _: task_id
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": settings.frontend_origin},
        ) as http:
            credentials = {
                "email": f"{uuid4()}@example.com",
                "password": "integration-password",
            }
            response = await http.post(
                "/api/v1/auth/register", json={**credentials, "name": "Incident Engineer"}
            )
            assert response.status_code == 201
            async with app.state.session_factory() as session:
                user = await session.scalar(select(User).where(User.email == credentials["email"]))
                assert user is not None
                user.role = Role.engineer
                await session.commit()
            assert (await http.post("/api/v1/auth/login", json=credentials)).status_code == 200

            service = await http.post(
                "/api/v1/services",
                json={"name": f"integration-{uuid4()}", "environment": "test"},
            )
            assert service.status_code == 201
            incident = await http.post(
                "/api/v1/incidents",
                json={
                    "title": "Integration incident",
                    "description": "Verify the real PostgreSQL incident path.",
                    "severity": "high",
                    "service_id": service.json()["id"],
                },
            )
            assert incident.status_code == 201
            incident_id = incident.json()["id"]
            accepted = await http.post(f"/api/v1/incidents/{incident_id}/investigate")
            assert accepted.status_code == 202
            assert accepted.json()["task_id"] == task_id

            started = await mark_investigation_started(accepted.json()["investigation_id"])
            assert started["status"] == "started"
            detail = await http.get(f"/api/v1/incidents/{incident_id}")
            assert detail.status_code == 200
            body = detail.json()
            assert body["incident"]["status"] == IncidentStatus.investigating
            assert body["investigation"]["current_node"] == "phase_1_started"
            assert [event["event_type"] for event in body["timeline"]] == [
                "incident.created",
                "investigation.queued",
                "investigation.started",
            ]
            diagnostic = await http.post(
                f"/api/v1/incidents/{incident_id}/tools/database.diagnostics/execute",
                json={"arguments": {"diagnostic": "overview"}},
            )
            assert diagnostic.status_code == 200
            assert diagnostic.json()["success"] is True
            evidence = await http.get(f"/api/v1/incidents/{incident_id}/evidence?type=database")
            assert evidence.status_code == 200
            assert len(evidence.json()) == 1


async def test_real_phase_three_n_plus_one_diagnosis():
    settings = Settings(cookie_secure=False, registration_enabled=True)
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        app.state.enqueue_investigation = lambda _: f"phase-three-{uuid4()}"
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Origin": settings.frontend_origin},
        ) as http:
            credentials = {
                "email": f"{uuid4()}@example.com",
                "password": "phase-three-password",
            }
            assert (
                await http.post(
                    "/api/v1/auth/register",
                    json={**credentials, "name": "Phase Three Engineer"},
                )
            ).status_code == 201
            async with app.state.session_factory() as session:
                user = await session.scalar(select(User).where(User.email == credentials["email"]))
                assert user is not None
                user.role = Role.engineer
                await session.commit()
            assert (await http.post("/api/v1/auth/login", json=credentials)).status_code == 200
            incident = await http.post(
                "/api/v1/incidents",
                json={
                    "title": "Checkout recommendation latency regression",
                    "description": (
                        "p95 latency and database queries increased after the latest deployment."
                    ),
                    "severity": "high",
                },
            )
            assert incident.status_code == 201
            incident_id = incident.json()["id"]
            accepted = await http.post(f"/api/v1/incidents/{incident_id}/investigate")
            assert accepted.status_code == 202
            graph = InvestigationGraph(
                settings,
                app.state.session_factory,
                app.state.tool_gateway,
                build_model_router(settings),
            )
            result = await graph.run(UUID(accepted.json()["investigation_id"]))
            assert result["status"] == "completed"
            detail = await http.get(f"/api/v1/incidents/{incident_id}")
            assert detail.json()["incident"]["status"] == "diagnosis_ready"
            assert len(detail.json()["diagnosis"]["evidence_ids"]) == 6
            async with app.state.session_factory() as session:
                assert (
                    await session.scalar(
                        select(Hypothesis).where(
                            Hypothesis.investigation_id == UUID(accepted.json()["investigation_id"])
                        )
                    )
                    is not None
                )
                assert (
                    await session.scalar(
                        select(Diagnosis).where(Diagnosis.incident_id == UUID(incident_id))
                    )
                    is not None
                )
