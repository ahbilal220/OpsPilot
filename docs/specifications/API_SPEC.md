# API Specification

Base path:

```text
/api/v1
```

## Authentication

### POST `/auth/register`
### POST `/auth/login`
### POST `/auth/logout`
### GET `/auth/me`

## Incidents

### POST `/incidents`

Request:

```json
{
  "title": "Checkout latency regression",
  "description": "p95 latency increased after latest deployment",
  "severity": "high",
  "service_id": "uuid"
}
```

Response:

```json
{
  "id": "uuid",
  "status": "created"
}
```

### GET `/incidents`

Filters:
- status
- severity
- service
- created_from
- created_to

### GET `/incidents/{incident_id}`

Returns:
- incident,
- investigation,
- timeline,
- diagnosis,
- remediation.

### POST `/incidents/{incident_id}/investigate`

Starts investigation.

Must be idempotent.

### POST `/incidents/{incident_id}/cancel`

## Evidence

### GET `/incidents/{incident_id}/evidence`

Filters:
- type
- tool
- hypothesis

### GET `/evidence/{evidence_id}`

## Hypotheses

### GET `/incidents/{incident_id}/hypotheses`

### POST `/incidents/{incident_id}/hypotheses/{hypothesis_id}/validate`

For manual developer triggering/debugging only.

## Remediation

### GET `/incidents/{incident_id}/remediation`

### POST `/remediations/{id}/validate`

Runs sandbox validation.

### POST `/remediations/{id}/approve`

Request:

```json
{
  "reason": "Reviewed patch and validation results"
}
```

Required role:
`approver` or `admin`

### POST `/remediations/{id}/reject`

## Streaming

### GET `/incidents/{incident_id}/events`

SSE preferred for MVP.

Events:

```json
{
  "type": "tool.completed",
  "timestamp": "...",
  "payload": {}
}
```

## Evaluations

### POST `/evaluations/runs`

Request:

```json
{
  "suite": "mvp-v1",
  "scenarios": ["n_plus_one", "redis_outage"]
}
```

### GET `/evaluations/runs/{id}`

### GET `/evaluations/runs/{id}/results`

## System

### GET `/health`
### GET `/ready`
### GET `/metrics`

## API Rules

1. Every mutation must support request IDs.
2. Long-running endpoints return accepted/task state rather than blocking.
3. Pydantic models are mandatory.
4. Errors follow a shared envelope.

Example:

```json
{
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "This action requires human approval.",
    "details": {}
  }
}
```
