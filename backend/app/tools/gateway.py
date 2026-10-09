import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.events import record_event
from app.audit.models import ActorType
from app.evidence.models import Evidence
from app.investigations.models import Investigation
from app.tools.contracts import AdapterResult, ToolContext, ToolResult
from app.tools.errors import ToolInputError, ToolPolicyDenied, UnknownToolError
from app.tools.models import ToolExecution
from app.tools.policy import ToolPolicy
from app.tools.registry import ToolRegistry
from app.tools.sanitization import sanitize

logger = logging.getLogger("opspilot.tools")


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        policy: ToolPolicy,
        *,
        max_output_chars: int = 50000,
    ) -> None:
        self.registry = registry
        self.policy = policy
        self.max_output_chars = max_output_chars

    def _bounded(self, value: Any) -> dict[str, Any]:
        sanitized = sanitize(value)
        if not isinstance(sanitized, dict):
            sanitized = {"value": sanitized}
        rendered = json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
        if len(rendered) <= self.max_output_chars:
            return sanitized
        return {
            "truncated": True,
            "original_chars": len(rendered),
            "preview": rendered[: self.max_output_chars],
        }

    async def _record_denial(
        self,
        session: AsyncSession,
        context: ToolContext,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str,
        risk: str = "unknown",
    ) -> None:
        execution = ToolExecution(
            investigation_id=context.investigation_id,
            tool_name=tool_name,
            risk_level=risk,
            input_data=self._bounded(arguments),
            status="denied",
            error=reason,
            duration_ms=0,
        )
        session.add(execution)
        record_event(
            session,
            incident_id=context.incident_id,
            actor_type=ActorType.system,
            actor_id="tool-policy",
            event_type="tool.policy_denied",
            payload={"tool_name": tool_name, "reason": reason},
        )
        await session.commit()
        logger.info(
            "tool.policy_denied",
            extra={
                "status": "denied",
                "duration_ms": 0,
                "incident_id": str(context.incident_id),
                "investigation_id": str(context.investigation_id),
                "tool_name": tool_name,
                "execution_id": str(execution.id),
                "risk_level": risk,
            },
        )

    async def execute(
        self,
        session: AsyncSession,
        context: ToolContext,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        try:
            adapter = self.registry.get(tool_name)
        except UnknownToolError:
            await self._record_denial(
                session, context, tool_name, arguments, "Tool is not registered"
            )
            raise

        try:
            validated = adapter.input_model.model_validate(arguments)
        except ValidationError:
            execution = ToolExecution(
                investigation_id=context.investigation_id,
                tool_name=tool_name,
                risk_level=adapter.definition.risk.value,
                input_data=self._bounded(arguments),
                status="failed",
                error="Input schema validation failed",
                duration_ms=0,
            )
            session.add(execution)
            record_event(
                session,
                incident_id=context.incident_id,
                actor_type=ActorType.system,
                actor_id="tool-gateway",
                event_type="tool.failed",
                payload={"tool_name": tool_name, "reason": "validation"},
            )
            await session.commit()
            logger.info(
                "tool.failed",
                extra={
                    "status": "failed",
                    "duration_ms": 0,
                    "incident_id": str(context.incident_id),
                    "investigation_id": str(context.investigation_id),
                    "tool_name": tool_name,
                    "execution_id": str(execution.id),
                    "risk_level": adapter.definition.risk.value,
                },
            )
            raise ToolInputError("Tool input failed schema validation") from None

        decision = self.policy.evaluate(adapter.definition, context)
        if not decision.allowed:
            await self._record_denial(
                session,
                context,
                tool_name,
                validated.model_dump(mode="json"),
                decision.reason,
                adapter.definition.risk.value,
            )
            raise ToolPolicyDenied(decision.reason)

        execution = ToolExecution(
            investigation_id=context.investigation_id,
            tool_name=tool_name,
            risk_level=adapter.definition.risk.value,
            input_data=self._bounded(validated.model_dump(mode="json")),
            status="running",
        )
        session.add(execution)
        await session.flush()
        record_event(
            session,
            incident_id=context.incident_id,
            actor_type=ActorType.user,
            actor_id=context.actor_id,
            event_type="tool.started",
            payload={"tool_name": tool_name, "execution_id": str(execution.id)},
        )
        await session.commit()
        logger.info(
            "tool.started",
            extra={
                "status": "running",
                "incident_id": str(context.incident_id),
                "investigation_id": str(context.investigation_id),
                "tool_name": tool_name,
                "execution_id": str(execution.id),
                "risk_level": adapter.definition.risk.value,
            },
        )

        started = time.perf_counter()
        result: AdapterResult | None = None
        try:
            for attempt in range(adapter.definition.retry_policy.max_attempts):
                try:
                    async with asyncio.timeout(adapter.definition.timeout_seconds):
                        result = await adapter.execute(context, validated)
                    break
                except Exception:
                    if attempt + 1 >= adapter.definition.retry_policy.max_attempts:
                        raise
                    await asyncio.sleep(adapter.definition.retry_policy.backoff_seconds)
            if result is None:
                raise RuntimeError("Tool returned no result")
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            execution.status = "failed"
            execution.duration_ms = duration_ms
            execution.error = f"{type(exc).__name__}: tool execution failed"
            investigation = await session.get(Investigation, context.investigation_id)
            if investigation is not None:
                investigation.tool_calls_count += 1
            record_event(
                session,
                incident_id=context.incident_id,
                actor_type=ActorType.system,
                actor_id="tool-gateway",
                event_type="tool.failed",
                payload={"tool_name": tool_name, "execution_id": str(execution.id)},
            )
            await session.commit()
            logger.info(
                "tool.failed",
                extra={
                    "status": "failed",
                    "duration_ms": duration_ms,
                    "incident_id": str(context.incident_id),
                    "investigation_id": str(context.investigation_id),
                    "tool_name": tool_name,
                    "execution_id": str(execution.id),
                    "risk_level": adapter.definition.risk.value,
                },
            )
            return ToolResult(
                execution_id=execution.id,
                success=False,
                summary="Tool execution failed safely.",
                data={},
                evidence_ids=[],
            )

        duration_ms = round((time.perf_counter() - started) * 1000)
        safe_data = self._bounded(result.data)
        evidence_ids = []
        for draft in result.evidence:
            content_data = sanitize(draft.content)
            rendered = json.dumps(content_data, sort_keys=True, default=str)
            if len(rendered) > self.max_output_chars:
                rendered = f"{rendered[: self.max_output_chars]}…[truncated]"
            evidence = Evidence(
                incident_id=context.incident_id,
                investigation_id=context.investigation_id,
                type=draft.type,
                source=str(sanitize(draft.source, max_chars=120)),
                source_reference=(
                    str(sanitize(draft.source_reference, max_chars=2000))
                    if draft.source_reference is not None
                    else None
                ),
                tool_name=tool_name,
                query=self._bounded(validated.model_dump(mode="json")),
                content=rendered,
                summary=str(sanitize(draft.summary, max_chars=2000)),
                content_hash=hashlib.sha256(rendered.encode()).hexdigest(),
                observed_at=draft.observed_at,
            )
            session.add(evidence)
            await session.flush()
            evidence_ids.append(evidence.id)
            record_event(
                session,
                incident_id=context.incident_id,
                actor_type=ActorType.system,
                actor_id="tool-gateway",
                event_type="evidence.created",
                payload={"evidence_id": str(evidence.id), "tool_name": tool_name},
            )

        execution.status = "completed"
        execution.duration_ms = duration_ms
        execution.output_data = safe_data
        investigation = await session.get(Investigation, context.investigation_id)
        if investigation is not None:
            investigation.tool_calls_count += 1
        record_event(
            session,
            incident_id=context.incident_id,
            actor_type=ActorType.system,
            actor_id="tool-gateway",
            event_type="tool.completed",
            payload={
                "tool_name": tool_name,
                "execution_id": str(execution.id),
                "evidence_ids": [str(identifier) for identifier in evidence_ids],
                "duration_ms": duration_ms,
            },
        )
        await session.commit()
        logger.info(
            "tool.completed",
            extra={
                "status": "completed",
                "duration_ms": duration_ms,
                "incident_id": str(context.incident_id),
                "investigation_id": str(context.investigation_id),
                "tool_name": tool_name,
                "execution_id": str(execution.id),
                "risk_level": adapter.definition.risk.value,
            },
        )
        return ToolResult(
            execution_id=execution.id,
            success=True,
            summary=str(sanitize(result.summary, max_chars=2000)),
            data=safe_data,
            evidence_ids=evidence_ids,
        )
