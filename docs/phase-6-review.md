# Phase 6: Test intelligence

Scope: authenticated JUnit ingestion, durable parsing, test identities and execution history, SQL-backed pass rates, configurable potential-flakiness evidence, repository upload credentials and generated demonstration reports. Phase 7 remains the next implementation gate.

## Delivered behavior

Verified owners/admins can create expiring repository-scoped CI credentials, see safe token metadata and revoke access. Credentials are revealed once; stored hashes grant upload permission only. Raw XML goes directly to the backend with a machine bearer credential. User sessions and the browser proxy do not accept machine uploads.

The existing PostgreSQL queue dispatches report work. The worker rechecks repository authorization, token validity and its lease before storing suites, identities and executions atomically. Pending XML is encrypted, expires after one day and is cleared on terminal processing. Revocation fences pending jobs. Duplicate uploads return the existing receipt; an explicit correction replaces the previous report in metrics only after successful processing.

The bounded parser handles nested suites, parameterized names, skipped outcomes, failures/errors and explicit Surefire retries. Duplicate names remain distinguishable and are excluded from historical flakiness attribution when identity is ambiguous. DTDs/entities, malformed input and structural limits are enforced. Failure messages are bounded to 2,048 characters; captured output and properties are not retained. Declared-count mismatches and reduced-quality evidence remain visible.

Pass rate uses final retry outcomes from non-superseded reports for the latest completed workflow attempt, with skipped cases outside the denominator. PostgreSQL computes counts and daily cohorts. Flakiness uses a separate final-outcome sequence across completed attempts, partitioned by test, branch, environment, report key and shard. Results expose policy version, eligible samples, failure fraction, transitions and same-SHA retry reversals. These are investigation candidates, not diagnoses.

The new workspace pages support report/suite/case inspection, failure messages, execution histories, filters, pagination, coverage, policy editing and once-only token handling. No-report states point to the upload guide. The approved landing and its GIF remain unchanged.

## Files, schema and routes

| Area              | Main files                                                                                                                                   |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Migration         | `apps/api/migrations/versions/0008_test_reports.py`                                                                                          |
| Normalization     | `apps/api/src/forge/integrations/junit.py` and JUnit fixtures/tests                                                                          |
| Intake and worker | `apps/api/src/forge/{domain,repositories,services,api/v1,workers}/tests.py`; existing worker/main wiring                                     |
| Analytics         | `apps/api/src/forge/{repositories,services,api/v1}/test_analytics.py`                                                                        |
| Demonstration     | `domain/demo_tests.py`, `repositories/demo.py`, `seed.py`, demo regression tests                                                             |
| Workspace         | `apps/web/src/features/test-intelligence/`, `/app/tests` routes, navigation, overview link, proxy and guide                                  |
| Contracts         | [ADR 014](adr/014-test-intelligence.md), [JUnit setup](junit-setup.md), [API](apis.md), [metrics](analytics.md), [data model](data-model.md) |

Migration `0008_test_reports` follows `0007_cicd`. It adds `service_tokens`, `test_policies`, `test_reports`, `test_suites`, `test_identities` and `test_executions`, each with forced tenant RLS and composite references. Jobs gain a report kind/reference. A bounded database maintenance function clears expired/canceled payloads without returning tenant contents. No additional service or infrastructure dependency is introduced.

Routes below use `/api/v1/organizations/{organization}`:

- `GET /metrics/tests`, `/test-runs`, `/test-runs/{id}`, `/test-runs/{id}/suites`, `/test-runs/{id}/cases`, `/tests`, `/tests/{id}/history`.
- `GET, PATCH /repositories/{id}/test-policy`.
- `GET, POST /repositories/{id}/service-tokens`; `DELETE /service-tokens/{id}`.
- Machine-only `POST /repositories/{id}/test-reports` returns HTTP 202 with the receipt.

Browser routes are `/app/tests`, `/app/tests/reports/{id}`, `/app/tests/cases/{id}` and `/app/tests/settings?repository={id}`.

## Run and inspect

From the repository root, after the existing `.env` is configured:

```powershell
docker compose up -d --build --wait --wait-timeout 180
docker compose exec -T backend python -m forge.seed
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

The seed preserves existing demo passwords and anchors. Demo One now has 136 workflow attempts, 36 deployments and 30 reports with 278 stored executions; Demo Two has 68 attempts, 18 deployments and 15 reports with 139 executions. Only designated synthetic organizations are seeded. Reports pass through the same parser and persistence helper as uploads.

1. Sign in to a generated demo account and open **Tests**. Inspect pass-rate samples, missing-report coverage and the potential-flakiness candidates.
2. Open a report, inspect its nested suites, retries and quality warnings, then follow a test into execution history. Superseded reports stay inspectable.
3. Open **Report uploads and policy**, choose a repository and edit the thresholds as a verified manager. Demo repositories permit policy inspection/editing but cannot issue upload credentials.
4. For a selected live repository, import its exact Actions run/attempt, create a CI token and send a real XML report using the [documented curl command](junit-setup.md#send-uncompressed-xml). Refresh after processing. Replay the same bytes to observe the same receipt, or explicitly supersede a report to correct it.
5. Revoke the token and verify new uploads are denied. Completed history remains available to organization members.

## Validation

The isolated PostgreSQL suite passes **372 backend tests**, including parser limits, hand-calculated metric cohorts, duplicate/corrected reports, token and repository revocation, machine/user authentication separation, RLS/composite references, and demo replay. Ruff and strict mypy pass. Frontend unit checks pass **199 tests**, including 40 new test-intelligence cases. The production Compose stack builds and all four services are healthy.

The complete desktop/mobile browser regression suite passes **78 checks**, including ten new flows for report/history navigation, policy and token handling, viewer restrictions and organization switching, retryable errors and empty states. Actual signed-in demo captures cover the four new surfaces at desktop and mobile sizes, with no browser errors or page overflow. The final independent UI and backend reviews found no blockers. Frontend lint, type checks, formatting, configuration checks and the dependency audit also pass.

## Known limits

- The exact provider workflow run and attempt must already be imported. Phase 6 rejects unknown parents instead of retaining unverified links for later reconciliation.
- The API accepts direct uncompressed XML only. GitHub artifact retrieval, archives, multipart uploads and broader retry dialects remain unsupported.
- Report coverage is limited to uploaded artifacts. There is no expected-shard manifest, and missing reports never imply zero failures or passing tests.
- Workflow completion can use the existing last-job-completion proxy. Missing completion stays outside timed test metrics; receipt time is not substituted into that denominator.
- Ambiguous identities are excluded from flakiness attribution; missing branch/environment or fallback identity reduces confidence. Thresholds identify evidence to inspect, not a confirmed defect.
- Raw payload expiry cleanup requires the worker to run. Normalized evidence remains retained; comprehensive production retention/backup operations remain a later phase.
- Hosted CI requires a reachable authorized API origin. The local GitHub webhook tunnel accepts webhook deliveries only and cannot receive JUnit uploads. No public application deployment was provisioned.

**PHASE COMPLETE.** Phase 6 is implemented and validated. Sentry integration is Phase 7 and is not started here.
