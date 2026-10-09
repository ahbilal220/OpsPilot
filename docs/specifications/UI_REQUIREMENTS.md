# UI Requirements

## 1. Pages

### Login
Simple authentication.

### Incident List
Columns:
- title,
- severity,
- service,
- status,
- created,
- duration.

### Incident Detail

Sections:

1. Summary
2. Live investigation status
3. Timeline
4. Evidence
5. Hypotheses
6. Diagnosis
7. Remediation
8. Validation
9. Approval
10. Cost and model usage

### Evaluation Dashboard

Display:
- root-cause accuracy,
- evidence groundedness,
- tool success,
- average latency,
- average cost,
- scenario-level failures.

## 2. Incident Timeline Example

```text
17:31 Incident created
17:31 Investigation started
17:31 Metrics queried
17:32 Logs analyzed
17:32 Deployment correlated
17:33 Hypothesis: N+1 query
17:33 Hypothesis validated
17:34 Remediation generated
17:35 Sandbox tests passed
17:35 Awaiting approval
```

## 3. Evidence UX

Every evidence card should show:
- type,
- source,
- timestamp,
- short summary,
- "view raw" action,
- which hypotheses use it.

## 4. Explainability

When diagnosis says:

> N+1 query caused the regression.

The user should be able to click the statement and see the evidence.

## 5. Safety UX

Approval page must clearly display:
- exact action,
- diff,
- risk level,
- validation result,
- rollback plan.

Avoid one-click ambiguous approval.
