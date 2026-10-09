# Codex Implementation Instructions

## 1. Role

You are implementing **OpsPilot**, an evaluation-first autonomous AI incident-response platform.

Do not treat this as a chatbot project.

Before making architectural changes, read:

1. `README.md`
2. `PRD.md`
3. `SRS.md`
4. `ARCHITECTURE.md`
5. `SECURITY_GUARDRAILS.md`

## 2. Implementation Rules

### Rule 1 — Work Incrementally

Implement one roadmap phase at a time.

Do not generate the entire application in one pass.

### Rule 2 — Tests Come With Features

Every domain feature requires tests in the same change.

### Rule 3 — No Arbitrary Shell Tool

Do not implement unrestricted host shell execution.

Any command execution must happen inside the sandbox abstraction.

### Rule 4 — Separate Domain From Providers

Business logic must not directly import OpenAI/Anthropic/Gemini SDKs.

Use provider adapters.

### Rule 5 — Typed Contracts

Use:
- Pydantic request/response models,
- typed domain models,
- typed tool input/output,
- structured LLM outputs.

### Rule 6 — Never Trust LLM Output

Validate every output used by application logic.

### Rule 7 — Evidence Required

A diagnosis cannot be marked final unless it has supporting evidence records.

### Rule 8 — Approval Gate

No Level 3+ tool may run without a valid approval.

### Rule 9 — Keep MVP Modular

Prefer a modular monolith.

Do not split modules into network services without a documented reason.

### Rule 10 — Migrations Only

Do not mutate database schema manually.

Use Alembic.

## 3. Initial Repository Structure

Create:

```text
opspilot/
├── README.md
├── docs/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── incidents/
│   │   ├── investigations/
│   │   ├── agents/
│   │   ├── tools/
│   │   ├── rag/
│   │   ├── approvals/
│   │   ├── evaluations/
│   │   ├── telemetry/
│   │   ├── providers/
│   │   ├── db/
│   │   └── core/
│   ├── tests/
│   ├── alembic/
│   └── pyproject.toml
├── frontend/
├── demo-app/
├── benchmarks/
├── infra/
├── scripts/
├── docker-compose.yml
└── .github/workflows/
```

## 4. Backend Conventions

Recommended:
- FastAPI
- SQLAlchemy 2.x async
- Alembic
- Pydantic v2
- PostgreSQL
- Redis
- Celery
- pytest
- Ruff
- mypy or Pyright

Use repository/service boundaries only where they provide value.

Avoid enterprise-style boilerplate.

## 5. API Conventions

All API endpoints:
- `/api/v1/...`
- typed schemas
- consistent error envelope
- request ID support
- authorization dependency

Long-running actions should return `202 Accepted`.

## 6. Tool Contract

Implement a central registry.

Example:

```python
class ToolRisk(str, Enum):
    PURE = "pure"
    READ = "read"
    SANDBOX_WRITE = "sandbox_write"
    EXTERNAL_WRITE = "external_write"
    PRODUCTION_CRITICAL = "production_critical"

class ToolDefinition(BaseModel):
    name: str
    description: str
    risk: ToolRisk
    timeout_seconds: int

class ToolResult(BaseModel):
    success: bool
    summary: str
    data: dict
    evidence_ids: list[UUID]
```

Every tool execution must pass through a gateway that:
1. validates input,
2. checks policy,
3. checks approval,
4. executes,
5. sanitizes output,
6. records audit,
7. emits telemetry.

## 7. LLM Contract

Use a model router.

No agent should know provider-specific SDK code.

Implement:

```python
class ModelTask(str, Enum):
    CLASSIFICATION = "classification"
    EXTRACTION = "extraction"
    PLANNING = "planning"
    REASONING = "reasoning"
    PATCH_GENERATION = "patch_generation"

class ModelRouter:
    async def generate_structured(...):
        ...
```

Track:
- provider,
- model,
- tokens,
- latency,
- estimated cost.

## 8. Orchestrator

Use LangGraph or equivalent explicit state machine.

Never implement:
```python
while True:
    ask_llm_what_to_do()
```

The graph must have:
- hard maximum iterations,
- tool budget,
- cost budget,
- terminal inconclusive state.

## 9. First Vertical Slice

Before broadening scope, implement this complete flow:

### Scenario
N+1 database query in demo app.

### Required experience

1. User creates incident.
2. Investigation starts.
3. Metrics tool finds latency increase.
4. DB diagnostics show high query count.
5. Git tool finds recent relevant change.
6. Code search finds offending loop.
7. Hypothesis created.
8. Validation confirms query explosion.
9. Root cause report generated.
10. Patch proposed.
11. Sandbox tests patch.
12. Approval is requested.
13. UI displays complete evidence trail.

Do not implement the second incident until this works end-to-end.

## 10. Definition of Done

A feature is complete only when:

- implementation exists,
- unit tests exist,
- integration test exists where relevant,
- errors are handled,
- telemetry is emitted,
- audit is emitted where relevant,
- documentation is updated.

## 11. Commit Strategy

Prefer small commits such as:

```text
feat(incidents): add incident persistence
feat(tools): add tool registry and policy layer
feat(metrics): add prometheus read-only adapter
feat(investigation): add triage node
test(investigation): cover invalid model output
```

## 12. Do Not Invent Metrics

README benchmark numbers must come from actual evaluation results.

Do not write fake claims such as:
- "95% accuracy"
- "60% cost reduction"

until generated by the benchmark.

## 13. Questions / Ambiguity

When requirements are unclear:
- choose the simpler implementation,
- preserve safety,
- document the decision in an ADR,
- avoid speculative complexity.

## 14. First Task for Codex

Start with **Phase 0 only**.

Deliver:

1. repository structure,
2. `backend` FastAPI project,
3. PostgreSQL + Redis Docker Compose,
4. SQLAlchemy async setup,
5. Alembic,
6. base User model,
7. auth skeleton,
8. health/readiness endpoints,
9. structured logging,
10. pytest + Ruff,
11. frontend skeleton,
12. CI workflow.

Then stop and summarize:
- files created,
- commands to run,
- tests,
- architectural decisions,
- remaining Phase 0 items.

Do not begin agent implementation until Phase 0 is reviewed.
