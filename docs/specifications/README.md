# OpsPilot — Autonomous AI Incident Response Engineer

OpsPilot is a production-oriented Agentic AI platform that investigates software incidents by correlating logs, metrics, source code, deployment history, runbooks, database diagnostics, and test results. It produces an evidence-backed root-cause analysis and proposes a remediation plan that must pass validation and human approval before any mutating action is allowed.

This repository documentation is intentionally designed for implementation with Codex or another coding agent.

## Product Goal

Build a portfolio-grade AI engineering system that demonstrates:

- Agent orchestration and stateful workflows
- Reliable tool use
- Retrieval-Augmented Generation (RAG)
- MCP-compatible tool design
- FastAPI backend engineering
- PostgreSQL + pgvector
- Redis-backed state/caching
- Observability with OpenTelemetry, Prometheus, Grafana, and Langfuse
- Human-in-the-loop safety
- Reproducible AI evaluation
- Model routing and cost optimization
- Dockerized microservices
- CI/CD and cloud deployment
- Next.js monitoring/investigation UI

## Recommended Reading Order

1. `PRD.md`
2. `SRS.md`
3. `ARCHITECTURE.md`
4. `AGENT_DESIGN.md`
5. `DATA_MODEL.md`
6. `API_SPEC.md`
7. `RAG_DESIGN.md`
8. `SECURITY_GUARDRAILS.md`
9. `EVALUATION_FRAMEWORK.md`
10. `OBSERVABILITY.md`
11. `TESTING_STRATEGY.md`
12. `DEVOPS_DEPLOYMENT.md`
13. `ROADMAP.md`
14. `CODEX_INSTRUCTIONS.md`

## Core Principle

OpsPilot must not be a chatbot with tools.

It must behave like a constrained incident-response workflow:

**Observe → Triage → Gather Evidence → Form Hypotheses → Validate → Propose Fix → Test in Sandbox → Request Approval → Execute Approved Action → Verify**

Every important conclusion should be traceable to evidence.

## MVP Scope

The first usable MVP should support one deliberately instrumented demo application and these incident categories:

1. N+1 database query
2. Slow downstream API
3. Database connection exhaustion
4. Redis/cache outage
5. Invalid environment/configuration value
6. Bad deployment regression

The MVP is successful when OpsPilot can investigate these incidents, produce evidence-backed findings, and propose a validated remediation without uncontrolled production execution.
