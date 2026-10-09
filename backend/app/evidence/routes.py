from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, Session
from app.evidence.models import Evidence, EvidenceType
from app.evidence.schemas import EvidencePublic
from app.incidents.routes import get_incident_or_404

router = APIRouter(tags=["evidence"])


@router.get("/incidents/{incident_id}/evidence", response_model=list[EvidencePublic])
async def list_evidence(
    incident_id: UUID,
    session: Session,
    user: CurrentUser,
    evidence_type: Annotated[EvidenceType | None, Query(alias="type")] = None,
    tool: str | None = None,
) -> list[Evidence]:
    await get_incident_or_404(session, incident_id)
    query = select(Evidence).where(Evidence.incident_id == incident_id)
    if evidence_type is not None:
        query = query.where(Evidence.type == evidence_type)
    if tool is not None:
        query = query.where(Evidence.tool_name == tool)
    query = query.order_by(Evidence.created_at, Evidence.id)
    return list(await session.scalars(query))


@router.get("/evidence/{evidence_id}", response_model=EvidencePublic)
async def get_evidence(evidence_id: UUID, session: Session, user: CurrentUser) -> Evidence:
    evidence = await session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Evidence not found")
    return evidence
