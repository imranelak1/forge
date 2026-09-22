# Milestones and approval gates

Work one phase at a time. Each phase begins with its scope and ends with changed files, migrations, routes, checks, exact local/manual-test commands, known limitations and a **PHASE COMPLETE** summary. Stop for the user's next instruction at every gate.

Current next implementation phase: **Phase 6 — Test intelligence**. The six [planned product expansion tracks](product-expansion.md) add product direction and dependency milestones only; they do not reorder Phases 0–13 or authorize implementation at an existing gate.

## Phase 0 — Architecture and modeling

Deliver the Forge blueprint, diagrams, entity/API/pipeline/analytical models, security/operations strategy and ADRs. No application code, migrations, infrastructure provisioning or dependency installation. Approval accepts the direction; individual integration permissions and production sizing are verified during their phases.

## Phase 1 — Project foundation

Create the monorepo, Next.js/TypeScript application shell, FastAPI layered package, PostgreSQL access, Alembic baseline, formatting/check tooling, test harness, CI and Dockerfiles. Compose has frontend, backend and postgres only. No fake dashboard metrics or login controls that pretend to authenticate.

Acceptance: copy/configure `.env`, run `docker compose up -d`, reach the application foundation page and API live/ready endpoints, verify persistent DB storage and clean migration startup, pass backend/frontend build and smoke tests. No provider secrets required. Pin supported versions and check official compatibility when implementing.

## Phase 2 — Authentication and SaaS foundation

Introduce users, organizations, memberships/invitations, sessions, one-use identity tokens and auditing with migrations and RLS. Implement email/password auth, rotating tokens, CSRF, verification/reset delivery adapter, organization switching and RBAC. Seed isolated demo users/organizations.

Acceptance: register/login/logout/reset, create organization, invite matching verified user, revoke membership/session and prove immediate denial. Cross-tenant read/write and pooled-connection isolation tests pass. Passwords/tokens are not stored in plaintext. No engineering metrics yet.

## Phase 3 — GitHub integration

Implementation delivered; see [Phase 3 handoff](phase-3-review.md). The private GitHub App has since been connected, its signed webhook delivered successfully and one explicitly selected repository imported. Automated regression validation uses isolated provider fixtures.

Add GitHub OAuth identity, installation binding, repository catalog, inbox/events/jobs, worker, sync runs/cursors and signed webhook ingress. Create minimal PR/commit persistence needed for history sync; analytic extensions arrive in Phase 4. Migrate every new table. Connect only repositories authorized by the verified installation.

Acceptance: connect a sandbox repository, backfill resumably, inspect real sync states; duplicate webhook does not duplicate records, bad signature/source mapping fails, worker restart resumes durable work. Frontend/backend/postgres remain the base stack; worker is added now for a concrete workload. Unsupported future events are not advertised as processed.

## Phase 4 — Pull request and commit analytics

Implementation and validation are recorded in [Phase 4 handoff](phase-4-review.md). Scope: review/transition/file/issue relations, cycle/review/approval-to-merge metrics and traceable drill-down; database-backed PR sections of the overview and isolated 90-day generated PR history.

Acceptance: hand-calculated mean/median/P75/P95 fixtures match queries; missing approvals/reviews have explicit coverage; reopened/squashed/multi-PR commits behave as documented. All cross-tenant joins are rejected.

## Phase 5 — CI/CD intelligence

Implementation and validation are recorded in [Phase 5 handoff](phase-5-review.md).

Ingest Actions workflow attempts/jobs and deployment/status history. Implement CI success/failure, duration and trends, frequent failure summaries, deployment counts and environment classification. Seed realistic run attempts and deployment links.

Acceptance: retries are distinct attempts; excluded conclusions visible; duplicate deployment statuses do not inflate counts; successful workflow alone never creates an invented deployment.

## Phase 6 — Test intelligence

Implement scoped CI tokens, hardened JUnit upload/parser, test identity/suite/execution persistence, quality warnings, pass rate and configurable potential-flakiness evidence. Seed report fixtures/history.

Acceptance: nested/duplicate/retried/parameterized/skipped cases handled; malformed/oversized/entity-expansion input rejected; same report replay does not inflate totals; selected retry denominator and sample thresholds tested.

## Phase 7 — Sentry integration

Verify provider endpoints/scopes; add service/repository/environment/release mappings, error groups, authoritative time buckets, affected-user query aggregates and bounded samples. Implement production error trends with freshness/coverage. Seed generated error history through real data paths.

Acceptance: overlapping polls replace buckets, revoked credentials surface, unsupported granularity/user counts remain unavailable, error rates show correct units, release links are traceable.

## Phase 8 — Correlation engine

Resolve explicit typed links and persist labeled temporal candidates across the lifecycle. Provide a repository timeline and evidence details with ambiguous candidates/missing links.

