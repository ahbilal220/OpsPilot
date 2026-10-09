import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.agents.models import Diagnosis
from app.agents.schemas import DiagnosisPublic
from app.audit.events import record_event
from app.audit.models import ActorType, AuditEvent
from app.auth.dependencies import CurrentUser, Session, require_roles, trusted_origin
from app.auth.models import Role
from app.incidents.models import Incident, IncidentSource, IncidentStatus, Service, Severity
from app.incidents.schemas import (
    IncidentCreate,
    IncidentDetail,
    IncidentPublic,
    IncidentUpdate,
    InvestigationAccepted,
    InvestigationPublic,
    ServiceCreate,
    ServicePublic,
    ServiceUpdate,
    TimelineEventPublic,
)
from app.investigations.models import Investigation

router = APIRouter(tags=["incident management"])
write_access = [
    Depends(trusted_origin),
    Depends(require_roles(Role.engineer, Role.admin)),
]


async def get_service_or_404(session: Session, service_id: UUID) -> Service:
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(404, "Service not found")
    return service


async def get_incident_or_404(session: Session, incident_id: UUID) -> Incident:
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(404, "Incident not found")
    return incident


@router.post(
    "/services",
    response_model=ServicePublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=write_access,
)
async def create_service(body: ServiceCreate, session: Session, user: CurrentUser) -> Service:
    service = Service(
        name=body.name,
        repository_url=str(body.repository_url) if body.repository_url else None,
        default_branch=body.default_branch,
        environment=body.environment,
        service_metadata=body.metadata,
    )
    session.add(service)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Service name already exists") from None
    await session.refresh(service)
    return service


@router.get("/services", response_model=list[ServicePublic])
async def list_services(session: Session, user: CurrentUser) -> list[Service]:
    return list(await session.scalars(select(Service).order_by(Service.name)))


@router.patch("/services/{service_id}", response_model=ServicePublic, dependencies=write_access)
async def update_service(
    service_id: UUID, body: ServiceUpdate, session: Session, user: CurrentUser
) -> Service:
    service = await get_service_or_404(session, service_id)
    values = body.model_dump(exclude_unset=True)
    if "repository_url" in values and values["repository_url"] is not None:
        values["repository_url"] = str(values["repository_url"])
    if "metadata" in values:
        values["service_metadata"] = values.pop("metadata")
    for field, value in values.items():
        setattr(service, field, value)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Service name already exists") from None
    await session.refresh(service)
    return service


@router.post(
    "/incidents",
    response_model=IncidentPublic,
    status_code=status.HTTP_201_CREATED,
    dependencies=write_access,
)
async def create_incident(body: IncidentCreate, session: Session, user: CurrentUser) -> Incident:
    if body.service_id is not None:
        await get_service_or_404(session, body.service_id)
    incident = Incident(
        title=body.title,
        description=body.description,
        severity=body.severity,
        status=IncidentStatus.created,
        source=IncidentSource.manual,
        service_id=body.service_id,
        created_by=user.id,
    )
    session.add(incident)
    await session.flush()
    record_event(
        session,
        incident_id=incident.id,
        actor_type=ActorType.user,
        actor_id=str(user.id),
        event_type="incident.created",
        payload={"severity": incident.severity.value},
    )
    await session.commit()
    await session.refresh(incident)
    return incident


@router.get("/incidents", response_model=list[IncidentPublic])
async def list_incidents(
    session: Session,
    user: CurrentUser,
    incident_status: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    severity: Severity | None = None,
    service: Annotated[UUID | None, Query(alias="service")] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Incident]:
    query = select(Incident)
    if incident_status is not None:
        query = query.where(Incident.status == incident_status)
    if severity is not None:
        query = query.where(Incident.severity == severity)
    if service is not None:
        query = query.where(Incident.service_id == service)
    if created_from is not None:
        query = query.where(Incident.created_at >= created_from)
    if created_to is not None:
        query = query.where(Incident.created_at <= created_to)
    query = query.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    return list(await session.scalars(query))


async def build_incident_detail(session: Session, incident: Incident) -> IncidentDetail:
    investigation = await session.scalar(
        select(Investigation).where(Investigation.incident_id == incident.id)
    )
    events = list(
        await session.scalars(
            select(AuditEvent)
            .where(AuditEvent.incident_id == incident.id)
            .order_by(AuditEvent.created_at, AuditEvent.id)
        )
    )
    diagnosis = await session.scalar(select(Diagnosis).where(Diagnosis.incident_id == incident.id))
    return IncidentDetail(
        incident=IncidentPublic.model_validate(incident),
        investigation=(
            InvestigationPublic.model_validate(investigation) if investigation else None
        ),
        timeline=[TimelineEventPublic.model_validate(event) for event in events],
        diagnosis=DiagnosisPublic.model_validate(diagnosis) if diagnosis else None,
    )


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
async def get_incident(incident_id: UUID, session: Session, user: CurrentUser) -> IncidentDetail:
    return await build_incident_detail(session, await get_incident_or_404(session, incident_id))


