# Implementation Roadmap

## Phase 0 — Foundation

Deliverables:
- repository scaffold,
- Docker Compose,
- FastAPI,
- PostgreSQL,
- Redis,
- Next.js,
- authentication,
- CI,
- shared config/logging.

Exit criteria:
- `docker compose up` runs stack,
- health endpoints pass,
- user can log in.

## Phase 1 — Incident Management

Deliverables:
- incident CRUD,
- service registry,
- incident timeline,
- SSE event stream,
- worker queue.

Exit criteria:
- incident can be created and investigation job started.

## Phase 2 — Tool Gateway

Implement read-only tools:

1. mock/demo logs
2. Prometheus metrics
3. Git repository search/history
4. deployment history
5. database diagnostics

Exit criteria:
- tools use typed schemas,
- every call is audited,
- policy engine blocks unauthorized tool calls.

## Phase 3 — Orchestrated Investigation

Deliverables:
- LangGraph state,
- triage,
- planner,
- evidence collection,
- hypothesis creation,
- validation loop,
- root-cause report.

Exit criteria:
- manually injected N+1 incident can be diagnosed.

## Phase 4 — RAG

Deliverables:
- document ingestion,
- pgvector embeddings,
- lexical retrieval,
- hybrid retrieval,
- evidence citations.

Exit criteria:
- runbook evidence can contribute to diagnosis.

## Phase 5 — Remediation and Sandbox

Deliverables:
- patch proposal,
- isolated repository copy,
- test execution,
- before/after benchmark,
- approval state.

Exit criteria:
- N+1 fix can be proposed and validated without touching host/production.

## Phase 6 — Evaluation Harness

Deliverables:
- six incident scenarios,
- ground-truth manifests,
- scoring engine,
- evaluation reports,
- dashboard.

Exit criteria:
- full benchmark runs from one command.

## Phase 7 — Model Routing

Deliverables:
- provider abstraction,
- routing rules,
- fallback,
- cost tracking,
- baseline-vs-routed report.

Exit criteria:
- measurable cost/latency comparison.

## Phase 8 — Portfolio Polish

Deliverables:
- architecture diagrams,
- polished README,
- demo seed,
- 60–90 second demo script,
- screenshots,
- benchmark report,
- technical blog/report.

## Recommended Order of Incident Scenarios

1. N+1 query
2. Bad environment variable
3. Redis outage
4. Slow external dependency
5. DB pool exhaustion
6. Deployment regression

## Avoid Scope Creep

Do not add:
- Kubernetes,
- Slack,
- Jira,
- auto-merge,
- multi-cloud deployment

until the benchmark and core workflow are working.
