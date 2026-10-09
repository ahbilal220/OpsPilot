# Phase 0 validation status

Phase 0 is implemented and tested. Phase 1 and agent implementation have not begun.
Review is the only remaining Phase 0 handoff item.

## Measured checks

- Read CODEX_INSTRUCTIONS.md, all five required documents, and the remaining supplied
  specifications to resolve Phase 0 architecture, data, UI, and acceptance details.
- Complete container backend suite: **19 passed**, including real PostgreSQL and Redis.
  Covers auth lifecycle, hashing, role enforcement, CSRF, session rotation/revocation/
  expiration, validation, rate limits, dependency failures, readiness, and safe errors.
- Ruff lint and formatting checks passed; strict mypy passed (28 source files).
- Alembic schema comparison against PostgreSQL: no pending changes.
- Separate disposable PostgreSQL database: upgrade, check, downgrade, re-upgrade,
  and check passed. The disposable database was removed afterward.
- Next.js 16.3.5: ESLint, TypeScript, and production build passed, including Docker build.
- pnpm 10.17.1 frozen-lockfile installation passed.
- Docker Compose configuration validation, image builds, and `up --wait` passed.
  API, frontend, PostgreSQL, and Redis reported healthy; migration exited successfully.
- HTTP acceptance through Next.js proxy: homepage, health, readiness, registration,
  login, authenticated profile, and logout passed.
- Browser acceptance: registration/sign-in showed the viewer profile, session survived
  reload, and logout returned to sign-in. Rendered layout visually inspected.

## Environment and decisions

Docker Engine 29.8.1 and Compose 5.5.1 were installed with the user's local sudo step.
This machine's working daemon is the **default** Docker context. Its selected
`desktop-linux` context was unavailable; validation explicitly used `--context default`
without changing the user's selection. Existing sessions may require `sg docker -c`.

The stack is left running at http://localhost:3000 (API on localhost:8000).
A generated local database password is stored in ignored `.env` with mode 0600.
Only local test accounts were created; create your own viewer account in the UI.

Application/runtime dependencies and development dependencies have separate pinned
locks. A dedicated test image keeps lint/type-check packages out of the runtime image.
CI is configured but has not run remotely because this folder has not been pushed.

See [ADR-007](adr/007-phase-zero-foundation.md) for scope and security decisions.
No benchmark, incident workflow, provider integration, tool execution, or Phase 1
functionality is claimed or implemented.
