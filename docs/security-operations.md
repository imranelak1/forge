# Security, operations and verification

Status: Phase 3 adds GitHub App account-administrator proof, encrypted short-lived authorization, signed webhook intake, tenant-scoped persistence and fenced worker jobs to the implemented identity/session/RBAC/RLS controls. See [ADR 011](adr/011-github-phase-3.md). Production deployment and remaining analytical/automation controls are still later requirements.

## Tenant boundary

Use three reinforcing controls: verified membership/RBAC in application services, organization-scoped repository queries, and PostgreSQL row-level security on organization-owned operational and analytical serving tables. Composite foreign keys prevent cross-tenant associations even when both records exist.

The application connects with a non-owner, non-superuser role without `BYPASSRLS`. Migrations run under a separate role. Enable and force RLS, with both read predicates and write checks requiring the current tenant. Set tenant context with transaction-local `set_config` after verifying membership; absent context denies access. Roll back/close transactions before returning pooled connections, and test reuse across tenants. PostgreSQL documents owner/superuser bypass behavior, so merely enabling policies is insufficient. [PostgreSQL row security](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)

User identity/session tables are global and accessible only to the auth repository. Membership discovery and organization bootstrap need restricted user-bound policies/functions; they must not permit arbitrary organization reads. The tenant-root organization table uses its own ID for its policy. Restricted queue claiming and webhook-binding lookups expose minimal routing metadata, then processing resumes under the derived tenant. Any security-definer function pins its search path, restricts execute grants, accepts validated arguments and is covered by negative tests.

RLS is defense against accidental unscoped SQL, not a defense against complete application credential compromise; a trusted service can set tenant context. Parameterized queries, minimum database privileges, controlled administrative roles and audited code paths remain necessary. Tenant-aware caching, file/report access, exports and worker tasks follow the same scope rules.

## Identity and secret handling

Use Argon2id with per-password salt and parameters at or above then-current OWASP guidance, calibrated on deployment hardware. Support long passwords without silent truncation, bounded input cost, generic login/reset responses and per-IP/account rate limits. Rehash on login when parameters change. [OWASP password storage guidance](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)

Store only hashes of refresh, invitation, verification, reset and machine tokens. Rotate refresh tokens transactionally; retain spent hashes to identify replay and revoke the family. The frontend serializes refresh requests across tabs (for example, a browser lock) because strict reuse detection can revoke a session when two concurrent refreshes reuse the same token. Test that behavior and document re-login recovery. Password reset revokes active sessions. Authorization checks read current membership/session state, not stale JWT role claims.

JWT signing keys, GitHub private keys, OAuth client secrets, webhook secrets, Sentry credentials, database credentials and encryption keys come from environment/secret mounts locally and a managed secret facility in production. `.env.example` contains names and explanations, never functioning secrets/default passwords. Startup fails if required secrets are absent or unsafe. Only explicitly public settings use `NEXT_PUBLIC_`.

Use authenticated encryption for provider credentials and retained sensitive raw payloads, with key ID/version for rotation. Keys are independent from database backups. Do not log Authorization, Cookie, provider token query strings, source code patches, or raw JUnit failure payloads. Strip/redact likely secrets from failure messages and cap retained bodies. Encrypt transport and production storage. A secret rotation procedure tests old/new overlap where required, then revokes old material.

## Input and egress boundaries

Require exact-byte webhook signatures; tenant source binding checks; replay keys; bounded JSON/XML; safe XML parsing; validated enums and identifiers; and parameterized SQL. Do not trust provider-controlled URLs for backend fetching: GitHub/Sentry hosts are configured adapter endpoints, and outbound automation uses validated destinations with restricted network egress. HTML/Markdown provider content is displayed as escaped text or through a sanitizing renderer.

Use same-origin browser requests, an explicit CORS allowlist when needed, Secure HttpOnly cookies, CSRF checks and security headers. Restrict destructive and integration/automation operations by role and record their outcomes. Signup/email delivery and authorization failures have bounded logs and rate limits. Organization deletion disables collection/actions before purging live data and analytics projections; backup copies expire according to the documented backup policy.

## Containers and environment configuration

Phase 1 Compose includes `frontend`, `backend`, `postgres`, plus a persistent database volume. Only necessary developer ports are published; production PostgreSQL is private. Use container healthchecks and a backend startup migration step serialized with a database lock. Readiness stays false until migrations finish and the database is reachable. Phase 1 development uses one backend instance; production later uses a separate release migration job before replicas start.

Phase 3 adds `worker` from the backend image because durable sync/webhook work now exists. No Redis is required. Phase 10 orchestration services belong in an explicit optional Compose profile/overlay, not the default Phase 1 stack. Kafka and ClickHouse are likewise absent until their approved phases. Use non-root images, pinned tested base/dependency versions, multi-stage frontend builds, and startup validation.

Planned configuration groups:

