# Phase 3 validation

Phase 3 implements the bounded, evidence-driven investigation workflow for the first
N+1 database-query scenario.

## Delivered

- An explicit persisted state graph for triage, planning, evidence collection,
  hypothesis creation, validation, and root-cause synthesis.
- Hard limits for graph iterations, read-only tool calls, model cost, and wall time,
  with terminal completed, inconclusive, failed, and cancelled states.
- A provider-neutral structured model contract and router with validated Pydantic
  output plus durable provider, model, token, latency, cost, and success records.
- A deterministic offline fixture provider for the checkout recommendation N+1
  vertical slice and safe inconclusive handling for incidents outside that scope.
- Six-source evidence collection through the Phase 2 tool gateway: Prometheus metrics,
  logs, database diagnostics, deployment history, Git history, and repository search.
- Durable hypotheses with validation plans, computed confidence, validation checks,
  and supporting evidence identifiers.
- A root-cause diagnosis that can be finalized only after server-side validation and
  only with citations to evidence belonging to the incident.
- Hypothesis, diagnosis, and model-execution APIs; timeline/SSE events; and UI panels
  for graph progress, hypotheses, validation, diagnosis, and evidence citations.
- Alembic revision `0005_orchestrated_investigation` and readiness enforcement at that
  schema head.
- Unit, failure, budget, scope, invalid-model-output, real-service integration,
  frontend production-build, migration, and live stack acceptance coverage.

## Safety boundary

The graph can invoke only registry-defined pure/read tools. The Phase 2 gateway still
validates, authorizes, sanitizes, bounds, audits, and persists every call. A model plan
cannot add a tool, alter risk metadata, supply SQL, execute a host command, or convert
retrieved content into an instruction. All model output is schema-validated. Confidence
comes from deterministic evidence checks, and a final diagnosis requires valid evidence
citations above the configured threshold.

Phase 3 does not ingest runbooks, build vector indexes, generate or apply patches, run a
sandbox, request approval, or perform an external write. Those are later roadmap phases.

## Operator acceptance

Start the stack and run the checks in the repository README. Then create a high-severity
incident titled **Checkout recommendation latency regression** whose description mentions
increased checkout latency and database queries after the latest recommendation
deployment. Start the investigation. The Phase 3 exit criterion is met when the worker
finishes at `diagnosis_ready`, the hypothesis is supported, all six evidence types are
shown, and the N+1 diagnosis links back to its evidence.

The automated acceptance flow is `python3 scripts/phase3_smoke.py`.
