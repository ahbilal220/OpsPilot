import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.models import Diagnosis, Hypothesis, HypothesisStatus
from app.agents.schemas import (
    DiagnosisDraft,
    EvidencePlan,
    HypothesisDraft,
    InvestigationState,
    PlannedToolCall,
    TriageResult,
    ValidationResult,
)
from app.agents.validation import ids_belong_to_evidence, validate_n_plus_one_hypothesis
from app.audit.events import record_event
from app.audit.models import ActorType
from app.core.config import Settings
from app.evidence.models import Evidence
from app.incidents.models import Incident, IncidentStatus, Service
from app.investigations.models import Investigation
from app.providers.contracts import ModelTask
from app.providers.router import ModelOutputError, ModelRouter
from app.tools.contracts import ToolContext, ToolRisk
from app.tools.gateway import ToolGateway

logger = logging.getLogger("opspilot.investigation")
GraphOutputT = TypeVar("GraphOutputT", bound=BaseModel)


class WorkflowStopped(Exception):
    pass


class InvestigationGraph:
    """Bounded explicit state graph for the deterministic Phase 3 vertical slice."""

    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        tool_gateway: ToolGateway,
        model_router: ModelRouter,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.tool_gateway = tool_gateway
        self.model_router = model_router

    async def run(self, investigation_id: UUID) -> dict[str, str]:
        try:
            async with asyncio.timeout(self.settings.investigation_max_seconds):
                return await self._run(investigation_id)
        except WorkflowStopped as exc:
            return await self._stop(investigation_id, str(exc))
        except Exception as exc:
            await self._fail(investigation_id, type(exc).__name__)
            return {"status": "failed", "investigation_id": str(investigation_id)}

    async def _run(self, investigation_id: UUID) -> dict[str, str]:
        async with self.session_factory() as session:
            investigation = await session.scalar(
                select(Investigation).where(Investigation.id == investigation_id).with_for_update()
            )
            if investigation is None:
                return {"status": "missing", "investigation_id": str(investigation_id)}
            if investigation.status in {"completed", "inconclusive", "cancelled"}:
                return {
                    "status": investigation.status,
                    "investigation_id": str(investigation_id),
                }
            if investigation.status == "running":
                return {"status": "running", "investigation_id": str(investigation_id)}
            incident = await session.get(Incident, investigation.incident_id)
            if incident is None:
                raise RuntimeError("Investigation incident is missing")
            if incident.status == IncidentStatus.cancelled:
                investigation.status = "cancelled"
                investigation.current_node = "cancelled"
                investigation.completed_at = datetime.now(UTC)
                await session.commit()
                return {"status": "cancelled", "investigation_id": str(investigation_id)}

            first_start = investigation.started_at is None
            now = datetime.now(UTC)
            investigation.status = "running"
            investigation.current_node = "triage"
            investigation.started_at = investigation.started_at or now
            incident.started_at = incident.started_at or now
            incident.status = IncidentStatus.investigating
            if first_start:
                record_event(
                    session,
                    incident_id=incident.id,
                    actor_type=ActorType.system,
                    actor_id="worker",
                    event_type="investigation.started",
                    payload={"investigation_id": str(investigation.id)},
                )
            state = InvestigationState(
                incident_id=incident.id,
                investigation_id=investigation.id,
                incident_summary=f"{incident.title}\n{incident.description}",
                tool_budget_remaining=self.settings.investigation_tool_budget,
                model_budget_usd_remaining=self.settings.investigation_model_budget_usd,
            )
            await self._persist(session, investigation, state)

            service = (
                await session.get(Service, incident.service_id) if incident.service_id else None
            )
            await self._enter_node(session, investigation, state, "triage")
            triage = await self._model(
                session,
                investigation,
                state,
                task=ModelTask.classification,
                operation="triage",
                output_model=TriageResult,
                input_data={
                    "incident_summary": state.incident_summary,
                    "severity": incident.severity.value,
                    "service_name": service.name if service else None,
                },
            )
            state.affected_services = triage.affected_services
            state.initial_categories = triage.initial_categories
            state.scope_supported = triage.scope_supported
            record_event(
                session,
                incident_id=incident.id,
                actor_type=ActorType.agent,
                actor_id="triage",
                event_type="triage.completed",
                payload={
                    "affected_services": triage.affected_services,
                    "categories": triage.initial_categories,
                    "scope_supported": triage.scope_supported,
                },
            )
            await self._persist(session, investigation, state)
            if not triage.scope_supported:
                state.blockers.append(triage.scope_reason)
                return await self._inconclusive(session, incident, investigation, state)

            await self._enter_node(session, investigation, state, "planning")
            plan = await self._model(
                session,
                investigation,
                state,
                task=ModelTask.planning,
                operation="evidence_plan",
                output_model=EvidencePlan,
                input_data={
                    "scope_supported": state.scope_supported,
                    "affected_services": state.affected_services,
                    "categories": state.initial_categories,
                },
            )
            state.planned_calls = self._allowed_plan(plan)
            record_event(
                session,
                incident_id=incident.id,
                actor_type=ActorType.agent,
                actor_id="planner",
                event_type="investigation.plan_created",
                payload={"tools": [call.tool_name for call in state.planned_calls]},
            )
            await self._persist(session, investigation, state)
            if not state.planned_calls:
                state.blockers.append("The bounded planner produced no allowed read-only calls.")
                return await self._inconclusive(session, incident, investigation, state)

            await self._enter_node(session, investigation, state, "evidence_collection")
            failed_calls = await self._collect(session, investigation, state, state.planned_calls)
            if not state.evidence_ids:
                state.blockers.append("No evidence was collected.")
                return await self._inconclusive(session, incident, investigation, state)

            await self._enter_node(session, investigation, state, "hypothesis_creation")
            evidence = await self._evidence(session, state)
            draft = await self._model(
                session,
                investigation,
                state,
                task=ModelTask.reasoning,
                operation="hypothesis",
                output_model=HypothesisDraft,
                input_data={
                    "evidence_ids": [str(item.id) for item in evidence],
                    "evidence": [
                        {"id": str(item.id), "type": item.type.value, "summary": item.summary}
                        for item in evidence
                    ],
                },
            )
            if not ids_belong_to_evidence(draft.supporting_evidence_ids, evidence):
                raise ModelOutputError("Hypothesis cited unavailable evidence")
            hypothesis = Hypothesis(
                investigation_id=investigation.id,
                title=draft.title,
                description=draft.description,
                confidence=Decimal("0"),
                status=HypothesisStatus.proposed.value,
                supporting_evidence_ids=[str(item) for item in draft.supporting_evidence_ids],
                contradicting_evidence_ids=[str(item) for item in draft.contradicting_evidence_ids],
                validation_plan=draft.validation_plan,
            )
            session.add(hypothesis)
            await session.flush()
            state.hypothesis_ids.append(hypothesis.id)
            state.selected_hypothesis_id = hypothesis.id
            record_event(
                session,
                incident_id=incident.id,
                actor_type=ActorType.agent,
                actor_id="hypothesis",
                event_type="hypothesis.created",
                payload={"hypothesis_id": str(hypothesis.id), "title": hypothesis.title},
            )
            await self._persist(session, investigation, state)

            validation = await self._validate(session, incident, investigation, state, hypothesis)
            if validation.status != HypothesisStatus.supported.value and failed_calls:
                retryable = failed_calls[: state.tool_budget_remaining]
                if retryable:
                    await self._enter_node(session, investigation, state, "more_evidence")
                    await self._collect(session, investigation, state, retryable)
                    validation = await self._validate(
                        session, incident, investigation, state, hypothesis
                    )
            if (
                validation.status != HypothesisStatus.supported.value
                or validation.confidence < self.settings.diagnosis_confidence_threshold
            ):
                state.blockers.append(validation.summary)
                return await self._inconclusive(session, incident, investigation, state)

            await self._enter_node(session, investigation, state, "diagnosis")
            evidence = await self._evidence(session, state)
            diagnosis_draft = await self._model(
                session,
                investigation,
                state,
                task=ModelTask.reasoning,
                operation="diagnosis",
                output_model=DiagnosisDraft,
                input_data={
                    "hypothesis_id": str(hypothesis.id),
                    "hypothesis": hypothesis.title,
                    "evidence_ids": hypothesis.supporting_evidence_ids,
                    "confidence": str(hypothesis.confidence),
                },
            )
            if not ids_belong_to_evidence(diagnosis_draft.evidence_ids, evidence):
                raise ModelOutputError("Diagnosis cited unavailable evidence")
            diagnosis = Diagnosis(
                incident_id=incident.id,
                investigation_id=investigation.id,
                root_cause=diagnosis_draft.root_cause,
                summary=diagnosis_draft.summary,
                confidence=hypothesis.confidence,
                evidence_ids=[str(item) for item in diagnosis_draft.evidence_ids],
                limitations=diagnosis_draft.limitations,
            )
            session.add(diagnosis)
            await session.flush()
            investigation.status = "completed"
            investigation.current_node = "diagnosis_ready"
            investigation.completed_at = datetime.now(UTC)
            incident.status = IncidentStatus.diagnosis_ready
            state.status = "completed"
            state.current_node = "diagnosis_ready"
            record_event(
                session,
                incident_id=incident.id,
                actor_type=ActorType.agent,
                actor_id="root-cause-synthesizer",
                event_type="diagnosis.ready",
                payload={
                    "diagnosis_id": str(diagnosis.id),
                    "hypothesis_id": str(hypothesis.id),
                    "confidence": str(hypothesis.confidence),
                    "evidence_ids": diagnosis.evidence_ids,
                },
            )
            await self._persist(session, investigation, state)
            logger.info(
                "investigation.completed",
                extra={
                    "incident_id": str(incident.id),
                    "investigation_id": str(investigation.id),
                    "status": "completed",
                },
            )
            return {"status": "completed", "investigation_id": str(investigation_id)}

    async def _model(
        self,
        session: AsyncSession,
        investigation: Investigation,
        state: InvestigationState,
        *,
        task: ModelTask,
        operation: str,
        output_model: type[GraphOutputT],
        input_data: dict[str, object],
    ) -> GraphOutputT:
        if state.model_budget_usd_remaining <= 0:
            raise WorkflowStopped("Model cost budget exhausted")
        result = await self.model_router.generate_structured(
            session,
            investigation_id=investigation.id,
            task=task,
            operation=operation,
            input_data=input_data,
            output_model=output_model,
        )
        await session.refresh(investigation)
        state.model_budget_usd_remaining = max(
            Decimal("0"),
            self.settings.investigation_model_budget_usd - investigation.llm_cost_usd,
        )
        return result

    def _allowed_plan(self, plan: EvidencePlan) -> list[PlannedToolCall]:
        definitions = {
            item.name: item
            for item in self.tool_gateway.registry.definitions()
            if item.read_only and item.risk in {ToolRisk.pure, ToolRisk.read}
        }
        return [call for call in plan.calls if call.tool_name in definitions]

    async def _collect(
        self,
        session: AsyncSession,
        investigation: Investigation,
        state: InvestigationState,
        calls: list[PlannedToolCall],
    ) -> list[PlannedToolCall]:
        allowed_calls = self._allowed_plan(EvidencePlan(calls=calls))
        allowed_tools = frozenset(call.tool_name for call in allowed_calls)
        failed: list[PlannedToolCall] = []
        for call in calls:
            await self._ensure_active(session, investigation, state)
            if state.tool_budget_remaining <= 0:
                state.blockers.append("Tool budget exhausted.")
                failed.append(call)
                continue
            state.tool_budget_remaining -= 1
            try:
                result = await self.tool_gateway.execute(
                    session,
                    ToolContext(
                        incident_id=state.incident_id,
                        investigation_id=state.investigation_id,
                        actor_id="orchestrator",
                        allowed_tools=allowed_tools,
                    ),
                    call.tool_name,
                    call.arguments,
                )
            except Exception:
                failed.append(call)
                continue
            if result.success:
                for evidence_id in result.evidence_ids:
                    if evidence_id not in state.evidence_ids:
                        state.evidence_ids.append(evidence_id)
            else:
                failed.append(call)
            await self._persist(session, investigation, state)
        return failed

    async def _validate(
        self,
        session: AsyncSession,
        incident: Incident,
        investigation: Investigation,
        state: InvestigationState,
        hypothesis: Hypothesis,
    ) -> ValidationResult:
        await self._enter_node(session, investigation, state, "hypothesis_validation")
        evidence = await self._evidence(session, state)
        result = validate_n_plus_one_hypothesis(hypothesis, evidence)
        record_event(
            session,
            incident_id=incident.id,
            actor_type=ActorType.agent,
            actor_id="validation",
            event_type="validation.completed",
            payload={
                "hypothesis_id": str(hypothesis.id),
                "status": result.status,
                "confidence": str(result.confidence),
                "checks": result.checks,
            },
        )
        record_event(
            session,
            incident_id=incident.id,
            actor_type=ActorType.agent,
            actor_id="validation",
            event_type="hypothesis.updated",
            payload={"hypothesis_id": str(hypothesis.id), "status": result.status},
        )
        await self._persist(session, investigation, state)
        return result

    async def _evidence(self, session: AsyncSession, state: InvestigationState) -> list[Evidence]:
        if not state.evidence_ids:
            return []
        return list(
            await session.scalars(
                select(Evidence)
                .where(
                    Evidence.incident_id == state.incident_id,
                    Evidence.id.in_(state.evidence_ids),
                )
                .order_by(Evidence.created_at, Evidence.id)
            )
        )

    async def _enter_node(
        self,
        session: AsyncSession,
        investigation: Investigation,
        state: InvestigationState,
        node: str,
    ) -> None:
        await self._ensure_active(session, investigation, state)
        if state.iteration_count >= self.settings.investigation_max_iterations:
            raise WorkflowStopped("Maximum investigation iterations reached")
        state.iteration_count += 1
        state.current_node = node
        investigation.current_node = node
        record_event(
            session,
            incident_id=state.incident_id,
            actor_type=ActorType.agent,
            actor_id="orchestrator",
            event_type="investigation.node_started",
            payload={"node": node, "iteration": state.iteration_count},
        )
        await self._persist(session, investigation, state)

    async def _ensure_active(
        self,
        session: AsyncSession,
        investigation: Investigation,
        state: InvestigationState,
    ) -> None:
        await session.refresh(investigation)
        if investigation.status == "cancelled":
            state.status = "cancelled"
            raise WorkflowStopped("Investigation was cancelled")

    async def _persist(
        self,
        session: AsyncSession,
        investigation: Investigation,
        state: InvestigationState,
    ) -> None:
        investigation.iteration_count = state.iteration_count
        investigation.state_snapshot = state.model_dump(mode="json")
        await session.commit()

    async def _inconclusive(
        self,
        session: AsyncSession,
        incident: Incident,
        investigation: Investigation,
        state: InvestigationState,
    ) -> dict[str, str]:
        state.status = "inconclusive"
        state.current_node = "inconclusive"
        investigation.status = "inconclusive"
        investigation.current_node = "inconclusive"
        investigation.completed_at = datetime.now(UTC)
        incident.status = IncidentStatus.failed
        record_event(
            session,
            incident_id=incident.id,
            actor_type=ActorType.agent,
            actor_id="orchestrator",
            event_type="investigation.inconclusive",
            payload={"blockers": state.blockers[:10]},
        )
        await self._persist(session, investigation, state)
        return {"status": "inconclusive", "investigation_id": str(investigation.id)}

    async def _fail(self, investigation_id: UUID, failure_type: str) -> None:
        async with self.session_factory() as session:
            investigation = await session.get(Investigation, investigation_id)
            if investigation is None or investigation.status in {"completed", "cancelled"}:
                return
            incident = await session.get(Incident, investigation.incident_id)
            investigation.status = "failed"
            investigation.current_node = "failed"
            investigation.completed_at = datetime.now(UTC)
            if incident is not None and incident.status != IncidentStatus.cancelled:
                incident.status = IncidentStatus.failed
                record_event(
                    session,
                    incident_id=incident.id,
                    actor_type=ActorType.system,
                    actor_id="orchestrator",
                    event_type="investigation.failed",
                    payload={"failure_type": failure_type},
                )
            await session.commit()
            logger.info(
                "investigation.failed",
                extra={
                    "incident_id": str(investigation.incident_id),
                    "investigation_id": str(investigation.id),
                    "status": "failed",
                },
            )

    async def _stop(self, investigation_id: UUID, reason: str) -> dict[str, str]:
        async with self.session_factory() as session:
            investigation = await session.get(Investigation, investigation_id)
            if investigation is None:
                return {"status": "missing", "investigation_id": str(investigation_id)}
            if investigation.status == "cancelled":
                return {"status": "cancelled", "investigation_id": str(investigation_id)}
            incident = await session.get(Incident, investigation.incident_id)
            investigation.status = "inconclusive"
            investigation.current_node = "inconclusive"
            investigation.completed_at = datetime.now(UTC)
            snapshot = dict(investigation.state_snapshot)
            blockers = list(snapshot.get("blockers", []))
            blockers.append(reason)
            snapshot.update(
                {
                    "status": "inconclusive",
                    "current_node": "inconclusive",
                    "blockers": blockers,
                }
            )
            investigation.state_snapshot = snapshot
            if incident is not None and incident.status != IncidentStatus.cancelled:
                incident.status = IncidentStatus.failed
                record_event(
                    session,
                    incident_id=incident.id,
                    actor_type=ActorType.agent,
                    actor_id="orchestrator",
                    event_type="investigation.inconclusive",
                    payload={"blockers": blockers[:10]},
                )
            await session.commit()
            return {"status": "inconclusive", "investigation_id": str(investigation_id)}
