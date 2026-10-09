# ADR 010: Phase 3 bounded investigation state graph

- Status: accepted
- Date: 2026-10-03

## Context

Phase 3 must turn a queued incident into an evidence-backed diagnosis for the first
N+1-query scenario. The workflow must expose triage, planning, evidence collection,
hypothesis creation, validation, and root-cause synthesis as explicit states. It must
remain bounded, preserve the Phase 2 tool policy boundary, validate all model output,
and finish inconclusively instead of guessing when evidence or budget is insufficient.
Phase 3 must stop before retrieval-augmented generation, patch generation, sandbox
execution, approval, or remediation.

## Decision

`InvestigationGraph` is an explicit state-machine implementation equivalent to the
required LangGraph workflow. Its state is a typed `InvestigationState` snapshot stored
on the investigation after each node and tool call. The graph has no open-ended model
loop. It enforces a 12-node maximum, a 10-call tool budget, a USD 0.25 model-cost
budget, and a 60-second wall-clock limit. Unsupported scenarios, exhausted budgets,
missing evidence, failed validation, and cancellation reach terminal states.

The graph runs these Phase 3 nodes:

1. triage and scope classification;
2. a structured evidence plan;
3. evidence collection through the existing `ToolGateway`;
4. hypothesis creation with evidence identifiers;
5. deterministic validation, with one bounded retry of failed planned reads;
6. root-cause synthesis and `diagnosis_ready`.

The planner cannot expand its own authority. The server filters plans to registered
pure/read tools, constructs the allowed set from registry metadata, and sends every
call through the Phase 2 gateway for schema validation, policy, timeouts, sanitization,
evidence persistence, and audit. Retrieved logs and source code remain untrusted input;
they cannot grant permissions or select tools.

The model boundary is `ModelRouter` plus a typed `StructuredModelProvider` protocol.
Agents do not import a provider SDK. Every response is validated against the requested
Pydantic schema. Provider, model, token counts, latency, estimated cost, and success are
stored in `model_executions`. Phase 3 enables only an offline deterministic fixture
provider for the first N+1 vertical slice. This keeps acceptance reproducible while
preserving the provider boundary needed for future adapters.

The fixture provider proposes a hypothesis but does not determine its confidence.
Server-side validation checks independent latency, query-count, code, Git, deployment,
and database evidence. Confidence is computed from those checks. A diagnosis is stored
only when validation supports the hypothesis above the configured threshold and every
cited identifier belongs to evidence collected for the incident.

## Consequences

The manually injected checkout N+1 scenario produces a traceable diagnosis with six
typed evidence records, one supported hypothesis, model execution telemetry, and
clickable evidence citations. Other incident classes terminate inconclusively in this
phase. The deterministic provider is intentionally narrow and is not a claim of broad
diagnostic accuracy. Phase 4 RAG and Phase 5 remediation remain unimplemented.
