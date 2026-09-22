# Phase 4: Pull request and commit analytics

Scope: database-backed PR flow metrics, searchable PR/commit history, paginated source evidence and isolated demonstration history. The approved landing is preserved. Actions intelligence remains Phase 5.

## Delivered behavior

The overview computes cycle time, review waiting and approval-to-merge distributions from the same merged PR cohort. Mean, median, P75 and P95 use PostgreSQL exact percentiles. Each metric returns eligible/excluded counts and reasons, daily UTC trends, source coverage, input watermark and formula version `pr-flow-v1`. Evidence links retain the repository, author and time window. A separate current open queue reports age without mixing unmerged work into completed-cycle metrics.

PR details expose reviews, lifecycle events, explicit commit membership/merge associations and issue references. Commit details expose metadata-only file changes and their associated PRs. Lists and evidence use signed, tenant/filter-bound cursors. All active organization members may read; foreign organization/resource requests return generic 404s. Selected retained history remains readable after disconnection.

Provider enrichment adds one bounded page per durable job checkpoint. Reviews preserve a known historical approval after dismissal; a dismissal first observed without its prior state remains uncertain. A newer PR snapshot invalidates its previous evidence coverage. Files never persist patch contents. Missing Issues permission leaves that source unavailable while PR/commit collection continues.

## Files and storage

| Area              | Main files                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| Schema            | `apps/api/migrations/versions/0006_analytics.py`                                                        |
| Metrics and reads | `apps/api/src/forge/{domain,repositories,services,api/v1}/analytics.py`                                 |
| Collection        | GitHub adapter, evidence normalization, pipeline repositories and worker                                |
| Demo              | `domain/demo.py`, `repositories/demo.py`, `seed.py`                                                     |
| Interface         | `apps/web/src/features/analytics`, application overview/list/detail routes and API proxy                |
| Decisions         | [ADR 012](adr/012-pr-commit-analytics.md), [metric definitions](analytics.md), [API contracts](apis.md) |

Migration `0006_analytics` adds six tenant tables: `pull_request_reviews`, `pull_request_transitions`, `pull_request_commits`, `commit_files`, `issues` and `issue_pull_requests`. It extends repositories, PRs and commits with per-source coverage; repositories gain `is_demo`. Jobs gain repository-scoped enrichment routing. Composite references enforce both tenant and repository relationships, and all added evidence tables force RLS. No derived metric table is needed.

## Endpoints

All routes below follow `/api/v1/organizations/{organization_id}` and use GET.

| Route                                                      | Result                                                  |
| ---------------------------------------------------------- | ------------------------------------------------------- |
| `/metrics/pull-requests`                                   | Exact distributions, UTC trend, open queue and coverage |
| `/pull-requests`, `/commits`                               | Filtered, cursor-paged persisted records                |
| `/pull-requests/{id}`, `/commits/{id}`, `/issues/{id}`     | Record details                                          |
| `/pull-requests/{id}/{reviews,transitions,commits,issues}` | Paged PR evidence                                       |
| `/commits/{id}/{files,pull-requests}`                      | Paged file metadata and explicit associations           |
| `/repositories/{id}/issues`                                | Paged issues with source coverage                       |
| `/issues/{id}/pull-requests`                               | Explicit same-repository references                     |

Windows use timezone-aware `[from,to)` bounds, default 90 days, maximum 366. Lists default to 30 rows and allow at most 100. Optional repository and exact case-insensitive author filters apply consistently. PR activity uses `updated_at`; metric evidence uses `merged_at`. No provider calls occur on analytics reads.

## Run and verify

From the repository root:

```powershell
docker compose up -d --build --wait --wait-timeout 180
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

Seeding is optional and disabled in production. It creates 90 generated PRs in Demo One and 45 in Demo Two, with related commits and evidence spanning 90 days. Stable IDs and a persisted first-run anchor make reruns idempotent. Only the designated, owner-held demo organizations are writable. Synthetic repositories are marked, disconnected and excluded from live workers; source URLs are absent because no matching GitHub records exist. Existing demo passwords remain unchanged. New passwords print only on initial identity creation.

Open `/app`, inspect eligible and excluded metric evidence, follow a PR to its reviews/commits/issues, inspect commit file metadata, change UTC/repository/author filters, and switch organizations. For the connected real repository, request a normal sync on `/app/repositories` to enrich existing commits.

## Verification

- Isolated PostgreSQL/backend suite: **279 passed**, including migrations, seed idempotence, worker fencing/revocation, provider limits, exact percentiles, evidence pagination and cross-tenant/repository negative cases. Two upstream test-client deprecation warnings remain.
- Frontend unit suite: **117 passed**; configuration generation/upgrade: **1 passed**.
- Production Chromium suite: **58 passed** across desktop and mobile. After the final mobile filter/guide changes, all **12 affected analytics/foundation checks passed again**.
- Ruff, Ruff formatting, mypy, ESLint, TypeScript, Prettier and whitespace checks passed. The final production Docker build passed; backend, frontend, PostgreSQL and worker are healthy with `0006_analytics` applied.
- Independent code review found no blocking isolation, metric-grain or ingestion-fencing issues after fixing inactive-source coverage and adding a self-review demo example. Bounded browser review confirmed no page errors or horizontal overflow in the inspected views.

The running local GitHub installation was verified independently of fixtures: one selected repository retained its 30 real commits; all 30 now have complete file coverage with 417 persisted file-change records. Its 31 enrichment jobs completed without errors. No extra repository was selected. The source has no imported PRs, so live review timing is not claimed; persisted demo history and hand-calculated database fixtures cover that path. The optional Issues source accurately reports unavailable.

Generated history was seeded through the restricted runtime role into the existing demo organizations. Its overview reads 72 merged PRs in Demo One and exposes distinct included/excluded cohorts. Visual review inspected the actual seeded database on desktop and mobile; the mobile filters were collapsed into an accessible disclosure to bring analytical results into the first screen.

## Limits and next gate

- Cycle time includes draft and reopened wall-clock intervals. First approval measures historical timing, not current approval or authorization to merge.
- Missing/incomplete review evidence excludes timing samples rather than becoming zero. Provider pagination is not an immutable snapshot; coverage and bounds remain visible.
- The configured local App has Contents and Pull requests read access. Issues read access is absent, so live issue evidence remains unavailable until that permission is granted. Its current event subscriptions are Push and Pull request; enable Pull request review for immediate review refresh, and Issues when granting issue access. Existing manual sync reconciles reviews without that event subscription. Generated demo issue relationships and adapter fixtures verify the supported path.
- GitHub caps PR membership at 250 commits and commit file metadata at 3,000 files. General page/capacity limits are explicit partial coverage.
- Issue links require explicit same-repository provider references. Titles, branches and temporal proximity do not establish a relationship.
- Imports remain manual/webhook driven. Scheduled reconciliation, Actions/deployments, test reports, Sentry and automation are later milestones.

Phase 5 begins only after the user's next instruction.
