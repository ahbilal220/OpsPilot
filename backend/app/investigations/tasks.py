import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.agents.graph import InvestigationGraph
from app.audit.events import record_event
from app.audit.models import ActorType
from app.auth.models import User  # noqa: F401 -- registers the incident FK target
from app.core.config import Settings
from app.incidents.models import Incident, IncidentStatus
from app.investigations.celery_app import celery_app
from app.investigations.models import Investigation
from app.providers.bootstrap import build_model_router
from app.tools.bootstrap import build_tool_gateway


async def mark_investigation_started(investigation_id: UUID) -> dict[str, str]:
    settings = Settings()
    engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            investigation = await session.scalar(
                select(Investigation).where(Investigation.id == investigation_id).with_for_update()
            )
            if investigation is None:
                return {"status": "missing", "investigation_id": str(investigation_id)}
            if investigation.status in {"started", "cancelled"}:
                return {
                    "status": investigation.status,
                    "investigation_id": str(investigation_id),
                }
            incident = await session.get(Incident, investigation.incident_id)
            if incident is None or incident.status == IncidentStatus.cancelled:
                investigation.status = "cancelled"
                investigation.current_node = "cancelled"
                return {"status": "cancelled", "investigation_id": str(investigation_id)}
            now = datetime.now(UTC)
            investigation.status = "started"
            investigation.current_node = "phase_1_started"
            investigation.started_at = now
            incident.status = IncidentStatus.investigating
            incident.started_at = incident.started_at or now
            record_event(
                session,
                incident_id=incident.id,
                actor_type=ActorType.system,
                actor_id="worker",
                event_type="investigation.started",
                payload={"investigation_id": str(investigation.id)},
            )
        return {"status": "started", "investigation_id": str(investigation_id)}
    finally:
        await engine.dispose()


@celery_app.task(name="opspilot.investigations.start")  # type: ignore[untyped-decorator]
def start_investigation(investigation_id: str) -> dict[str, str]:
    return asyncio.run(run_investigation_workflow(UUID(investigation_id)))


async def run_investigation_workflow(investigation_id: UUID) -> dict[str, str]:
    settings = Settings()
    engine = create_async_engine(settings.database_url.get_secret_value(), pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        graph = InvestigationGraph(
            settings,
            factory,
            build_tool_gateway(settings, engine, factory),
            build_model_router(settings),
        )
        return await graph.run(investigation_id)
    finally:
        await engine.dispose()
