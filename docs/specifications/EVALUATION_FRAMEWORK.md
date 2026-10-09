# Evaluation Framework

## 1. Purpose

OpsPilot's evaluation system is a first-class product feature.

The benchmark should answer:

- Did the agent find the correct root cause?
- Did it collect relevant evidence?
- Did it use the correct tools?
- Did it hallucinate evidence?
- Did it propose a valid remediation?
- Was the remediation safe?
- How much did it cost?
- How long did it take?

## 2. Benchmark Structure

```text
benchmarks/
├── suites/
│   └── mvp_v1.yaml
├── scenarios/
│   ├── n_plus_one/
│   ├── redis_outage/
│   ├── bad_env/
│   ├── db_pool_exhaustion/
│   ├── slow_dependency/
│   └── bad_deployment/
├── runner/
└── reports/
```

## 3. Scenario Definition

Example:

```yaml
id: n_plus_one_001
title: N+1 query regression
service: trip-api
injector: scripts/inject_n_plus_one.py

ground_truth:
  category: database
  root_cause_file: app/repositories/trips.py
  root_cause_symbol: get_trip_recommendations
  causal_commit: abc123

expected_evidence:
  - db_query_count_spike
  - latency_increase
  - recent_commit

allowed_remediations:
  - eager_loading
  - batch_query
```

## 4. Metrics

### Root Cause Accuracy
- top-1
- top-3
- category accuracy
- file/symbol localization accuracy

### Evidence Quality
- evidence precision
- evidence recall
- citation correctness
- unsupported claim count

### Tool Use
- tool selection precision
- unnecessary tool-call count
- failed tool-call rate

### Safety
- unapproved mutation count
- policy violation count
- prompt injection success rate

### Remediation
- patch compiles
- tests pass
- incident symptom improves
- regression count

### Efficiency
- wall-clock time
- number of model calls
- tokens
- cost
- tool latency

## 5. Groundedness Scoring

A statement is grounded when its referenced evidence supports the claim.

Use deterministic checks where possible.

LLM-as-judge may supplement, not replace, rule-based scoring.

## 6. Model Routing Experiment

Compare:

### Baseline
One frontier model for all tasks.

### Routed
- small model for classification/extraction,
- stronger model for hypothesis/root-cause synthesis,
- local model for sensitive source summaries where available.

Report:
- total cost,
- latency,
- accuracy,
- safety metrics.

## 7. Reproducibility

Every evaluation run stores:

- Git SHA
- model provider/model
- prompt version
- temperature/settings
- benchmark version
- incident seed
- tool versions
- environment metadata

## 8. Failure Analysis

The public project report should include:

- false diagnoses,
- missed evidence,
- bad tool plans,
- overconfident outputs,
- invalid remediations,
- model-provider differences.

Do not hide failures.
