# Software Requirements Specification (SRS)

## 1. Purpose

This SRS defines software behavior, constraints, interfaces, data requirements, safety requirements, and acceptance conditions for OpsPilot.

## 2. System Context

OpsPilot consists of:

1. Web dashboard
2. Backend API
3. Investigation orchestration engine
4. Tool gateway
5. RAG subsystem
6. Database
7. Queue/state infrastructure
8. Observability stack
9. Demo application under investigation
10. Evaluation harness
11. Sandboxed validation environment

## 3. Functional Requirements

### SRS-F-001 Authentication
The system shall authenticate users before allowing incident access.

### SRS-F-002 Authorization
The system shall support at least:
- `viewer`
- `engineer`
- `approver`
- `admin`

### SRS-F-003 Incident Lifecycle
Allowed states:

`created -> queued -> investigating -> diagnosis_ready -> remediation_ready -> awaiting_approval -> executing -> verifying -> resolved`

Failure states:

`blocked`, `failed`, `cancelled`

### SRS-F-004 Investigation Trigger
An investigation can start from:
- API request,
- UI action,
- benchmark runner.

### SRS-F-005 Tool Registry
All agent tools shall be registered with:
- name,
- description,
- input schema,
- output schema,
- risk level,
- read/write capability,
- timeout,
- retry policy.

### SRS-F-006 Tool Authorization
The orchestration layer shall reject tool calls not allowed in the current workflow state.

### SRS-F-007 Structured Agent Outputs
Agent outputs used by software logic shall be JSON-schema/Pydantic validated.

### SRS-F-008 Evidence
All investigation evidence shall be persisted.

### SRS-F-009 Hypothesis Tracking
The system shall support multiple competing hypotheses.

### SRS-F-010 Root Cause Report
The system shall produce a structured report containing:
- incident summary,
- impact,
- timeline,
- observed symptoms,
- likely root cause,
- supporting evidence,
- contradictory evidence,
- confidence,
- recommended remediation,
- unresolved uncertainty.

### SRS-F-011 Sandbox
Potential remediations shall execute only in an isolated validation environment.

### SRS-F-012 Approval
Any action classified as mutating or high-risk shall require approval.

### SRS-F-013 Audit
The system shall maintain append-only audit records for:
- tool calls,
- agent transitions,
- approvals,
- model calls,
- manual interventions.

### SRS-F-014 Evaluation
The benchmark runner shall produce machine-readable results.

## 4. Non-Functional Requirements

### NFR-001 Reliability
A failed tool call should not crash the entire investigation.

### NFR-002 Idempotency
Repeated event delivery should not create duplicate actions.

### NFR-003 Security
Secrets shall not be sent to the LLM unless explicitly required and approved by a secret-handling policy.

### NFR-004 Performance
API endpoints unrelated to long-running investigations should target p95 < 500 ms in local/demo conditions.

### NFR-005 Scalability
Long-running tasks must execute outside API request workers.

### NFR-006 Explainability
Final conclusions shall be traceable to evidence.

### NFR-007 Observability
All agent runs, tools, API requests, model calls, and queues shall emit traceable telemetry.

### NFR-008 Reproducibility
The benchmark must support deterministic incident injection where possible.

### NFR-009 Maintainability
Tool integrations shall use interfaces/adapters so they can be replaced without changing core orchestration.

### NFR-010 Testability
External tools and LLM providers must be mockable.

## 5. Constraints

- Primary backend language: Python 3.12+
- API framework: FastAPI
- Primary database: PostgreSQL
- Vector capability: pgvector
- Orchestration: LangGraph or a custom explicit state graph
- Cache/state: Redis
- Frontend: Next.js + TypeScript
- Container runtime: Docker
- Production observability: OpenTelemetry compatible
- CI: GitHub Actions

## 6. External Interfaces

### LLM Providers
Providers must be behind an abstraction layer.

Required interface:

```python
class ModelProvider(Protocol):
    async def generate_structured(
        self,
        messages: list[Message],
        schema: type[BaseModel],
        metadata: dict
    ) -> BaseModel:
        ...
```

### Tool Providers
Required high-level interface:

```python
class Tool(Protocol):
    name: str
    risk_level: str

    async def execute(self, context, input):
        ...
```

## 7. Safety Requirements

### SAFE-001
No arbitrary production shell tool in MVP.

### SAFE-002
Read-only tools may execute autonomously.

### SAFE-003
Mutating tools require approval tokens.

### SAFE-004
Approval tokens must be scoped to:
- incident,
- action,
- user,
- expiration.

### SAFE-005
Agents cannot alter their own permission policy.

### SAFE-006
Tool outputs must be treated as untrusted input to reduce prompt-injection risk.

### SAFE-007
Retrieved repository/document content must never override system instructions.

## 8. Availability / Failure Behavior

If an LLM provider fails:
1. retry according to policy,
2. optionally route to fallback provider,
3. persist failure,
4. mark investigation blocked if no safe fallback exists.

If an external tool fails:
1. record failure,
2. evaluate whether alternative evidence exists,
3. continue where safe.

## 9. Acceptance Summary

The first public release must demonstrate at least six known incident types end-to-end and export an evaluation report with actual measured performance.
