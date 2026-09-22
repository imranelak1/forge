# Phase 3: GitHub integration

Date: 2026-09-22. Scope: GitHub App repository authorization, selection, historical sync and signed webhooks. The approved landing remains unchanged. PR and commit analytics are Phase 4.

## Delivered behavior

A verified Forge owner/admin can authorize a GitHub App, prove ownership of the source account, bind an installation to one organization, select accessible repositories and monitor their imports. GitHub/Google sign-in remains independent. Source authorization requires the personal GitHub account owner or an active GitHub organization administrator; repository access alone is insufficient.

The Integrations screen shows configuration, connection, repository catalog and selection states. Repositories shows real stored metadata, PR/commit counts, last successful sync and paginated sync history. Running work polls for progress; retries and partial failures remain visible. Desktop tables become labeled rows on mobile. Members/viewers can inspect permitted data, while mutations require a verified owner/admin. Browser test fixtures are clearly synthetic and do not seed engineering data into the running application.

Background jobs persist one page at a time with checkpoints, finite retries and fenced leases. Webhook receipts and jobs commit together before acknowledgement. Exact duplicates create no second job; invalid signatures and changed delivery identities are rejected. Revocation cancels affected work and invalidates fetched results. Uninstall/reinstall preserves separate source histories. Disconnect retains imported records and prevents new collection.

## Files and important decisions

| Area          | Files and purpose                                                                                                                                                                                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Schema        | `apps/api/migrations/versions/0004_github.py`, `0005_github_access.py`: eleven tables, forced RLS, composite foreign keys, bounded job claim function, installation-scoped repository uniqueness and retention index                                      |
| Provider      | `apps/api/src/forge/integrations/github.py`: fixed-host GitHub App authorization, administrator proof, installation tokens, bounded HTTP responses and rate-limit classification                                                                          |
| API           | `api/v1/github.py`, `api/v1/webhooks.py`, `services/github.py`, `services/webhooks.py`, `repositories/github.py`, `repositories/webhooks.py`: session/CSRF/RBAC checks, encrypted short-lived authorization, catalog/selection/history and signed ingress |
| Worker        | `workers/github.py`, `repositories/pipeline.py`, `domain/github.py`: leases, checkpoints, retries, normalization, source timestamp guards, replay protection and revocation checks                                                                        |
| Web           | `apps/web/src/features/github`, `/app/integrations`, `/app/repositories`, overview, navigation, guide, auth provider and same-origin proxy                                                                                                                |
| Operations    | `.env.example`, `docker-compose.yml`, configuration validation, application wiring, structured logs and isolated backend test runner                                                                                                                      |
| Tests         | GitHub provider/integration, pipeline policy/integration, webhook ingress, UI/proxy/auth-provider unit tests and desktop/mobile GitHub workflows                                                                                                          |
| Documentation | Architecture, APIs, data model, integrations, pipelines, development, security, product/design references, [ADR 011](adr/011-github-phase-3.md) and [GitHub setup](github-setup.md)                                                                       |

The worker is a fourth Compose service using the backend runtime image and restricted DB role. It receives no migration, SMTP or social-login secrets. No Redis, Kafka or scheduler was added. Structured worker logs contain job/organization IDs, fencing generation and fixed error codes, without raw payloads or credentials.

## Database changes

`0004_github` follows the social-login migration. Eight tenant tables are `integrations`, `repositories`, `sync_runs`, `webhook_inbox`, `jobs`, `pull_requests`, `commits` and `events`. Three global control tables hold short-lived authorization, installation routing and minimal delivery receipts. Every tenant table forces RLS; missing tenant context denies reads/writes. Composite references also bind repository data to its integration.

The restricted `forge.claim_job(uuid)` function claims one available or expired job and returns only tenant/job/fence metadata. Subsequent work uses transaction-local tenant context. API and worker share a non-owner, non-superuser runtime role without `BYPASSRLS`.

`0005_github_access` makes repository identity unique within an installation and indexes bounded processed-payload cleanup. Its downgrade refuses contraction if reinstallations have produced multiple histories; it never discards history to satisfy the older constraint.

## Endpoints

All routes use `/api/v1`. Below, `{org}` means `/organizations/{organization_id}` and `{github}` means `{org}/integrations/github`.

