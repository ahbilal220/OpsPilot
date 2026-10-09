from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import ActorType, AuditEvent


def record_event(
    session: AsyncSession,
    *,
    incident_id: UUID | None,
    actor_type: ActorType,
    actor_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        incident_id=incident_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload or {},
    )
    session.add(event)
    return event
