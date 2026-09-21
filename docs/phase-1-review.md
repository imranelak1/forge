# Phase 1 — Project Foundation

**PHASE COMPLETE — Project Foundation.** Implementation scope ends here; Phase 2 has not begun.

## Outcome

Forge now boots as a three-service local application. The Next.js interface has an engineering overview empty state, live system status and setup guide. FastAPI exposes versioned health contracts through service and repository layers. PostgreSQL starts with separate runtime/migration roles; Alembic owns the operational namespace. There are no hardcoded engineering metrics or fake login/integration actions.

## Files and boundaries

| Location                                       | Changes                                                                                                                                                                                                                                       |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/web/`                                    | Next.js/React/TypeScript app, Tailwind tokens, source-owned shadcn Button, Lucide icons, bundled Geist, TanStack Query, typed health client and same-origin forwarding; component and desktop/mobile browser tests                            |
| `apps/api/src/forge/`                          | Pydantic configuration, API contracts/error handling, health service/domain/repository, SQLAlchemy engine/base, structured logs and serialized migration startup; explicit future integration/analytics/automation/security/worker boundaries |
| `apps/api/migrations/`                         | Alembic environment/template and baseline revision `0001_foundation`                                                                                                                                                                          |
| `apps/api/tests/`                              | Configuration, liveness/readiness, error redaction, migration round-trip and database-role tests                                                                                                                                              |
| `infrastructure/`                              | Digest-pinned multi-stage Docker builds, non-root app runtimes, PostgreSQL role bootstrap                                                                                                                                                     |
| `docker-compose.yml`                           | Exactly frontend, backend and postgres; healthchecks, startup dependencies, loopback ports and persistent database volume                                                                                                                     |
| `scripts/`                                     | Non-overwriting secret generation and isolated PostgreSQL test runner                                                                                                                                                                         |
| `.github/workflows/ci.yml`                     | Frontend/API checks, Docker smoke/integration tests, browser tests and persistence check                                                                                                                                                      |
| `data/`                                        | Documented dbt/pipeline boundaries, with no premature runtimes or fake models                                                                                                                                                                 |
| Root config/lockfiles                          | npm workspace, uv lock, formatting, ignore rules and line-ending policy                                                                                                                                                                       |
| `docs/`, `PRODUCT.md`, frontend design records | Current runbook/handoff, updated implementation status and approved ADRs; design context for subsequent phases                                                                                                                                |

Recharts is installed and locked for later analytics; rendering charts waits for real persisted data. No Redis, Airflow, Kafka, ClickHouse or worker container has been introduced.

## Important implementation decisions

- Health routes delegate database work to a repository through a health service. Liveness is independent of PostgreSQL; readiness requires both connection and exact migration-head parity.
- Readiness failure returns 503 with a consistent problem envelope and safe check states. A down database gives unknown schema state, not a falsely diagnosed missing migration. Requests carry validated/generated request IDs and structured duration/status logs.
- Migration startup uses a PostgreSQL advisory lock with timeout, preventing competing startup migrations. The DDL password is removed before launching the web process. Local Compose still supplies it to the container for restarts; separate production release jobs remain Phase 13 work.
- Database passwords are never embedded in source or connection URL strings. SQLAlchemy constructs escaped URLs; logs omit driver details and credentials. The app database role cannot create tables and has no RLS-bypass privilege.
- Browser health requests stay same-origin. Only the two known health checks can be forwarded; the browser cannot choose an upstream URL or read internal connection settings.
- All unavailable future features are explicitly labeled. Failure descriptions describe what a check tests instead of asserting success. Mobile lifecycle overflow has a visible cue and keyboard focus.

## Database changes

Infrastructure initialization creates restricted `forge_app`, DDL `forge_migrator`, and bootstrap administrator roles. Alembic creates schema `forge`, owned by `forge_migrator`, grants runtime usage, and records `0001_foundation` in `public.alembic_version`. Runtime can read that revision table.

No users, organizations, engineering entities or demo records exist yet. RLS and tenant entity constraints will be implemented with Phase 2's schema, not claimed for nonexistent data. The baseline downgrade refuses to cascade through later tables.

## Endpoints and pages

| Route                                   | Behavior                                                                           |
| --------------------------------------- | ---------------------------------------------------------------------------------- |
| API `GET /api/v1/health/live`           | 200 when API process is responding; no database dependency                         |
| API `GET /api/v1/health/ready`          | 200 when connection and migration checks pass; otherwise safe 503 problem response |
| API `GET /api/v1/openapi.json`, `/docs` | Generated contract / interactive docs in development; absent in production         |
| Web `GET /api/v1/health/live`, `/ready` | Same-origin forwarding to the configured internal API                              |
| Web `GET /healthz`                      | Frontend process health only                                                       |
| Web `/`, `/system`, `/guide`            | Overview foundation, actual system checks and working setup guidance               |

## Run and manually test

The local `.env` has already been generated with independent random passwords and is ignored. On this workstation the application is running at `http://localhost:3000`; API docs are at `http://localhost:8000/docs`. PostgreSQL is published on `127.0.0.1:15432` because Windows blocked 5432.

For another checkout, from the root:

```powershell
node scripts/configure.mjs
docker compose up -d
docker compose ps
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
```

Skip configuration generation when `.env` already exists. Use `docker compose up -d --build` after code changes. Visit `/system`, run checks, and follow the guide links. Expect no connected sources, no organization session and no numerical engineering metrics.

Exact frontend, backend, browser, outage and storage-persistence commands are in [the development guide](development.md).

## Verification evidence

- Backend: 12 unit/integration tests passed, including real PostgreSQL migration round-trip, duplicate startup safety, and runtime-role DDL denial. Native unit-only run passed 10 tests; the two database tests are intentionally gated in that mode.
- Frontend: three component tests passed for healthy, offline and migration-pending states; six Playwright tests passed across 1440px desktop and 390px mobile, including real-stack readiness.
- Static/build checks: Ruff, Python formatting, strict mypy, ESLint, TypeScript, Prettier and production Next.js/Docker builds passed. npm dependency audit reported zero vulnerabilities.
- Compose: all three containers healthy, direct and forwarded readiness verified. PostgreSQL container recreation retained `0001_foundation` before the API restarted, confirming volume persistence independently of startup migration.
- Visual inspection: desktop/mobile captures had no page overflow or browser exceptions. A separate UI review identified unconditional success wording in failed checks; it was corrected to neutral descriptions, with a regression assertion. Mobile lifecycle continuation was also clarified.
- Final UI verdict: **ship** for Phase 1; both identified findings were scored resolved. A real PostgreSQL outage returned live 200 and ready 503, with database `down` and migrations `unknown`, and recovered after restart.

The workflow is committed for GitHub Actions, but no remote workflow run or deployment is claimed. Checks above were run locally.

## Limitations

Authentication, organizations/RBAC/RLS, integrations, ingestion, generated history, metrics and automation remain unimplemented by design. This is a locally runnable foundation, not a production deployment. Tests and docs exercise the current surface rather than fabricating later behavior.

ESLint 9 is deprecated upstream but matches the current React lint plugin's supported peer range; Starlette's test client emits httpx/AnyIO deprecation warnings. Neither warning was suppressed. Compatible upgrade tracking is documented in [development](development.md).

The user-approved dark-tool direction was implemented directly in code; no separately approved image comp exists. Visual checks assess the brief and actual UI, not fidelity to an invented reference.

**Next approval gate:** Phase 2 only, covering secure email/password sessions, organizations, membership, permissions and tenant isolation. Stop here until instructed to proceed.
