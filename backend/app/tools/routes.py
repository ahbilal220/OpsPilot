from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from app.auth.dependencies import CurrentUser, Session, require_roles, trusted_origin
from app.auth.models import Role
from app.incidents.models import IncidentStatus
from app.incidents.routes import get_incident_or_404
from app.investigations.models import Investigation
from app.tools.contracts import ToolContext, ToolDefinition, ToolInvokeRequest, ToolResult
from app.tools.errors import ToolInputError, ToolPolicyDenied, UnknownToolError
from app.tools.gateway import ToolGateway
from app.tools.models import ToolExecution
from app.tools.schemas import ToolExecutionPublic

router = APIRouter(tags=["tool gateway"])
invoke_access = [
    Depends(trusted_origin),
    Depends(require_roles(Role.engineer, Role.admin)),
]


@router.get("/tools", response_model=list[ToolDefinition])
async def list_tools(request: Request, user: CurrentUser) -> list[ToolDefinition]:
    gateway = cast(ToolGateway, request.app.state.tool_gateway)
    return gateway.registry.definitions()


@router.get("/incidents/{incident_id}/tool-executions", response_model=list[ToolExecutionPublic])
async def list_tool_executions(
    incident_id: UUID, session: Session, user: CurrentUser
) -> list[ToolExecution]:
    await get_incident_or_404(session, incident_id)
    investigation = await session.scalar(
        select(Investigation).where(Investigation.incident_id == incident_id)
    )
    if investigation is None:
        return []
    return list(
        await session.scalars(
            select(ToolExecution)
            .where(ToolExecution.investigation_id == investigation.id)
            .order_by(ToolExecution.created_at, ToolExecution.id)
        )
    )


@router.post(
    "/incidents/{incident_id}/tools/{tool_name}/execute",
    response_model=ToolResult,
    dependencies=invoke_access,
)
async def invoke_tool(
    incident_id: UUID,
    tool_name: str,
    body: ToolInvokeRequest,
    session: Session,
    user: CurrentUser,
    request: Request,
) -> ToolResult:
    incident = await get_incident_or_404(session, incident_id)
    investigation = await session.scalar(
        select(Investigation).where(Investigation.incident_id == incident_id)
    )
    if investigation is None:
        raise HTTPException(409, "Incident has no investigation")
    gateway = cast(ToolGateway, request.app.state.tool_gateway)
    allowed = (
        gateway.registry.names
        if incident.status == IncidentStatus.investigating and investigation.status == "started"
        else frozenset()
    )
    context = ToolContext(
        incident_id=incident_id,
        investigation_id=investigation.id,
        actor_id=str(user.id),
        allowed_tools=allowed,
    )
    try:
        return await gateway.execute(session, context, tool_name, body.arguments)
    except ToolInputError as exc:
        raise HTTPException(422, str(exc)) from None
    except (ToolPolicyDenied, UnknownToolError) as exc:
        raise HTTPException(403, str(exc)) from None
