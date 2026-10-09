# Testing Strategy

## 1. Testing Pyramid

### Unit Tests
Cover:
- policies,
- parsers,
- schemas,
- scoring,
- state transitions,
- adapters.

### Integration Tests
Cover:
- PostgreSQL,
- Redis,
- pgvector,
- Prometheus adapter,
- Git adapter,
- sandbox runner.

### Contract Tests
Ensure tool schemas and provider interfaces remain stable.

### Workflow Tests
Execute investigation state graph with mocked tools/models.

### End-to-End Tests
Run a complete incident against the demo application.

### Benchmark Tests
Inject known failures and score results.

## 2. LLM Testing

Avoid tests that require exact natural-language strings.

Test:
- schema validity,
- required evidence IDs,
- policy compliance,
- tool-selection constraints.

## 3. Golden Fixtures

Store representative:
- logs,
- metric snapshots,
- git diffs,
- runbook chunks,
- structured model outputs.

## 4. CI Test Groups

Fast:
```text
unit + lint + typecheck
```

Medium:
```text
integration
```

Expensive:
```text
LLM evaluation + benchmark subset
```

Nightly/manual:
```text
full benchmark
```

## 5. Quality Gates

A PR should fail if:
- Ruff/formatter fails,
- mypy/pyright fails,
- unit tests fail,
- schema migrations are invalid,
- safety-policy tests fail.

## 6. Critical Safety Tests

1. Agent requests unregistered tool.
2. Agent requests write action without approval.
3. Retrieved document contains malicious instructions.
4. Model emits invalid JSON.
5. Tool times out.
6. LLM provider fails.
7. sandbox patch modifies forbidden file.
