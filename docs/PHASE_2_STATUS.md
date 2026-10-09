# Phase 2 validation

Phase 2 implements the policy-controlled tool and evidence boundary used by later
investigation phases.

## Delivered

- A central registry and gateway with typed input/output schemas, risk metadata,
  timeouts, bounded retries, output limits, redaction, and safe failure results.
- Read-only adapters for demo logs, Prometheus instant queries, repository text search,
  Git history, demo deployments, and allowlisted database diagnostics.
- Durable tool execution records for allowed, failed, invalid, unknown, and denied
  calls, plus append-only incident timeline events.
- Durable evidence linked to incident, investigation, source, tool, query, timestamps,
  sanitized content, and SHA-256 content hash.
- Evidence and tool-execution APIs, OpenAPI contracts, live SSE updates, and evidence
  cards with raw sanitized views in the incident workspace.
- Alembic revision `0004_tool_gateway` and readiness enforcement at that schema head.
- A local Prometheus service and deterministic demo fixture/repository sources built
  into the API image.
- Unit, authorization, policy-denial, traversal, redaction, timeout, migration,
  PostgreSQL/Redis/Prometheus integration, frontend, and stack smoke coverage.

## Safety boundary

Only engineers and admins can invoke tools, browser calls require a trusted origin, and
the incident must have a started investigation. Phase 2 policy allows registered
read-only tools only. It rejects mutation risk, unknown names, client-selected paths
outside the demo repository, arbitrary SQL, arbitrary commands, and arbitrary network
origins. Inputs, outputs, failures, and denials are audited. Tool output is untrusted
evidence and cannot change policy or trigger another tool.

No LLM or agent selects tools, forms a hypothesis, marks a diagnosis final, proposes a
remediation, requests approval, or performs an external write. Those remain later-phase
work.

## Operator acceptance

Run the Compose checks and smoke flow in the repository README. Create an incident as an
engineer, start its investigation, wait for the `investigation.started` event, and select
**Collect demo evidence**. The Phase 2 exit criteria are met when all six calls appear in
the execution audit, evidence appears for all five roadmap source categories, and an
unknown or mutating tool call is denied and recorded as `tool.policy_denied`.
