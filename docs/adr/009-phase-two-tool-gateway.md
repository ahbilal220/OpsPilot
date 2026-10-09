# ADR 009: Phase 2 policy-controlled read-only tool gateway

- Status: accepted
- Date: 2026-10-03

## Context

Phase 2 must give later investigations a single safe route to logs, metrics, repository
context, deployment history, and database diagnostics. Each call must have typed
contracts, a durable audit record, policy enforcement, bounded execution, and evidence
that can be traced back to its source. Phase 2 must stop before an agent plans or invokes
these tools autonomously.

## Decision

All diagnostic access passes through `ToolGateway`. Adapters register immutable
definitions containing their risk level, read-only flag, JSON input/output schemas,
timeout, and retry policy. The gateway validates input with Pydantic, evaluates policy,
records the execution, applies a timeout and bounded retry policy, sanitizes and limits
output, creates hash-addressed evidence records, emits timeline events, and returns a
typed result. Adapter exceptions are represented as safe failed results; raw exception
messages and credentials are not returned to callers.

The Phase 2 policy permits only registered Level 0/1 read-only tools explicitly present
in the server-derived incident context. Unknown, mutating, and out-of-workflow calls are
denied and audited. Invocation also requires an engineer or admin role, a trusted browser
origin, an incident in `investigating`, and an investigation in `started`. Client input
cannot expand the allowed tool set or change a tool's risk classification.

Six adapters cover the five roadmap sources:

- logs and deployment history read fixed demo JSON fixtures;
- metrics query a fixed configured Prometheus origin with URL-encoded PromQL;
- repository search traverses a fixed demo tree with path and secret-directory guards;
- Git history runs a fixed argument-vector command without a shell;
- database diagnostics choose from a fixed enum of read-only SQL statements and never
  accept SQL from a caller.

Repository and fixture roots are configured by the server and copied into the API image.
No adapter receives host Docker access, arbitrary filesystem paths, a command string,
write credentials, or a production endpoint. Evidence content is sanitized, bounded,
hashed with SHA-256, and linked to its incident, investigation, tool, query, and source.
The original tool invocation and final status remain in `tool_executions`; the incident
timeline remains the ordered operational audit projection.

The interface exposes a manual **Collect demo evidence** action after an investigation
starts. It calls the gateway for each demo source and renders evidence cards with type,
source, time, summary, raw sanitized content, and content hash. This is a user action,
not an investigation agent.

## Consequences

Later phases can call one stable gateway and cite durable evidence without broadening
adapter privileges. Tool failures do not crash the investigation API or leak raw errors.
The demo repository and fixtures are deterministic rather than production integrations.
Prometheus and PostgreSQL are live local services, but they remain fixed, read-only
targets. Agent orchestration, hypotheses, diagnosis, remediation, approval, and external
writes remain outside Phase 2.
