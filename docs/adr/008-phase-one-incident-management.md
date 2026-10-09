# ADR 008: Phase 1 incident management and queued investigation start

- Status: accepted
- Date: 2026-09-23

## Context

Phase 1 must provide the operational record that later investigation phases will use: a
service registry, incident lifecycle, append-only timeline, live event delivery, and a
durable handoff to a background worker. It must stop before any diagnostic reasoning,
tool execution, or remediation behavior.

## Decision

PostgreSQL is authoritative for services, incidents, investigations, and audit events.
The API creates one investigation per incident in a transaction, records an
`investigation.queued` event, and then submits its identifier to Celery through Redis.
Submission is idempotent at the database boundary. A broker failure is represented as a
blocked investigation and an append-only `investigation.queue_failed` event.

The Phase 1 worker performs one bounded transition: it locks the investigation, marks it
started, moves the incident to `investigating`, and records `investigation.started`. It
does not call an LLM, connect to an operational system, infer a diagnosis, or propose a
remediation.

Authenticated users may read the registry and incident records. Mutations require an
exact trusted browser origin and an `engineer` or `admin` role. New registrations remain
`viewer`; a local operator may change an existing account with the explicit CLI command.

The timeline is the ordered audit-event projection for an incident. Server-sent events
poll this durable source and support `Last-Event-ID`, so reconnecting clients can resume.
SSE is a delivery mechanism rather than a second source of truth.

Incidents and referenced services are retained rather than hard-deleted. Incident
cancellation is the terminal user-controlled lifecycle operation and is itself audited.

## Consequences

The API can acknowledge investigation work with HTTP 202 while preserving a traceable
state transition even when the broker is unavailable. Worker delivery remains at least
once, so its transition is idempotent. Later phases can extend the investigation state
machine without changing the Phase 1 ownership boundary.

