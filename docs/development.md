# Development guide

## Start locally

Use Docker with Compose v2. Native frontend tools use Node 22.x (at least 22.13) and npm 10+. Native backend tools use uv 0.12.17 and Python 3.13; uv can provision the interpreter. Commit both dependency lockfiles with changes.

From the repository root:

```powershell
node scripts/configure.mjs
docker compose up -d --build
docker compose ps
```

Without Node, copy `.env.example` to `.env` and fill the three password fields with independent cryptographically random values of at least 20 characters. Empty credentials fail startup. The helper refuses to overwrite `.env` and never prints its passwords. `.env` is excluded from Git and Docker build contexts. No provider or JWT secrets are required in Phase 1.

| Configuration                                | Purpose                                                                        |
| -------------------------------------------- | ------------------------------------------------------------------------------ |
| `COMPOSE_PROJECT_NAME`                       | Local namespace, `forge`                                                       |
| `FORGE_ENVIRONMENT`                          | `development`, `test`, `production`; production disables interactive API docs  |
| `FORGE_LOG_LEVEL`                            | Structured log level, default `INFO`                                           |
| `FORGE_DATABASE_NAME`                        | Database, `forge`; letters/digits/underscores only                             |
| `FORGE_DATABASE_HOST`, `FORGE_DATABASE_PORT` | Native API connection, `127.0.0.1:15432`; Compose overrides to `postgres:5432` |
| `FORGE_DATABASE_PASSWORD`                    | Restricted `forge_app` credential                                              |
| `FORGE_MIGRATION_PASSWORD`                   | `forge_migrator` DDL credential                                                |
| `POSTGRES_PASSWORD`                          | Bootstrap administrator credential, supplied only to PostgreSQL                |
| `WEB_PORT`, `API_PORT`, `POSTGRES_PORT`      | Loopback host ports 3000, 8000, 15432                                          |

Change both `POSTGRES_PORT` and `FORGE_DATABASE_PORT` when changing the native database port. Compose frontend uses server-only `API_INTERNAL_URL=http://backend:8000`; native frontend defaults to `http://127.0.0.1:8000`. Override that variable in the native frontend process if the API port differs. No database values enter browser bundles.

## Native workflows

Frontend, from the root (stop the container occupying port 3000):

```powershell
docker compose up -d postgres backend
docker compose stop frontend
npm ci
npm run dev
```

Backend, starting from the root (stop the container occupying port 8000):

```powershell
docker compose up -d postgres
docker compose stop backend
Set-Location apps/api
uv sync --frozen
uv run --env-file ../../.env python -m forge.migration
uv run --env-file ../../.env uvicorn forge.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Settings deliberately does not search arbitrary parent directories for secrets. The native commands load `.env` explicitly. If uv was installed as a Python module, use the interpreter containing it, for example `py -3.14 -m uv`, in place of `uv`.

## Migrations and database roles

Container initialization creates `forge_bootstrap`, `forge_migrator` and `forge_app`. These are infrastructure roles, not application users. Runtime has no superuser, RLS-bypass, role-creation or table-creation privilege. SQL values are safely quoted in the bootstrap script.

Alembic revision `0001_foundation` creates the `forge` schema under the migration role and grants runtime schema usage. `public.alembic_version` stores the revision and grants runtime SELECT for readiness. No organization-owned tables exist yet. Tenant RLS, composite keys and DML grants arrive with Phase 2; this foundation does not claim tenant isolation before those tables exist.

The backend entrypoint serializes `upgrade head` under a bounded PostgreSQL advisory lock before starting Uvicorn. It removes the migration password from the launched web process environment. The container configuration still supplies that credential for restarts; a separate release migration job is a production-phase concern. Repeated startup is safe, and readiness compares applied revisions to migration heads in the packaged code. No runtime `create_all()` exists. Baseline downgrade uses `DROP SCHEMA ... RESTRICT` to protect later tables.

## Automated checks

Frontend, from the root:

```powershell
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm audit --audit-level=high
```

Backend, from `apps/api`:

```powershell
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q -m 'not integration'
```

All backend tests with real PostgreSQL, from the root:

```powershell
node scripts/test-backend.mjs
```

This starts PostgreSQL if necessary, builds the test image, creates a fresh `forge_<hex>_test` database and runs all tests. Cleanup removes only that generated database. Tests cover safe repeated migration, downgrade/upgrade readiness and runtime DDL denial. Direct integration runs require `FORGE_RUN_DB_TESTS=1` and a database ending in `_test`; prefer the runner to avoid selecting an existing test database.

Browser checks against running Compose:

```powershell
npx playwright install chromium
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:3000'
$env:FORGE_E2E_LIVE = '1'
npm run test:e2e
```

Without those environment variables, Playwright starts a dev server on 3100 and skips live-database assertions. Test-only network mocks never ship in the app. CI runs native checks, production build, Docker startup, isolated PostgreSQL tests and desktop/mobile browser checks against the real stack.

## Manual acceptance

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/health/live
Invoke-RestMethod http://localhost:8000/api/v1/health/ready
Invoke-RestMethod http://localhost:3000/api/v1/health/ready
```

