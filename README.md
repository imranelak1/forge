# Forge

Engineering intelligence and pipeline automation for software teams.

Forge traces changes through pull requests, CI, tests, deployments and production errors, with evidence behind insights and auditable pipeline responses.

**Current milestone: Phase 1 — Project Foundation.** The running application includes a responsive dark shell, honest engineering empty states, live API/database/schema checks, and setup guidance. Authentication and organizations start in Phase 2; integrations and metrics arrive later. No customer records or synthetic dashboard metrics are included yet.

## Run locally

Requires Docker with Compose v2. The optional configuration helper requires Node.js 22.13 or newer in the 22.x line.

```powershell
node scripts/configure.mjs
docker compose up -d
docker compose ps
```

The helper generates three independent local database passwords in ignored `.env`, refusing to overwrite an existing file. Alternatively, copy `.env.example` to `.env` and configure all password fields with distinct random values of at least 20 characters. Docker builds missing images automatically; after source changes use `docker compose up -d --build`.

- Landing page: [localhost:3000](http://localhost:3000)
- Application: [localhost:3000/app](http://localhost:3000/app)
- System checks: [localhost:3000/system](http://localhost:3000/system)
- API documentation (development): [localhost:8000/docs](http://localhost:8000/docs)
- Liveness: [localhost:8000/api/v1/health/live](http://localhost:8000/api/v1/health/live)
- Readiness: [localhost:8000/api/v1/health/ready](http://localhost:8000/api/v1/health/ready)

Default host ports are 3000 (web), 8000 (API), and **15432** (PostgreSQL). Configure alternate ports in `.env` if needed. The database keeps its internal container port 5432. All published ports bind to loopback. Only frontend, backend and postgres run.

## Verify

```powershell
npm ci
npm run lint
npm run typecheck
npm test
npm run build
node scripts/test-backend.mjs
npx playwright install chromium
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:3000'
$env:FORGE_E2E_LIVE = '1'
npm run test:e2e
```

The backend test runner creates a random temporary PostgreSQL database and removes only that database after testing. It does not migrate or clear the application database. See [development instructions](docs/development.md) for native workflows, checks and troubleshooting.

## Repository

```text
apps/web/             Next.js, TypeScript, Tailwind, shadcn/ui, TanStack Query
apps/api/             FastAPI, Pydantic, SQLAlchemy, Alembic and tests
data/dbt/             Phase 10 analytical-model boundary
data/pipelines/       Future scheduled pipelines
infrastructure/       Containers and PostgreSQL role bootstrap
scripts/              Local configuration and isolated database checks
docs/                 Architecture, contracts, ADRs and milestone handoffs
```

Recharts is pinned for later database-backed analytics; no charts are rendered without data. Lucide supplies interface icons; Geist is served from the bundled font package.

## Documentation

The [landing-page handoff](docs/landing-page.md) covers the centered WebGL cable, monochrome landing page and its accessibility fallbacks.

The [frontend design reference](apps/web/DESIGN.md) records the implemented typography, colors, components and responsive behavior.

| Document                                               | Contents                                                 |
| ------------------------------------------------------ | -------------------------------------------------------- |
| [Phase 1 handoff](docs/phase-1-review.md)              | Changes, commands, verification and limitations          |
| [Development](docs/development.md)                     | Local/native workflows, credentials and migrations       |
| [Architecture](docs/architecture.md)                   | Diagrams, module boundaries and deployment evolution     |
| [Data model](docs/data-model.md)                       | Entity grains, tenant constraints and lifecycle evidence |
| [APIs](docs/apis.md)                                   | Implemented health routes and future contracts           |
| [Integrations](docs/integrations.md)                   | GitHub, Actions, JUnit and Sentry                        |
| [Pipelines](docs/pipelines.md)                         | Durable processing, correlation and automation           |
| [Analytics](docs/analytics.md)                         | Metric definitions and future dbt models                 |
| [Security and operations](docs/security-operations.md) | Phased security, tests and recovery requirements         |
| [Milestones](docs/roadmap.md)                          | Acceptance gates for Phases 0–13                         |
| [ADRs](docs/adr/README.md)                             | Approved architectural decisions                         |
| [Phase 0 record](docs/phase-0-review.md)               | Historical architecture handoff                          |

This is a local foundation, not a production SaaS. No authentication, tenant entities, ingestion, worker, analytics engine or automated actions exist yet. Phase 2 begins only after the user's next instruction.