@router.patch("/incidents/{incident_id}", response_model=IncidentPublic, dependencies=write_access)
async def update_incident(
    incident_id: UUID, body: IncidentUpdate, session: Session, user: CurrentUser
) -> Incident:
    incident = await get_incident_or_404(session, incident_id)
    if incident.status != IncidentStatus.created:
        raise HTTPException(409, "Only newly created incidents can be edited")
    values = body.model_dump(exclude_unset=True)
    if "service_id" in values and values["service_id"] is not None:
        await get_service_or_404(session, values["service_id"])
    changes: list[str] = []
    for field, value in values.items():
        if getattr(incident, field) != value:
            setattr(incident, field, value)
            changes.append(field)
    if changes:
        record_event(
            session,
            incident_id=incident.id,
            actor_type=ActorType.user,
            actor_id=str(user.id),
            event_type="incident.updated",
            payload={"fields": sorted(changes)},
        )
    await session.commit()
    await session.refresh(incident)
    return incident


@router.post(
    "/incidents/{incident_id}/investigate",
    response_model=InvestigationAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=write_access,
)
async def investigate_incident(
    incident_id: UUID, request: Request, session: Session, user: CurrentUser
) -> InvestigationAccepted:
    incident = await session.scalar(
        select(Incident).where(Incident.id == incident_id).with_for_update()
    )
    if incident is None:
        raise HTTPException(404, "Incident not found")
    if incident.status in {IncidentStatus.cancelled, IncidentStatus.resolved}:
        raise HTTPException(409, "Incident cannot be investigated in its current state")
    investigation = await session.scalar(
        select(Investigation).where(Investigation.incident_id == incident.id)
    )
    if investigation is not None:
        return InvestigationAccepted(
            investigation_id=investigation.id,
            incident_id=incident.id,
            status=investigation.status,
            task_id=investigation.queue_task_id,
        )

    investigation = Investigation(incident_id=incident.id, status="queued", current_node="queued")
    session.add(investigation)
    incident.status = IncidentStatus.queued
    await session.flush()
    record_event(
        session,
        incident_id=incident.id,
        actor_type=ActorType.user,
        actor_id=str(user.id),
        event_type="investigation.queued",
        payload={"investigation_id": str(investigation.id)},
    )
    await session.commit()

    try:
        task_id = await run_in_threadpool(request.app.state.enqueue_investigation, investigation.id)
    except Exception:
        investigation.status = "blocked"
        investigation.current_node = "queue_unavailable"
        incident.status = IncidentStatus.blocked
        record_event(
            session,
            incident_id=incident.id,
            actor_type=ActorType.system,
            actor_id="api",
            event_type="investigation.queue_failed",
            payload={"investigation_id": str(investigation.id)},
        )
        await session.commit()
        raise HTTPException(503, "Investigation queue unavailable") from None

    investigation.queue_task_id = task_id
    await session.commit()
    return InvestigationAccepted(
        investigation_id=investigation.id,
        incident_id=incident.id,
        status=investigation.status,
        task_id=task_id,
    )


@router.post(
    "/incidents/{incident_id}/cancel",
    response_model=IncidentPublic,
    dependencies=write_access,
)
async def cancel_incident(incident_id: UUID, session: Session, user: CurrentUser) -> Incident:
    incident = await get_incident_or_404(session, incident_id)
    if incident.status == IncidentStatus.cancelled:
        return incident
    if incident.status == IncidentStatus.resolved:
        raise HTTPException(409, "Resolved incidents cannot be cancelled")
    incident.status = IncidentStatus.cancelled
    investigation = await session.scalar(
        select(Investigation).where(Investigation.incident_id == incident.id)
    )
    if investigation is not None:
        investigation.status = "cancelled"
        investigation.current_node = "cancelled"
        investigation.completed_at = datetime.now(UTC)
    record_event(
        session,
        incident_id=incident.id,
        actor_type=ActorType.user,
        actor_id=str(user.id),
        event_type="incident.cancelled",
    )
    await session.commit()
    await session.refresh(incident)
    return incident


def serialize_sse(event: AuditEvent) -> str:
    data = TimelineEventPublic.model_validate(event).model_dump_json()
    return f"id: {event.id}\nevent: {event.event_type}\ndata: {data}\n\n"


@router.get("/incidents/{incident_id}/events")
async def incident_events(
    incident_id: UUID,
    request: Request,
    session: Session,
    user: CurrentUser,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    await get_incident_or_404(session, incident_id)
    await session.close()
    try:
        cursor = UUID(last_event_id) if last_event_id else None
    except ValueError:
        raise HTTPException(400, "Invalid Last-Event-ID") from None

    async def stream() -> AsyncIterator[str]:
        last_seen = cursor
        heartbeat = 0
        while not await request.is_disconnected():
            async with request.app.state.session_factory() as event_session:
                events = list(
                    await event_session.scalars(
                        select(AuditEvent)
                        .where(AuditEvent.incident_id == incident_id)
                        .order_by(AuditEvent.created_at, AuditEvent.id)
                    )
                )
            start = 0
            if last_seen is not None:
                for index, event in enumerate(events):
                    if event.id == last_seen:
                        start = index + 1
                        break
            for event in events[start:]:
                last_seen = event.id
                yield serialize_sse(event)
            heartbeat += 1
            if heartbeat >= 15:
                heartbeat = 0
                yield ": keep-alive\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
