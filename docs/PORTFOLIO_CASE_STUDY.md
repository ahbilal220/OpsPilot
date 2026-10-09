# OpsPilot portfolio case study

## Summary

OpsPilot is an evidence-driven agentic AI incident-response platform. It coordinates a
bounded investigation workflow across metrics, logs, database diagnostics, deployment
history, Git history, and repository search. The system validates a hypothesis before it
can produce a cited root-cause diagnosis.

## Problem

Production incident investigation is often fragmented across observability tools and
code repositories. A free-running AI agent creates an additional risk: it may invent a
cause, exceed its budget, or perform unsafe actions without review.

## Solution

OpsPilot uses an explicit persisted state graph rather than an unbounded agent loop. The
current Phase 3 vertical slice:

1. triages a checkout-latency incident;
2. plans a bounded evidence collection run;
3. invokes six read-only diagnostic sources through a policy-controlled tool gateway;
4. records evidence and model-execution telemetry;
5. creates and validates an N+1-query hypothesis; and
6. produces a diagnosis whose citations are verified server-side.

## Safety properties

- Hard limits for iterations, tool calls, elapsed time, and model cost.
- Typed and validated model output.
- Allowlisted read-only tools with sanitized, audited results.
- Deterministic evidence checks before a hypothesis is marked supported.
- Final diagnoses require evidence records belonging to the incident.
- No patch generation, sandbox execution, approval, or remediation in Phase 3.

## Stack

- Python, FastAPI, Pydantic, SQLAlchemy, Alembic
- PostgreSQL, Redis, Celery
- Next.js, React, TypeScript
- Docker Compose, Prometheus, GitHub Actions
- Pytest, Ruff, strict mypy

## Current status

Phases 0–3 are implemented. The repository includes the full application, migrations,
tests, Docker stack, acceptance scripts, architecture decisions, and preserved product
specifications. Phase 4 remediation work has not begun.

