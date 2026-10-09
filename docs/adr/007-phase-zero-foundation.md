# ADR-007: Phase 0 foundation and scope

Status: implemented and validated for Phase 0; awaiting user review.

## Scope
The roadmap requires a user to log in, extending CODEX_INSTRUCTIONS' auth skeleton.
Implement registration/login/logout/profile and a minimal login UI. All later modules
are empty package boundaries. No incident CRUD, worker, tools, model adapters, agents,
RAG, sandbox executor, or approval execution is implemented.

## Decisions
- Modular monolith; FastAPI on Python 3.12+, SQLAlchemy 2 async, PostgreSQL with a
  pgvector-capable image. Vector extension/tables wait for their own Alembic migration.
- A separate one-shot Compose migration service runs before API startup. No startup
  create_all or manual schema edits; test databases also use Alembic.
- Argon2id password hashes and random opaque sessions in Redis. Only SHA-256 session
  token digests are Redis keys; HttpOnly, SameSite=Strict cookies carry tokens. Sessions
  expire, rotate on login, and are revoked on logout. Redis loss signs users out.
- Browser requests use the Next.js same-origin proxy. Mutating auth requests require
  an exact configured Origin, including CLI requests. Secure cookies and disabled
  registration are the application defaults; .env.example explicitly enables local
  HTTP demo mode. Never deploy that local configuration publicly.
- Registration rejects supplied roles and assigns viewer. Role dependencies read the
  current database role on every request. Administrative role management is deferred;
  no API can elevate an account. No approval authority exists in Phase 0.
- Redis provides an atomic per-peer 20-attempt/minute login/registration limit. Proxy
  headers are not trusted. Behind Next.js this is a conservative shared proxy bucket;
  a trusted-proxy-aware public deployment policy is deferred.
- Health checks are intentionally anonymous, as are login and registration. Profile
  and logout use authentication dependencies; future domain routes must do likewise.
- JSON request telemetry uses route templates and allowlisted fields, excluding raw
  bodies, headers, query strings, passwords, tokens, and exception messages. Auth
  audit events go to structured logs. Durable append-only domain auditing and OTEL
  export remain later-phase work; trace/incident fields are null for now.
- Runtime and test Docker targets are separate. Runtime dependencies have their own
  pinned lock; development tools are installed only for checks.
- No host execution tools or production credentials. Safety-level conflicts in the
  specifications do not affect this phase because no agent tools exist. Resolve the
  stricter write-approval policy before implementing Phase 2/5.

## Validation boundaries
SQLite migration-backed tests and a Redis double exercise fast API behavior. They
cannot establish PostgreSQL enum behavior or Redis Lua/expiry behavior. Separate
integration tests, migration round-trip/check, and Compose proxy smoke tests cover
those in CI. No benchmark results are claimed.

References: [FastAPI password hashing](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
and [Next.js installation](https://nextjs.org/docs/app/getting-started/installation).
