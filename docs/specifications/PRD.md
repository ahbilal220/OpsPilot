# Product Requirements Document (PRD)

## 1. Product

**Name:** OpsPilot  
**Category:** Agentic AI / AI SRE / Developer Infrastructure  
**Primary User:** Backend engineer, SRE, platform engineer, engineering team lead  
**Secondary User:** AI engineer evaluating reliability of agent systems

## 2. Problem Statement

Incident response is fragmented across logs, metrics, source code, deployment history, runbooks, databases, and human memory. Engineers manually move between tools, correlate timestamps, form hypotheses, inspect code, run tests, and decide whether a proposed fix is safe.

Most AI assistants can summarize one source of information, but they do not reliably execute a structured investigation process or provide measurable evidence that their diagnosis is correct.

OpsPilot should reduce investigation time by acting as an evidence-driven incident-response assistant that can autonomously gather read-only diagnostic information, reason over it, validate hypotheses, and prepare safe remediation proposals.

## 3. Product Vision

A developer should be able to submit:

> "Checkout latency increased after today's deployment. Investigate."

OpsPilot should:

1. Create an incident.
2. Pull relevant metrics and logs.
3. Inspect recent deployments and commits.
4. Retrieve architecture documentation and runbooks.
5. Generate ranked hypotheses.
6. Validate those hypotheses using tools.
7. Identify likely root cause.
8. Generate a proposed code/configuration fix.
9. Validate the proposal in an isolated environment.
10. Present evidence, confidence, risks, and test results.
11. Wait for human approval before any production-changing action.
12. Verify recovery after execution.

## 4. Goals

### G1 — Demonstrate production-grade agent engineering

The system must include:
- deterministic workflow control,
- state persistence,
- retries,
- tool authorization,
- structured outputs,
- evidence provenance,
- failure handling,
- evaluation.

### G2 — Demonstrate backend/system-design strength

The platform should include:
- authenticated REST APIs,
- WebSocket/SSE updates,
- PostgreSQL persistence,
- background execution,
- caching,
- event logging,
- containerized services.

### G3 — Demonstrate trustworthy AI behavior

Every root-cause claim must reference collected evidence. Mutating tools must never execute without approval.

### G4 — Demonstrate measurable AI quality

OpsPilot must ship with a repeatable benchmark containing injected incidents and machine-readable scoring.

### G5 — Demonstrate cost awareness

The system should track token usage, model cost, tool latency, and investigation cost.

## 5. Non-Goals

For the initial release, OpsPilot will not:

- autonomously execute arbitrary shell commands in production,
- provide unrestricted infrastructure access,
- replace a real SRE team,
- support every cloud provider,
- optimize for multi-tenant enterprise scale,
- automatically merge pull requests,
- self-deploy unapproved fixes,
- build a general-purpose coding assistant.

## 6. User Personas

### Persona A — Backend Engineer

Needs fast diagnosis of errors, regressions, and latency spikes.

### Persona B — SRE / Platform Engineer

Needs structured incident evidence, service health context, runbook retrieval, and auditability.

### Persona C — Engineering Lead

Needs incident summaries, confidence levels, timelines, and proposed remediation.

### Persona D — Portfolio Reviewer / Recruiter

Needs a clear demonstration of modern AI engineering skills and measurable results.

## 7. Core User Stories

### Incident Investigation

As an engineer, I want to create an incident from a natural-language description so OpsPilot can begin investigation.

### Live Progress

As an engineer, I want to see agents and tools executing in real time so I can understand what the system is doing.

### Evidence

As an engineer, I want each conclusion linked to logs, metrics, code, commits, or documentation.

### Root Cause

As an engineer, I want OpsPilot to rank hypotheses and explain why one is most strongly supported.

### Remediation

As an engineer, I want a proposed fix with risks, affected files, rollback plan, and validation results.

### Human Approval

As an engineer, I want the platform to block dangerous actions until I explicitly approve them.

### Evaluation

As an AI engineer, I want benchmark results for diagnostic accuracy, groundedness, tool selection, latency, and cost.

## 8. Functional Requirements

### FR-1 Incident Creation
Users can create an incident from:
- manual text,
- monitoring alert payload,
- demo benchmark trigger.

### FR-2 Context Gathering
OpsPilot can gather:
- logs,
- metrics,
- source code,
- recent commits,
- deployment history,
- database diagnostics,
- runbooks,
- service dependency metadata.

### FR-3 Agent Orchestration
Investigation must be coordinated through a state machine, not uncontrolled agent-to-agent chat.

### FR-4 Hypothesis Management
OpsPilot must store explicit hypotheses containing:
- description,
- supporting evidence,
- contradicting evidence,
- confidence,
- validation plan,
- status.

### FR-5 Evidence Provenance
Each evidence item must contain:
- source/tool,
- timestamp,
- query/input,
- raw or summarized result,
- reference URI or identifier,
- hash where practical.

### FR-6 Remediation Proposal
A proposal must include:
- change description,
- patch/diff if code-related,
- risk analysis,
- rollback instructions,
- validation plan,
- test results.

### FR-7 Approval Workflow
Mutating actions require explicit approval.

### FR-8 Sandbox Validation
Code/config remediation must be tested in a sandbox or isolated container.

### FR-9 Real-Time Updates
Frontend receives progress using WebSockets or Server-Sent Events.

### FR-10 Audit Trail
Every agent decision, tool invocation, approval, and state transition is recorded.

### FR-11 Model Routing
The platform should be able to route tasks to different models based on complexity, privacy, latency, or cost.

### FR-12 Evaluation Harness
Injected incidents can be executed and automatically scored.

## 9. Success Metrics

Target metrics for the portfolio release:

| Metric | Target |
|---|---:|
| Root-cause top-1 accuracy | >= 80% |
| Root-cause top-3 accuracy | >= 90% |
| Evidence citation correctness | >= 95% |
| Unsafe mutating action without approval | 0 |
| Tool-call schema success rate | >= 98% |
| Incident workflow completion rate | >= 90% |
| Median diagnosis latency for demo incidents | <= 5 min |
| Benchmark reproducibility | 100% from documented seed/config |
| Cost tracking coverage | 100% of LLM calls |

These are project targets, not claims. Report actual results once measured.

## 10. Product Differentiators

1. Evaluation-first design.
2. Explicit evidence provenance.
3. Deterministic orchestration instead of free-form agent conversations.
4. Human approval before mutation.
5. Sandbox validation of remediation.
6. Model-cost routing.
7. Reproducible incident benchmark.
8. Transparent failure analysis.

## 11. MVP Features

The MVP must include:

- Authentication
- Incident CRUD
- Investigation state machine
- Metrics tool
- Logs tool
- Code search tool
- Git history tool
- Runbook RAG
- Hypothesis engine
- Root-cause report
- Sandbox test tool
- Approval workflow
- Dashboard
- Audit log
- Evaluation harness
- Docker Compose environment

## 12. Post-MVP Features

- GitHub PR creation
- OpenTelemetry trace analysis
- Slack integration
- Jira issue creation
- Kubernetes diagnostics
- AWS CloudWatch integration
- multi-repository incidents
- learned model router
- incident memory
- automated regression prevention suggestions
