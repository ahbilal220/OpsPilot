import json
from uuid import UUID, uuid4

from sqlalchemy import select

from app.audit.models import AuditEvent
from app.auth.models import Role, User
from app.incidents.routes import serialize_sse
from app.investigations.models import Investigation
from app.investigations.tasks import mark_investigation_started

ACCOUNT = {
    "email": "phase-one@example.com",
    "password": "phase-one-password",
    "name": "Phase One Engineer",
}


async def login_as(client, app, role: Role = Role.engineer):
    assert (await client.post("/api/v1/auth/register", json=ACCOUNT)).status_code == 201
    async with app.state.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == ACCOUNT["email"]))
        assert user is not None
        user.role = role
        await session.commit()
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ACCOUNT["email"], "password": ACCOUNT["password"]},
    )
    assert response.status_code == 200
    return response.json()


async def create_service(client):
    response = await client.post(
        "/api/v1/services",
        json={
            "name": "checkout-api",
            "repository_url": "https://example.com/checkout.git",
            "default_branch": "main",
            "environment": "demo",
            "metadata": {"owner": "payments"},
        },
    )
    assert response.status_code == 201
    return response.json()


async def create_incident(client, service_id):
    response = await client.post(
        "/api/v1/incidents",
        json={
            "title": "Checkout latency regression",
            "description": "p95 latency increased after deployment",
            "severity": "high",
            "service_id": service_id,
        },
    )
    assert response.status_code == 201
    return response.json()


async def test_viewer_can_read_but_cannot_mutate(client):
    http, app = client
    await login_as(http, app, Role.viewer)
    assert (await http.get("/api/v1/services")).status_code == 200
    denied = await http.post(
        "/api/v1/incidents",
        json={"title": "Denied", "description": "Viewer write", "severity": "low"},
    )
    assert denied.status_code == 403


async def test_service_registry_and_incident_crud(client):
    http, app = client
    await login_as(http, app)
    service = await create_service(http)
    assert service["metadata"] == {"owner": "payments"}
    assert len((await http.get("/api/v1/services")).json()) == 1

    updated_service = await http.patch(
        f"/api/v1/services/{service['id']}",
        json={"environment": "staging", "metadata": {"owner": "platform"}},
    )
    assert updated_service.status_code == 200
    assert updated_service.json()["environment"] == "staging"

    incident = await create_incident(http, service["id"])
    assert incident["status"] == "created"
    filtered = await http.get("/api/v1/incidents?severity=high&status=created")
    assert [item["id"] for item in filtered.json()] == [incident["id"]]

    update = await http.patch(
        f"/api/v1/incidents/{incident['id']}",
        json={"severity": "critical", "title": "Checkout severely degraded"},
    )
    assert update.status_code == 200
    assert update.json()["severity"] == "critical"

    detail = await http.get(f"/api/v1/incidents/{incident['id']}")
    assert detail.status_code == 200
    assert [event["event_type"] for event in detail.json()["timeline"]] == [
        "incident.created",
        "incident.updated",
    ]
    assert detail.json()["diagnosis"] is None
    assert detail.json()["remediation"] is None

    cancelled = await http.post(f"/api/v1/incidents/{incident['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert (await http.post(f"/api/v1/incidents/{incident['id']}/cancel")).status_code == 200


async def test_investigation_start_is_queued_idempotent_and_processed(client):
    http, app = client
    await login_as(http, app)
    service = await create_service(http)
    incident = await create_incident(http, service["id"])
    dispatched = []

    def enqueue(investigation_id):
        dispatched.append(investigation_id)
        return "task-phase-one"

    app.state.enqueue_investigation = enqueue
    first = await http.post(f"/api/v1/incidents/{incident['id']}/investigate")
    second = await http.post(f"/api/v1/incidents/{incident['id']}/investigate")
    assert first.status_code == second.status_code == 202
    assert first.json()["investigation_id"] == second.json()["investigation_id"]
    assert first.json()["task_id"] == second.json()["task_id"] == "task-phase-one"
    assert len(dispatched) == 1

    result = await mark_investigation_started(uuid4())
    assert result["status"] == "missing"
    started = await mark_investigation_started(dispatched[0])
    assert started["status"] == "started"
    repeated = await mark_investigation_started(dispatched[0])
    assert repeated["status"] == "started"

    detail = (await http.get(f"/api/v1/incidents/{incident['id']}")).json()
    assert detail["incident"]["status"] == "investigating"
    assert detail["investigation"]["status"] == "started"
    assert detail["investigation"]["current_node"] == "phase_1_started"
    assert [event["event_type"] for event in detail["timeline"]] == [
        "incident.created",
        "investigation.queued",
        "investigation.started",
    ]


async def test_queue_failure_is_recorded_and_safe_to_retry(client):
    http, app = client
    await login_as(http, app)
    incident = await create_incident(http, None)

    def fail(_investigation_id):
        raise ConnectionError("broker secret")

    app.state.enqueue_investigation = fail
    response = await http.post(f"/api/v1/incidents/{incident['id']}/investigate")
    assert response.status_code == 503
    assert "broker secret" not in response.text
    detail = (await http.get(f"/api/v1/incidents/{incident['id']}")).json()
    assert detail["incident"]["status"] == "blocked"
    assert detail["investigation"]["status"] == "blocked"
    assert detail["timeline"][-1]["event_type"] == "investigation.queue_failed"


async def test_missing_resources_validation_and_edit_lock(client):
    http, app = client
    await login_as(http, app)
    assert (await http.get(f"/api/v1/incidents/{uuid4()}")).status_code == 404
    missing_service = await http.post(
        "/api/v1/incidents",
        json={
            "title": "Missing service",
            "description": "Invalid reference",
            "severity": "medium",
            "service_id": str(uuid4()),
        },
    )
    assert missing_service.status_code == 404
    incident = await create_incident(http, None)
    app.state.enqueue_investigation = lambda _identifier: "task-lock"
    assert (await http.post(f"/api/v1/incidents/{incident['id']}/investigate")).status_code == 202
    locked = await http.patch(f"/api/v1/incidents/{incident['id']}", json={"title": "Too late"})
    assert locked.status_code == 409


async def test_timeline_event_serialization_and_invalid_sse_cursor(client):
    http, app = client
    await login_as(http, app)
    incident = await create_incident(http, None)
    async with app.state.session_factory() as session:
        event = await session.scalar(
            select(AuditEvent).where(AuditEvent.incident_id == UUID(incident["id"]))
        )
        assert event is not None
        rendered = serialize_sse(event)
        assert rendered.startswith(f"id: {event.id}\nevent: incident.created\ndata: ")
        payload = json.loads(rendered.split("data: ", 1)[1])
        assert payload["event_type"] == "incident.created"
    response = await http.get(
        f"/api/v1/incidents/{incident['id']}/events",
        headers={"Last-Event-ID": "invalid"},
    )
    assert response.status_code == 400


async def test_cancellation_updates_investigation(client):
    http, app = client
    await login_as(http, app)
    incident = await create_incident(http, None)
    app.state.enqueue_investigation = lambda _identifier: "task-cancel"
    await http.post(f"/api/v1/incidents/{incident['id']}/investigate")
    assert (await http.post(f"/api/v1/incidents/{incident['id']}/cancel")).status_code == 200
    async with app.state.session_factory() as session:
        investigation = await session.scalar(select(Investigation))
        assert investigation is not None
        assert investigation.status == "cancelled"
        assert investigation.completed_at is not None
