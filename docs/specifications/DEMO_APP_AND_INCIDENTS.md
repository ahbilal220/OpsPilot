# Demo Application and Incident Design

## 1. Purpose

OpsPilot needs a controlled system that can fail in reproducible ways.

Create a small e-commerce or travel-booking demo application with:

- `gateway`
- `orders/trips API`
- `recommendation service`
- PostgreSQL
- Redis
- mock external provider

For MVP these can live in one demo repository and may be separate containers.

## 2. Required Telemetry

Demo application emits:

- HTTP request count,
- latency histogram,
- error count,
- DB query count,
- DB pool usage,
- Redis operation errors,
- external API latency.

## 3. Scenario 1 — N+1 Query

Injection:
replace batched/eager loading with per-row lazy query.

Expected evidence:
- latency increase,
- query count increase,
- relevant recent commit,
- offending source code.

## 4. Scenario 2 — Bad Environment Variable

Injection:
invalid timeout/connection setting.

Expected evidence:
- deployment timing,
- config change,
- startup/runtime error.

## 5. Scenario 3 — Redis Outage

Injection:
stop Redis or point service to invalid host.

Expected evidence:
- Redis connection errors,
- cache miss/fallback behavior,
- service degradation.

## 6. Scenario 4 — Slow Dependency

Injection:
mock provider delays responses.

Expected evidence:
- downstream latency,
- trace/span or request logs,
- service-level latency correlation.

## 7. Scenario 5 — DB Pool Exhaustion

Injection:
reduce pool size and create concurrent load.

Expected evidence:
- pool saturation,
- timeout errors,
- traffic correlation.

## 8. Scenario 6 — Bad Deployment

Injection:
deploy known regression commit.

Expected evidence:
- incident start immediately after deployment,
- change diff,
- symptom resolved by rollback/fix.

## 9. Reset

Every scenario must have:
- inject command,
- verify command,
- reset command,
- ground truth.

Example:

```bash
make scenario-n-plus-one
make verify-n-plus-one
make reset-demo
```