Acceptance: full SHA/release mappings establish known associations; overlapping deployments remain ambiguous; temporal proximity never claims defect causality or chooses an action target.

## Phase 9 — Alerts and pipeline automation

Implement typed/versioned rules, baseline evaluation, preview, evidence, incidents, advisory deployment flags, configured destinations, durable action outbox and retry history. Complete the engineering overview and demo scenario.

Acceptance: replay and late data do not double-fire actions; missing data/zero baseline handled; rule disablement prevents unsent work; signed mock receiver deduplicates repeated delivery; UI distinguishes requested, accepted, confirmed, failed and unknown. No native rollback execution.

## Phase 10 — dbt and Airflow pipelines

Add dbt staging/dimensions/bridges/facts/metric models, data tests and freshness gates. Add Airflow for scheduled sync/reconciliation/backfill/dbt runs with isolated configuration and explicit scheduler ownership. Preserve tenant isolation in source and serving relations.

Acceptance: incremental/full rebuild parity, late-update/deletion propagation, metric parity with operational SQL, RLS preservation after materialization, safe retry of failed DAG tasks, and no duplicate worker/Airflow schedule ownership. Document why scheduled dependencies now justify orchestration.

## Phase 11 — Kafka integration

Begin only after measuring a need such as multiple independent consumers, durable stream replay or sustained queue contention. Write a capacity ADR first. If evidence does not justify Kafka, explicitly defer this phase rather than add idle infrastructure.

When approved: add transactional event relay, versioned topics, tenant/aggregate partition keys, idempotent consumers, offset/replay and dead-letter operations. Acceptance includes producer outage recovery, duplicates, consumer lag and tenant-isolation tests; PostgreSQL remains the transactional source of truth.

## Phase 12 — ClickHouse integration

Begin only after PostgreSQL indexing/rollup improvements fail the documented analytical targets at the measured volume. If unjustified, record deferral. When approved, add analytical projections and an `AnalyticsRepository` implementation; keep operational state and permissions in PostgreSQL.

Acceptance: metric/window/precision parity, ingestion watermark visibility, deletion propagation, rebuild/reconciliation, tenant tests and documented query-cost improvement. Do not migrate authentication or action outbox tables.

## Phase 13 — Production deployment

Choose deployment target and resource budgets, provision secrets/TLS/private DB/backups, perform controlled release migrations, and finalize observability/runbooks. Deliver a documented opt-in demo deployment separate from customer data.

Acceptance: CI builds/scans immutable images, deploy smoke tests pass, restore drill meets agreed recovery objectives, load/freshness targets measured, security/tenant checks pass and limitations are published. Do not claim production readiness merely because Compose boots.

## Choices deferred to the relevant phase

Dependency/runtime versions and development ports belong to Phase 1; transactional email provider to Phase 2; GitHub App registration/scopes to Phase 3; supported JUnit dialect fixtures to Phase 6; Sentry account capability/retention to Phase 7; customer halt-receiver contract to Phase 9; infrastructure capacity gates to Phases 10–12; hosting, recovery budget and deployment region to Phase 13. None blocks review of this Phase 0 design.

## Planned product tracks and dependency milestones

The [product expansion plan](product-expansion.md) defines audiences, evidence limits, small MVPs and acceptance/success signals for six directions. They remain planned; each pilot needs a bounded scope decision at a gate.

| Milestone                 | Planned work                                                                                        | Dependency and release boundary                                                                                                                                                                                                      |
| ------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Public-data pilot         | Shareable OSS health pages, contributor guidance and free maintainer draft tools                    | Build on Phases 4–6 after Phase 6. First establish a separate public catalog, publication consent and reliable historical contributor coverage. Outbound maintainer nudges wait for Phase 9.                                         |
| Personal pilot            | Private engineering profile and year-in-review owned by the individual                              | Build on Phases 2–5 after the public-data foundation; require separate personal consent, revocation and authorization, with no employer/admin access. Annual comparisons require sufficient history.                                 |
| Side-project pilot        | Free monitoring for one or two projects, post-deployment watch and optional team adoption           | Propose after Phases 7–9. Require explicit deployment/error mappings and quiet, opt-in alerts; CI success never substitutes for deployment evidence.                                                                                 |
| Benchmark pilot           | Opt-in, anonymized aggregate comparisons by language/team-size bands                                | Require stable covered metrics, enough independent opt-in participants, cohort suppression and privacy validation. Public-repository status does not imply consent. Phase 10 is optional support, not a prerequisite for collection. |
| Public production release | Approved pilots with enforceable quotas, deletion, visibility-change handling and operating budgets | Phase 13 operational acceptance applies before production launch. Phases 11–12 remain conditional on measured need.                                                                                                                  |

Prioritize public usefulness and maintainer help, then personal reflection, then monitoring; publish benchmarks only once participation and privacy requirements are met. These milestones are dependency checks, not extra numbered phases or an instruction to start work now.
