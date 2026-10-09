# Phase 1 validation

Phase 1 implements incident intake and the first durable background-work transition.

## Delivered

- Service registry create, list, and update endpoints.
- Incident create, list/filter, detail, update-before-start, and cancel endpoints.
- Role-gated mutations with trusted-origin enforcement.
- One idempotent investigation record per incident and Celery/Redis queue submission.
- A bounded worker transition from queued to started; no diagnosis, tools, agents, or
  remediation behavior.
- Append-only PostgreSQL audit events and reconnectable server-sent event delivery.
- A responsive Phase 1 workspace for service registration, incident intake, queue start,
  cancellation, and live timeline viewing.
- Alembic revisions `0002_incident_management` and `0003_phase_one_constraints`, with
  readiness enforcement at the Phase 1 head revision.
- Unit, authorization, failure-path, SSE, migration, real-service integration, and stack
  smoke coverage.

## Safety boundary

New users are viewers. Only engineers and admins can change service or incident state,
and browser mutations require a configured trusted origin. The worker records that an
investigation began and stops there. Phase 2 agent behavior has not been started.

## Operator acceptance

Run the checks and acceptance flow documented in the repository README. The Phase 1 exit
criterion is met when an engineer creates an incident, receives HTTP 202 from the start
endpoint, and observes both `investigation.queued` and `investigation.started` in the
incident timeline.
