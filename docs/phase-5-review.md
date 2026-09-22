# Phase 5: CI/CD intelligence

Scope: persisted GitHub Actions attempts/jobs, independent deployment/status history, CI and deployment metrics with inspectable evidence, explicit environment classification and isolated demonstration facts. The existing PR/commit surfaces and approved animated landing remain available.

## Delivered behavior

CI shows outcomes per attempt, with reruns retained separately. Success and failure fractions share the decisive completed cohort. Duration and queue distributions expose exact mean, median, P75 and P95, eligible/excluded counts and reasons. Daily UTC results and recurring workflow failures link to filtered source attempts. Job details and explicit same-repository commit/PR links remain inspectable.

Workflow completion is a **last-job-completion proxy**, derived only from complete terminal job evidence. Missing completion stays unknown and visible in coverage; REST `updated_at` is never substituted. Rerun queue time remains unavailable because the provider creation timestamp belongs to the original run. Generic failures have unknown causes; logs are not downloaded.

Deployments come from independent provider objects and status histories. A deployment's first success counts once, including when later statuses repeat success or become inactive. Complete status history is required for eligibility. Production classification comes from an explicit provider flag or audited repository/environment override; names alone never classify. Verified owners/admins may set or remove overrides in Forge, with CSRF, origin validation and tenant audit.

## Files, schema and endpoints

| Area                | Main files                                                                                                 |
| ------------------- | ---------------------------------------------------------------------------------------------------------- |
| Schema              | `apps/api/migrations/versions/0007_cicd.py`                                                                |
| Analytics and reads | `apps/api/src/forge/{domain,repositories,services,api/v1}/delivery.py`                                     |
| Collection          | GitHub adapter, CI/CD normalization, repository checkpoints and worker                                     |
| Demo                | `domain/demo_delivery.py`, `repositories/demo.py`, `seed.py`                                               |
| Interface           | `apps/web/src/features/delivery`, CI/deployment/environment routes and API proxy                           |
| Decisions           | [ADR 013](adr/013-actions-deployment-intelligence.md), [analytics](analytics.md), [API contracts](apis.md) |

Migration `0007_cicd` adds `workflow_runs`, `workflow_jobs`, `workflow_run_pull_requests`, `deployment_environments`, `deployments` and `deployment_statuses`. All force tenant RLS and enforce same-repository composite references. Repositories gain independent CI/deployment coverage and bounded source windows. No metrics table or extra infrastructure service is needed.

All routes follow `/api/v1/organizations/{organization}`. Reads require active membership; foreign resources return generic 404s. GET routes include `/metrics/ci`, `/workflow-runs`, `/workflow-runs/{id}`, attempt children `jobs`, `pull-requests`, `commits`, `/metrics/deployments`, `/deployments`, `/deployments/{id}`, deployment children `statuses`, `commits`, and `/repositories/{id}/environments`. PUT `/repositories/{id}/environments/classification` sets or removes an override. [Full filter and cursor contracts](apis.md)

## Run and inspect

From the repository root:

```powershell
docker compose --parallel 1 up -d --build --wait --wait-timeout 180
docker compose exec backend python -m forge.seed
node scripts/test-backend.mjs
npm run lint
npm run typecheck
npm test
npm run test:config
npm run format:check
$env:PLAYWRIGHT_BASE_URL='http://localhost:3000'
$env:FORGE_E2E_LIVE='1'
npm run test:e2e
```

Open `/app/ci`, inspect outcome cohorts and excluded queue samples, then open an attempt's jobs and associated changes. Open `/app/deployments`, inspect included/excluded successes and status history, then use Environment classification to inspect or change a repository override. Removing an override restores each deployment's own provider flag. A viewer can inspect but cannot edit.

Opt-in seeding adds **108 workflow attempts and 36 deployments** in Demo One; Demo Two has half those counts. These are generated records with related jobs, status histories, retries and incomplete-evidence examples, not hardcoded metric values. Stable IDs extend the existing Phase 4 change identities and persisted anchor. Repeated seeding preserves credentials and records, writes only designated owner-held demo organizations, never creates live jobs/bindings, and is rejected in production.

For real collection, grant the existing GitHub App **Actions: Read** and **Deployments: Read**, enable **Workflow run**, **Deployment** and **Deployment status** subscriptions, and accept the updated installation permissions. Then run a repository sync. Each absent capability is unavailable independently; PR/commit collection continues. [Setup](github-setup.md)

## Verification

- Isolated PostgreSQL/backend suite: **312 passed**, including migration/RLS, same-repository constraints, attempt retries, source revision/revocation fences, resumable pages, late explicit-link repair, exact percentile/cohort calculations, status deduplication, environment authorization/audit and demo idempotence. Two upstream test-client deprecation warnings remain.
- Production Chromium suite: **68 passed** across desktop and mobile, including real identity/organization flows and the unchanged animated landing. Delivery-specific cases cover metric/evidence filter continuity, jobs/statuses, policy edit/remove, viewer restrictions, tenant switching and retry recovery.
- The production build applied `0007_cicd`; backend, frontend, PostgreSQL and worker are healthy. Demo One was extended in place to 108 attempts and 36 deployments without changing its existing PR/commit identities or credentials.
- Initial actual-database browser inspection found no page errors or horizontal overflow across 16 desktop/mobile views. Coverage copy was then condensed into an accessible disclosure to bring metrics into view sooner; the final confirmation is recorded below.

The real installation was checked independently of fixtures. Its single selected repository remains connected and active. CI and deployment capability scans both completed, accurately reporting `actions_permission_required` and `deployments_permission_required`; they did not invent records or interrupt core access. The effective installation permissions remain Contents, Metadata and Pull requests read, and App subscriptions remain Push and Pull request. No additional repository was selected. Live CI/deployment history cannot be claimed until the owner grants and accepts the new permissions and enables the events listed above.

Frontend validation passed **159 unit tests**, the configuration test, ESLint, TypeScript and Prettier. Backend Ruff, Ruff formatting and mypy passed. The final frontend production build passed. One confirmation batch of the affected desktop/mobile CI and deployment summaries showed no browser errors or horizontal overflow; compact coverage retains uncertainty and exposes the detailed explanation on demand. All **22 affected browser checks passed again** after that correction.

## Limits and next gate

- Completion proxy and unknown rerun queue timestamps limit what CI timing can claim. Non-decisive conclusions remain separate from success/failure rates.
- Provider retention and bounded pagination do not establish unlimited history. Historical scans and webhooks reconcile known records; scheduled reconciliation remains Phase 10.
- Deployment frequency remains unavailable for incomplete source windows or status history. Repeated success statuses never inflate counts.
- No logs, test reports, artifacts, Sentry data or automatic deployment actions are implemented in this phase.
- Live Actions/deployment collection requires accepted App permissions. Generated demo facts never impersonate live GitHub sources.

Phase 6 begins only after the user's next instruction.
