from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.agents.models import Diagnosis, Hypothesis
from app.agents.schemas import DiagnosisPublic, HypothesisPublic
from app.agents.validation import validate_n_plus_one_hypothesis
from app.audit.events import record_event
from app.audit.models import ActorType
from app.auth.dependencies import CurrentUser, Session, require_roles, trusted_origin
from app.auth.models import Role
from app.evidence.models import Evidence
from app.incidents.routes import get_incident_or_404
from app.investigations.models import Investigation
from app.providers.models import ModelExecution
from app.providers.schemas import ModelExecutionPublic

router = APIRouter(tags=["orchestrated investigation"])
write_access = [
    Depends(trusted_origin),
    Depends(require_roles(Role.engineer, Role.admin)),
]


async def get_investigation(session: Session, incident_id: UUID) -> Investigation | None:
    return cast(
        Investigation | None,
        await session.scalar(select(Investigation).where(Investigation.incident_id == incident_id)),
    )


@router.get("/incidents/{incident_id}/hypotheses", response_model=list[HypothesisPublic])
async def list_hypotheses(
    incident_id: UUID, session: Session, user: CurrentUser
) -> list[Hypothesis]:
    await get_incident_or_404(session, incident_id)
    investigation = await get_investigation(session, incident_id)
    if investigation is None:
        return []
    return list(
        await session.scalars(
            select(Hypothesis)
            .where(Hypothesis.investigation_id == investigation.id)
            .order_by(Hypothesis.created_at, Hypothesis.id)
        )
    )


@router.get("/incidents/{incident_id}/diagnosis", response_model=DiagnosisPublic | None)
async def get_diagnosis(incident_id: UUID, session: Session, user: CurrentUser) -> Diagnosis | None:
    await get_incident_or_404(session, incident_id)
    return cast(
        Diagnosis | None,
        await session.scalar(select(Diagnosis).where(Diagnosis.incident_id == incident_id)),
    )


@router.get(
    "/incidents/{incident_id}/model-executions",
    response_model=list[ModelExecutionPublic],
)
async def list_model_executions(
    incident_id: UUID, session: Session, user: CurrentUser
) -> list[ModelExecution]:
    await get_incident_or_404(session, incident_id)
    investigation = await get_investigation(session, incident_id)
    if investigation is None:
        return []
    return list(
        await session.scalars(
            select(ModelExecution)
            .where(ModelExecution.investigation_id == investigation.id)
            .order_by(ModelExecution.created_at, ModelExecution.id)
        )
    )


@router.post(
    "/incidents/{incident_id}/hypotheses/{hypothesis_id}/validate",
    response_model=HypothesisPublic,
    dependencies=write_access,
)
async def validate_hypothesis(
    incident_id: UUID,
    hypothesis_id: UUID,
    session: Session,
    user: CurrentUser,
) -> Hypothesis:
    await get_incident_or_404(session, incident_id)
    investigation = await get_investigation(session, incident_id)
    if investigation is None:
        raise HTTPException(409, "Incident has no investigation")
    hypothesis = await session.get(Hypothesis, hypothesis_id)
    if hypothesis is None or hypothesis.investigation_id != investigation.id:
        raise HTTPException(404, "Hypothesis not found")
    evidence = list(
        await session.scalars(
            select(Evidence)
            .where(Evidence.incident_id == incident_id)
            .order_by(Evidence.created_at, Evidence.id)
        )
    )
    result = validate_n_plus_one_hypothesis(hypothesis, evidence)
    record_event(
        session,
        incident_id=incident_id,
        actor_type=ActorType.user,
        actor_id=str(user.id),
        event_type="validation.completed",
        payload={
            "hypothesis_id": str(hypothesis.id),
            "status": result.status,
            "confidence": str(result.confidence),
            "manual": True,
        },
    )
    await session.commit()
    await session.refresh(hypothesis)
    return hypothesis