Expect live `ok`; readiness `ready`, database `up`, migrations `current`. On `/system`, **Run checks** reruns real requests. Navigate to **Setup guide**; verify keyboard navigation and narrow-screen layout.

For a local outage check, stop PostgreSQL, reload `/system`, and observe unavailable database / unverified schema. Liveness still returns 200; readiness returns 503 with safe details. Restore PostgreSQL and rerun checks:

```powershell
docker compose stop postgres
docker compose up -d postgres
```

For persistence, stop the backend, recreate only PostgreSQL, inspect the existing revision before the backend restarts, then restore the backend:

```powershell
docker compose stop backend
docker compose up -d --force-recreate --wait postgres
docker compose exec -T postgres psql -U forge_bootstrap -d forge -c 'SELECT version_num FROM public.alembic_version'
docker compose up -d --wait backend
```

Use the configured database name if different. Named volume storage must retain `0001_foundation`. `docker compose down` preserves it; adding `--volumes` intentionally discards data and is not a connection-repair step.

## Troubleshooting and local credential rotation

```powershell
docker compose logs --tail=80 backend postgres
docker compose ps
```

- **Port blocked:** change the host port. Windows can reserve ports without a listening process; 15432 avoids the blocked 5432 on this workstation.
- **Migration startup failed:** verify reachability and the migration-role credential; startup logs give a safe exception type. The API does not launch after a failed migration.
- **Schema pending:** compare the deployed build and revision. Rebuild/restart to apply forward migrations; do not manually edit the version table.
- **Changed `.env` passwords:** existing database roles retain their old credentials. Environment changes alone do not rotate them.

For local role rotation, open psql interactively so no secret enters shell arguments/history:

```powershell
docker compose exec postgres psql -U forge_bootstrap -d forge
```

Inside psql run `\password forge_app` or `\password forge_migrator`, enter the new password at the hidden prompts, then `\q`. Update the matching `.env` value and recreate the backend. Rotate `forge_bootstrap` similarly, update `.env`, and recreate PostgreSQL while retaining the volume. A production secret-management workflow belongs to Phase 13.

## Toolchain decisions and known warnings

Next.js 16.3.5 / React 19.3.0 and Tailwind 4.3.3 are locked. Lint runs separately from build, and Tailwind uses its PostCSS adapter. [Next.js installation](https://nextjs.org/docs/app/getting-started/installation), [Tailwind setup](https://tailwindcss.com/docs/installation/framework-guides/nextjs)

shadcn/ui uses its manual CSS-variable structure and a source-owned Button primitive. [shadcn Tailwind v4 guidance](https://ui.shadcn.com/docs/tailwind-v4)

ESLint 9.39.4 is retained because the current React lint plugin declares support through ESLint 9. It is development-only and deprecated upstream; no npm audit findings were present at verification. Upgrade it when the plugin contract supports ESLint 10. The backend's Starlette test client emits upstream httpx/AnyIO deprecation warnings; tests pass and warnings are not suppressed.

Python 3.13, FastAPI 0.141.1, SQLAlchemy 2.0.54, Pydantic 2.13.5 and Alembic 1.20.0 are locked with uv. Node, Python and PostgreSQL container bases are digest-pinned; application runtime images use non-root users and separate runtime/test stages. [FastAPI container guidance](https://fastapi.tiangolo.com/deployment/docker/)
