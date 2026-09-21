# Phase 0 review and handoff

**PHASE COMPLETE — Phase 0: Architecture and Modeling.**

Historical Phase 0 handoff. The user subsequently approved this architecture on 2026-09-21 and authorized Phase 1. The statements below record the state at the end of Phase 0; see [the current Phase 1 handoff](phase-1-review.md) for implementation status.

## What was built and why

A source-controlled documentation package specifies how Forge will turn connected engineering records into inspectable lifecycle evidence and auditable pipeline responses. It retains the requested stack and establishes tenant isolation, durable ingestion and clear metric semantics before coding begins.

The central decisions are:

1. A layered FastAPI modular monolith and Next.js web product, with PostgreSQL as the transactional and initial analytical store.
2. Organization-scoped resources, composite foreign keys, RBAC and RLS, including background and analytical work.
3. OAuth identity separate from GitHub App installation access; app-level webhook verification followed by server-side tenant resolution.
4. Durable inbox/jobs/outbox and idempotent processing. A worker starts in Phase 3; Phase 1 Compose remains frontend/backend/postgres only.
5. Typed lifecycle links plus separately labeled temporal candidates, with evidence and unresolved ambiguity preserved.
6. Versioned database metric definitions, freshness and denominator coverage. Initial error rate is errors per minute, not a fabricated request-failure percentage.
7. Declarative baseline rules, deduplicated alerts, advisory deployment flags and signed customer webhook actions. Delivery acceptance is separate from confirmed pipeline outcome.
8. dbt/Airflow in Phase 10; Kafka and ClickHouse require explicit approval and measured reasons before introduction.

## Files created

All 21 files are documentation:

| Files                                            | Purpose                                                                                         |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- |
| [README.md](../README.md)                        | Forge identity, status, documentation index and local review commands                           |
| [architecture.md](architecture.md)               | Blueprint, system/evolution diagrams, layers, proposed monorepo and product surfaces            |
| [data-model.md](data-model.md)                   | ER diagram, all requested core entities, supporting grains, constraints and migration ownership |
| [apis.md](apis.md)                               | Auth/RBAC, endpoint inventory by phase, request flow, pagination/filtering/sorting/errors       |
| [integrations.md](integrations.md)               | Source authorization, sync, signatures, retry-safe ingestion, Actions, JUnit and Sentry         |
| [pipelines.md](pipelines.md)                     | Processing diagram, event envelope, job leases, quality, correlations, anomalies and actions    |
| [analytics.md](analytics.md)                     | Metric definitions, example SQL designs, dbt model diagram, incremental and quality contracts   |
| [security-operations.md](security-operations.md) | Security boundaries, config, containers, logs, tests, generated demo and production readiness   |
| [roadmap.md](roadmap.md)                         | Milestone scopes, acceptance tests and approval gates through Phase 13                          |
| [adr/README.md](adr/README.md) and ADR 001–010   | Decision index and ten proposed decision records                                                |
| [phase-0-review.md](phase-0-review.md)           | This handoff and review checklist                                                               |

## Database and endpoint changes

**Database:** none. No database was started or altered. Logical entities, natural keys, indexes, RLS strategy and Alembic ownership are specified, but migrations are not created.

**Endpoints:** none implemented. The API inventory is a proposed `/api/v1` contract, with each route assigned to its milestone. Health routes will first appear in Phase 1.

**Infrastructure:** none provisioned. No application scaffolding, Docker Compose file, dependency installation, credentials or generated demo records were added. The initial workspace was empty and was not a Git repository; no commit or PR was created. Phase 1 will establish the development and CI workflow.

## Exact commands for this phase

Run these PowerShell commands to inspect the deliverable:

```powershell
Set-Location 'C:\Users\imrane\Desktop\project'
Get-Content .\README.md
Get-Content .\docs\architecture.md
Get-Content .\docs\data-model.md
Get-Content .\docs\apis.md
Get-Content .\docs\pipelines.md
Get-ChildItem .\docs\adr\*.md
```

Use a Markdown preview with Mermaid support for the system, ER, request, pipeline and analytical diagrams. There is no app to run or manually exercise yet. Do not run `docker compose up -d` in this phase: its required files are a Phase 1 deliverable.

Future Phase 1 startup contract, **not currently runnable**:

```powershell
Copy-Item .env.example .env
notepad .env
docker compose up -d
docker compose ps
```

The Phase 1 handoff must give the actual configured URLs, health requests, test commands and expected results. Later phases add their real manual-test instructions; this phase does not invent commands for nonexistent packages.

## Manual architecture review

1. Follow a proposed lifecycle from issue/PR to commit, workflow attempt, tests, deployment and error. Check that missing/ambiguous links stay explicit.
2. Follow one valid webhook through App signature, installation mapping, durable receipt, normalization and database evidence. Repeat mentally with a duplicate and a worker crash.
3. Trace an attempted cross-organization resource ID through membership, scoped queries and composite foreign keys/RLS.
4. Inspect one PR percentile and one CI success-rate definition, including cohort, exclusions, source records and empty-input result.
5. Inspect a Sentry spike with zero/missing baseline and verify it cannot claim a percentage, causation or a completed rollback.
6. Follow an enabled rule through incident/outbox creation and a webhook timeout; ensure the external result remains ambiguous until verified.
7. Confirm Phase 1 has only three services and later infrastructure has an explicit purpose and gate.

Documentation checks cover local link existence, Markdown fences, diagram structure and required deliverable coverage. Application, SQL execution, migration, container, security and performance tests are not applicable yet; their future acceptance criteria are documented. Diagrams must still be previewed in the chosen renderer; textual checks do not certify rendering or runtime behavior.

## Limitations and approval boundary

This is a buildable design, not an implemented SaaS or a production-readiness claim. Dependency versions, provider account capabilities, production sizing and hosting decisions are intentionally verified in their relevant phases. Sentry endpoint capabilities in particular remain a Phase 7 validation task.

Approval is requested because the original brief explicitly requires stopping after Phase 0 and waiting before Phase 1. The next authorized step, after approval, is the project foundation only: monorepo, Next.js, FastAPI, PostgreSQL, Alembic, three-service Compose, health endpoints and baseline checks.
