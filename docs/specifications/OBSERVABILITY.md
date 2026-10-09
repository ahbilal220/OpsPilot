# Observability

## 1. Goals

OpsPilot must make both the investigated system and the AI workflow observable.

## 2. OpenTelemetry

Instrument:

- FastAPI requests,
- Celery tasks,
- investigation nodes,
- tool executions,
- model calls,
- retrieval operations,
- database queries.

## 3. Trace Structure

One incident should have a high-level trace:

```text
incident investigation
├── triage
├── collect metrics
├── collect logs
├── inspect git
├── retrieve runbooks
├── build hypotheses
├── validate hypothesis
├── synthesize root cause
└── generate remediation
```

## 4. Prometheus Metrics

Suggested metrics:

```text
opspilot_incidents_total
opspilot_investigations_active
opspilot_investigation_duration_seconds
opspilot_tool_calls_total
opspilot_tool_failures_total
opspilot_llm_calls_total
opspilot_llm_tokens_total
opspilot_llm_cost_usd_total
opspilot_rag_retrieval_duration_seconds
opspilot_approval_requests_total
opspilot_policy_denials_total
```

## 5. Langfuse

Track:
- prompts,
- model versions,
- latency,
- token counts,
- traces,
- scores,
- evaluation labels.

## 6. Grafana Dashboards

Dashboard 1: OpsPilot platform health

Dashboard 2: AI cost and quality

Dashboard 3: Demo application health

Dashboard 4: Benchmark results

## 7. Logging

Use structured JSON logging.

Required fields:
- timestamp
- request_id
- incident_id
- investigation_id
- trace_id
- component
- event
- level

Never log raw credentials.