| Method and route                                 | Result                                                          |
| ------------------------------------------------ | --------------------------------------------------------------- |
| `GET {github}`                                   | Configuration, pending authorization and connections            |
| `POST {github}/authorize`                        | One-use browser/session-bound GitHub App authorization          |
| `GET /integrations/github/callback`              | Validated callback and fixed UI redirect                        |
| `GET {github}/authorizations/{id}/installations` | Provider-authorized installation choices                        |
| `POST {github}/connections`                      | Verify source administrator, bind installation, enqueue catalog |
| `POST {github}/connections/{id}/refresh`         | Recheck access and request catalog sync                         |
| `DELETE {github}/connections/{id}`               | Disconnect and cancel future ingestion                          |
| `GET {github}/connections/{id}/repositories`     | Cursor-paged accessible repository catalog                      |
| `POST {github}/connections/{id}/selection`       | Save explicit changes and enqueue/cancel imports                |
| `GET {org}/repositories`                         | Selected repositories, database counts and latest sync          |
| `POST {org}/repositories/{id}/sync`              | Durable manual/retry sync request                               |
| `GET {org}/repositories/{id}/sync-runs`          | Cursor-paged sync history                                       |
| `POST /webhooks/github`                          | Signed raw-body intake, deduplication and durable receipt       |

Browser mutations require the current verified manager, exact origin and session-bound CSRF protection. Callback handling instead uses single-use state plus browser/session/user/organization binding. Webhooks use the App signature and server-controlled installation mapping. The frontend proxy exposes only the intended browser routes, not webhook intake.

## Run and verify

From the repository root:

```powershell
node scripts/configure.mjs --upgrade
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
node scripts/test-backend.mjs
npm test
npm run test:config
$env:PLAYWRIGHT_BASE_URL='http://localhost:3000'
$env:FORGE_E2E_LIVE='1'
npm run test:e2e
```

Open `http://localhost:3000/app/integrations`. The current local GitHub App configuration is blank, so it accurately shows setup required. Register/configure the separate App using [the exact setup instructions](github-setup.md), rebuild, then authorize an installation, select a repository and wait for its catalog/history sync. Inspect a real PR/push webhook delivery, redeliver it to check deduplication, remove access, and restart the worker during a multi-page import to verify live behavior.

The automated backend suite uses a temporary isolated PostgreSQL database and substitutes GitHub HTTP responses. It exercises real authentication, RLS, transactions, migrations, authorization races, duplicate ingestion, retries, lease recovery, access revocation and reinstall history. It does not prove live external account authorization. Browser tests cover real local auth/navigation plus explicitly synthetic GitHub states and no-overflow desktop/mobile layouts.

## Final verification

- Backend isolated PostgreSQL suite: **228 passed**, including migration roundtrip and both final authorization-race/processing-timeout regressions. Two upstream test-client deprecation warnings remain.
- Frontend unit suite: **75 passed**. Configuration creation/upgrade test: **1 passed**.
- Production-stack Chromium browser suite: **52 passed**, across desktop and mobile, including identity, social OAuth transport, GitHub controls and the approved landing animations.
- Ruff, Ruff formatting, mypy, ESLint, TypeScript and repository Prettier checks passed. Production Docker build passed; backend, frontend, PostgreSQL and worker are healthy with migration `0005_github_access` applied.
- Bounded visual review covered actual setup/empty screens and explicitly synthetic populated catalog, repository and sync states. The mobile sync-history clipping defect was corrected and confirmed; final review found no blocking UI gaps.

## Limits and next gate

- Live GitHub App authorization and external webhook delivery require the user's six App settings and reachable HTTPS webhook URL. Social OAuth credentials do not replace them. No customer repository was connected automatically.
- Initial history is fixed at 90 days of updated PRs and default-branch commits. Push payload commits are imported, but truncated non-default-branch pushes may omit history outside the default-branch reconciliation path. Provider pagination is not an immutable snapshot.
- Bounds are 1 MiB webhook bodies, 8 MiB provider responses, 100 records/page, 100 pages/stage, eight attempts/failing page and a 60-second lease. A 50-second processing deadline limits each job operation. Capacity errors stay visible.
- Manual/webhook-driven reconciliation is implemented. Scheduled polling, missed-delivery recovery, automatic replay of dead webhooks and an operator replay UI remain future work.
- Each claimed tenant job clears at most 100 processed raw payloads older than seven days. Idle tenants wait for the next job. Failed/queued payloads and deduplication metadata remain retained; scheduled purge is not implemented.
- Reviews, issues, PR/commit analytics, Actions, deployments, tests, Sentry, correlations and automated actions remain later milestones. No hardcoded dashboard metrics or fabricated provider connection is presented.

Phase 4 starts only after the user's next instruction.
