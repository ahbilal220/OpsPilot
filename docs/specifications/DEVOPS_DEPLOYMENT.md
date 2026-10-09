# DevOps and Deployment

## 1. Local Environment

Use Docker Compose.

Services:

```yaml
api:
worker:
frontend:
postgres:
redis:
prometheus:
grafana:
demo-app:
load-generator:
```

Optional:
- Langfuse

## 2. CI/CD

GitHub Actions pipeline:

```text
checkout
-> Python lint
-> Python typecheck
-> backend tests
-> frontend lint/test
-> build Docker images
-> security scan
-> integration tests
-> publish images
-> deploy staging
```

## 3. Environments

### local
Full Docker Compose.

### staging
Public portfolio demo.

### production-like
Optional cloud environment for architecture demonstration.

## 4. AWS Reference Deployment

Reasonable portfolio architecture:

- ECS/Fargate for API/worker/demo service
- RDS PostgreSQL
- ElastiCache Redis
- CloudWatch/OpenTelemetry bridge as needed
- ALB
- S3 for large artifacts
- Secrets Manager
- ECR

Avoid Kubernetes initially unless you specifically want Kubernetes to be part of the project's learning objective.

## 5. Migrations

Use Alembic.

Every schema change requires migration.

## 6. Environment Configuration

Example:

```text
DATABASE_URL=
REDIS_URL=

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GOOGLE_API_KEY=

LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=

OTEL_EXPORTER_OTLP_ENDPOINT=

GITHUB_TOKEN=
GITHUB_REPO=
```

Do not require all LLM providers simultaneously.

## 7. Deployment Safety

Public demo must never contain credentials capable of changing real production infrastructure.

Use fake/demo repositories and isolated services.
