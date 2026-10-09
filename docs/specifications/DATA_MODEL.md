# Data Model

## 1. Primary Entities

### users

```text
id UUID PK
email VARCHAR UNIQUE
password_hash VARCHAR
name VARCHAR
role ENUM(viewer, engineer, approver, admin)
created_at TIMESTAMPTZ
```

### incidents

```text
id UUID PK
title VARCHAR
description TEXT
severity ENUM(low, medium, high, critical)
status ENUM(...)
source ENUM(manual, alert, benchmark)
service_id UUID NULL
created_by UUID
started_at TIMESTAMPTZ NULL
resolved_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### services

```text
id UUID PK
name VARCHAR UNIQUE
repository_url TEXT NULL
default_branch VARCHAR
environment VARCHAR
metadata JSONB
```

### investigations

```text
id UUID PK
incident_id UUID FK
status VARCHAR
current_node VARCHAR
iteration_count INT
tool_calls_count INT
llm_cost_usd NUMERIC
started_at TIMESTAMPTZ
completed_at TIMESTAMPTZ NULL
state_snapshot JSONB
```

### evidence

```text
id UUID PK
incident_id UUID FK
investigation_id UUID FK
type ENUM(log, metric, code, git, deployment, document, database, test, trace)
source VARCHAR
source_reference TEXT NULL
tool_name VARCHAR
query JSONB
content TEXT
summary TEXT
content_hash VARCHAR NULL
observed_at TIMESTAMPTZ NULL
created_at TIMESTAMPTZ
```

### hypotheses

```text
id UUID PK
investigation_id UUID FK
title VARCHAR
description TEXT
confidence NUMERIC
status ENUM(proposed, testing, supported, rejected, inconclusive)
supporting_evidence_ids UUID[]
contradicting_evidence_ids UUID[]
validation_plan JSONB
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

### remediation_proposals

```text
id UUID PK
incident_id UUID FK
hypothesis_id UUID FK
type ENUM(code_patch, config_change, rollback, restart, scaling, manual)
summary TEXT
patch TEXT NULL
risk_level ENUM(low, medium, high, critical)
risks JSONB
rollback_plan TEXT
status ENUM(draft, validating, validation_failed, awaiting_approval, approved, rejected, executed)
created_at TIMESTAMPTZ
```

### validation_runs

```text
id UUID PK
remediation_id UUID FK
sandbox_id VARCHAR
status ENUM(running, passed, failed, error)
tests_total INT
tests_passed INT
benchmark_before JSONB
benchmark_after JSONB
output TEXT
created_at TIMESTAMPTZ
completed_at TIMESTAMPTZ NULL
```

### approvals

```text
id UUID PK
remediation_id UUID FK
requested_by VARCHAR
approved_by UUID NULL
status ENUM(pending, approved, rejected, expired)
reason TEXT NULL
expires_at TIMESTAMPTZ
created_at TIMESTAMPTZ
resolved_at TIMESTAMPTZ NULL
```

### tool_executions

```text
id UUID PK
investigation_id UUID FK
tool_name VARCHAR
risk_level VARCHAR
input JSONB
output JSONB NULL
status VARCHAR
duration_ms INT
error TEXT NULL
created_at TIMESTAMPTZ
```

### model_executions

```text
id UUID PK
investigation_id UUID FK
task_type VARCHAR
provider VARCHAR
model VARCHAR
prompt_tokens INT
completion_tokens INT
latency_ms INT
estimated_cost_usd NUMERIC
success BOOLEAN
created_at TIMESTAMPTZ
```

### audit_events

```text
id UUID PK
incident_id UUID NULL
actor_type ENUM(user, agent, system)
actor_id VARCHAR
event_type VARCHAR
payload JSONB
created_at TIMESTAMPTZ
```

### documents

```text
id UUID PK
title VARCHAR
source VARCHAR
metadata JSONB
created_at TIMESTAMPTZ
```

### document_chunks

```text
id UUID PK
document_id UUID FK
chunk_index INT
content TEXT
embedding VECTOR(...)
metadata JSONB
```

## 2. Indexes

Required:
- incidents(status, created_at)
- evidence(incident_id, type)
- tool_executions(investigation_id, created_at)
- model_executions(investigation_id, created_at)
- audit_events(incident_id, created_at)
- vector index on document_chunks.embedding

## 3. Data Retention

For demo:
- keep all incidents,
- redact secrets before storing tool outputs,
- support deleting benchmark runs.

Production-like design should separate sensitive raw telemetry from summarized evidence.