| Phase | Configuration                                                                                                                       |
| ----- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1     | Environment, public origin, internal API URL, PostgreSQL application/migration connection settings, log level                       |
| 2     | Independent `FORGE_AUTH_SECRET`, `FORGE_PUBLIC_ORIGIN`, mail adapter and SMTP settings; fixed JWT issuer/audience and cookie policy |
| 3     | GitHub App identifiers/private key, OAuth credentials/callback, webhook signing secret, worker concurrency and history limits       |
| 6     | Report size/case limits, CI token expiry policy                                                                                     |
| 7     | Sentry base URL, encrypted per-tenant credentials, polling/retention defaults                                                       |
| 9     | Egress allowlist, action signing configuration, delivery limits                                                                     |

Exact variable names and dependency versions are Phase 1/feature deliverables. Do not add unused mandatory secrets before the feature needs them.

## Logging and observability

Emit structured JSON logs with UTC timestamp, level, service, environment, request/trace ID, tenant ID when authorized, safe actor ID, operation, duration and result. Ingestion logs add integration/source delivery/event/job/attempt IDs; automation logs add rule version, evaluation, execution and attempt IDs. Avoid email addresses and high-cardinality payload fields unless needed for a restricted audit record.

Operational signals: request latency/error rate, database pool saturation, job backlog/oldest age, expired leases, ingestion latency, source freshness, sync completion/errors, rate-limit waits, quarantine volume, rule evaluation lag and outbound acceptance/failure/unknown counts. Alerting about Forge itself must distinguish provider outages from tenant configuration problems. Prometheus/Grafana are future consumers; do not deploy them merely to complete the diagram.

Audit logs capture member/role changes, integration credentials/configuration changes, rule versions/enablement, incident changes, replay mode, outbound delivery and organization deletion. Runtime roles cannot silently update audit history. Health endpoints return safe summaries; metrics/admin endpoints are private or authenticated.

## Testing strategy

Tests land with each feature, and production-like database behavior is tested on PostgreSQL rather than replaced by SQLite.

| Suite                         | Required evidence                                                                                                                                                      |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend unit                  | Role policies, transitions, rule predicates, zero-baseline handling, flakiness calculations, provider mapping and redaction                                            |
| Backend integration           | Alembic on clean/upgraded DB, tenant read/write isolation, composite FK rejection, pooled context reset, session rotation/revocation, concurrent last-owner protection |
| Ingestion contracts           | Sanitized provider fixtures, exact signature bytes, duplicate and changed-payload delivery, out-of-order input, pagination retry, missing parents, revoked permissions |
| Worker/automation integration | Crash before/after commit, expired lease fencing, replay without side effects, stable remote idempotency key, destination security and partial failure                 |
| Analytics/data                | Hand-calculated cohorts/percentiles/ratios, no fan-out, test retry policy, missing data, nonadditive user counts, late changes and full/incremental parity             |
| Frontend component            | Loading/error/empty/stale states, role-gated controls, filter/query keys, keyboard accessibility and accurate metric formatting                                        |
| End-to-end                    | Register/login, create/switch organizations, connect mocked source, sync, inspect contributing records, configure/preview action, assert cross-tenant denial           |
| Build/security                | Python lint/type checks, frontend lint/typecheck/build, dependency/secret scanning, container startup smoke and migration checks                                       |

Phase 1 introduces the test harness and foundation checks. Later phases add their suites as behavior exists. CI must not depend on live provider credentials; use fixtures/fake provider servers. Optional sandbox integration checks use isolated credentials and explicit test targets.

## Demo environment

Build an opt-in deterministic seed command as models become available. It creates at least two isolated organizations and distinct test users/roles, repositories, and 90 days of synthetic history. Include realistic weekdays, long-tail PR reviews, CI reruns, test flips, deployment/release links, an error spike, missing data, and a failed action receipt. Label the organization and UI as synthetic demo data.

Seed through validated ingestion/domain paths where practical, populate real tables, and query them through the same API as connected data. Never inject dashboard JSON or hardcoded metric results. Seed credentials are provided by the operator or randomly generated for local display; no permanent shared login/password. Demo outbound actions route to a local test receiver or remain disabled and must never send to real pipeline endpoints. The seed is idempotent and is rejected in production unless an explicit isolated demo deployment is configured.

History grows with milestones: Phase 2 users/tenants, Phase 4 PR/commit history, Phase 5 CI/deployments, Phase 6 tests, Phase 7 errors, Phase 9 evaluation/action history. Thus Phase 1 does not claim to contain months of data for unimplemented schemas.

## Production readiness (Phase 13)

Use a selected hosting target with TLS, private database networking, managed PostgreSQL backups, secret management, immutable image releases and controlled migrations. Target initial RPO of 24 hours and RTO of 4 hours, then validate with restore drills and documented costs; these are provisional requirements, not achieved guarantees. Enable point-in-time recovery if the required data-loss budget becomes stricter.

Document backup encryption and key recovery, restoration, credential revocation/rotation, stuck jobs, failed sync recovery, safe replay, outbound ambiguity, and emergency rule disablement. Test restoration and compare tenant counts/checksums. Define data retention/deletion including backup expiry. Release uses backward-compatible expand/backfill/contract changes and application rollback only while the database remains compatible. Destructive database downgrade is not the default rollback procedure.

Production acceptance requires measured load/freshness targets, tenant penetration tests, dependency review, restore evidence and runbooks. Docker Compose is the local workflow; production platform selection stays open until Phase 13 requirements are known.
