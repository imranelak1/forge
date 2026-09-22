# Integration architecture

Status: GitHub App authorization, repository catalog, PR/commit history sync and signed push/pull-request/installation webhook ingestion are implemented in Phase 3. See [setup and limits](github-setup.md). Actions, reviews, deployments, JUnit and Sentry below remain later milestones.

## Common adapter contract

Each source adapter implements connection validation, capability discovery, paginated history fetch, incremental changes, provider-to-domain mapping and health/permission reporting. Adapters return typed records and source checkpoints; application services own persistence and transactions. HTTP clients enforce bounded timeouts, retries with jitter, response-size limits and rate-limit handling. A 401/403 can mean revoked credentials or insufficient permissions; expose a reconnect/permission state instead of retrying indefinitely.

Use UTC source timestamps and opaque cursor/checkpoint storage. Track capabilities such as review history, workflow jobs, release mapping and exact error-user counts. Absence of a permission or a provider's retained history produces explicit partial coverage.

## GitHub identity versus repository authorization (Phase 3)

Use GitHub OAuth authorization for user sign-in/linking and a GitHub App installation for organization repository access. These are separate authorization decisions: signing in with GitHub does not connect every repository or create a Forge membership. The GitHub App OAuth user flow can supply identity; backend installation credentials perform repository sync. GitHub documents installation-level permissions and selected-repository control as reasons to prefer Apps for integrations. [GitHub comparison](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)

Installation binding requires an authenticated Forge admin, a one-use state tied to the target organization, and a server-side check that the authorizing GitHub identity owns the personal installation account or has active administrator membership in its GitHub organization. The app must own the installation, and current user access is checked again when binding. Initially one installation belongs to one Forge organization; supporting shared installations later requires an explicit mapping and routing ADR. Refresh permission/repository mappings on installation changes. Revocation suspends jobs and actions using that connection.

Phase 3 requests read-only repository metadata, contents and pull requests, plus organization members to verify source administration. Issues, Actions and deployment permissions are deferred until their collection phases. Subscribe to installation/repository changes for access reconciliation. Write permissions are not required for the initial outbound customer webhook action. The GitHub App private key and client secret remain server-side; short-lived installation tokens are encrypted if persisted and refreshed before expiry.

OAuth uses state, session/purpose binding, allowlisted redirects, and PKCE where supported by the chosen provider flow. Account linking requires an existing authenticated session or explicit account recovery proof. Never merge accounts solely by a returned email address. Phase 3 App authorization requires a verified Forge email and current owner/admin membership; social login has its own provider scopes and explicit account-linking policy.

## Historical and incremental synchronization

Connecting a repository creates a durable SyncRun and returns immediately. Phase 3 uses a fixed 90-day initial history window; configurability is a future extension. Enumerate repository metadata, issues/PRs, reviews and transitions, related commits and file summaries, workflow runs/attempts/jobs, deployments/statuses in resumable stages. Phase 3 ships the ingestion framework and repository/PR/commit seed sync; later phases add their datasets. Do not imply reviews, Actions or tests are available before their phase.

Use provider pagination and stable updated-time filters where available. Persist each accepted page with checkpoint advancement in one transaction. A page failure leaves the previous checkpoint intact. Overlap incremental time windows (initially 10 minutes) and upsert by natural key to catch late arrivals. For sources lacking updated-time filters, use bounded scans and scheduled reconciliation; never pretend a creation-time cursor captures all later updates. Re-fetch changed PR details/reviews and deployment statuses as needed.

Webhooks can race with backfill. Normalize immutable occurrences once; update projections only when source revision/time ordering is sufficient. When ordering is ambiguous, schedule an authoritative provider read instead of allowing an older payload to overwrite newer state. Record requested/completed coverage, source availability, counts, last success, next retry and per-stage errors. The UI shows queued/running/partial/succeeded/failed/canceled, without inventing a percentage when the total is unknown.

## Secure GitHub webhook intake

Validate `X-Hub-Signature-256` as HMAC-SHA256 over the exact raw body with constant-time comparison before parsing or enqueuing. The fixed `/api/v1/webhooks/github` endpoint uses the single configured GitHub App signing secret; verified installation routing determines the tenant. Require bounded body size and supported content type. [Signature verification](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)

The GitHub App has an app-level webhook URL, shared by its installations. After verifying the body, read its installation identity and use a restricted server-side lookup to find the tenant-owned Integration; validate any repository against that installation's authorized mapping. Never require a different App webhook URL per Forge organization or accept a tenant ID from the payload. Unknown/unbound installations receive an acknowledged ignored control event with minimal metadata; they cannot ingest tenant engineering data. The authenticated installation callback can reconcile early events by backfill. [GitHub App webhook configuration](https://docs.github.com/en/rest/apps/webhooks), [installation payload identity](https://docs.github.com/en/webhooks/webhook-events-and-payloads)

Persist the raw inbox record and normalization job atomically, then acknowledge 202. Duplicate deliveries return 200 with the original receipt and no second job. `X-GitHub-Delivery` supplies the dedup key; a redelivery retains that identifier. Reject a reused ID with a different body digest or event using a safe conflict response. Keep durable dedup metadata after payload expiry. GitHub recommends a prompt 2xx response and asynchronous processing; failed delivery recovery must also be planned. [Webhook delivery guidance](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks)

| Event                                          | Normalized work                                                            | Availability                          |
| ---------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------- |
| `push`                                         | Upsert referenced commits/ref changes; fetch missing details               | Phase 3 foundation, Phase 4 analytics |
| `pull_request`                                 | PR state and lifecycle transitions; fetch authoritative detail when needed | Phases 3–4                            |
| `pull_request_review`                          | Review/approval/dismissal history needed for timing coverage               | Phase 4                               |
| `issues` and issue/PR reference reconciliation | Issue lifecycle and explicit PR links                                      | Phase 4                               |
| `workflow_run`                                 | Attempt status, timing and jobs reconciliation                             | Phase 5                               |
| `deployment`                                   | Deployment identity, SHA, ref and environment                              | Phase 5                               |
| `deployment_status`                            | Immutable status transitions; projection reconciliation                    | Phase 5                               |
| installation/repository access events          | Suspend/reconcile source authorization                                     | Phase 3                               |

Authenticated but unsupported events/actions are explicitly recorded as ignored with a reason, not retried forever. Future-phase event types need not be subscribed before their handlers exist. Provider ping validates connectivity without creating engineering activity. Use reconciliation jobs and, where authorized, delivery-log redelivery tools to recover missed deliveries; do not rely on unlimited automatic provider retries.

## GitHub Actions and deployment collection (Phase 5)

Retain run ID plus attempt number and job records; reruns are additional attempts. Resolve full head SHA and provider-reported PR associations. Preserve queued/start/completion times and original conclusions. Fetch bounded failure metadata when permission allows; normalize common failure categories but retain `unknown` when evidence is absent. Do not scrape or retain full build logs by default because they can contain credentials.

Actions success is not proof of a deployment. Ingest GitHub deployment/status objects independently, and link a workflow only when the provider or a configured CI manifest supplies its identity. Environment names require explicit production classification.

## JUnit ingestion (Phase 6)

Support direct XML upload authenticated by a repository-scoped CI token initially. Associate with verified workflow run/attempt, commit SHA, report key and shard where supplied. Missing source parents can be reconciled later, but known cross-tenant or cross-repository IDs are rejected. Re-uploading identical content for the same report identity returns the original receipt. A corrected report explicitly supersedes its predecessor; do not silently count both.

Use a hardened XML parser with DTD/external-entity processing disabled and no network resolution. Initial limits: 10 MiB uncompressed body, 100,000 cases, bounded nesting and message lengths. Do not accept archives until decompression limits are implemented. Handle both `testsuite` and `testsuites`, nested suites, skipped cases, failure/error tags, duplicate test names, parameterization and retries. Preserve parse/quality warnings and compare declared counts to derived leaf counts.

Artifact retrieval from Actions can be added after direct upload, with provider-expiry and archive-size checks. CI success without an uploaded report does not imply tests passed.

## Sentry (Phase 7)

Connect a Sentry integration with least-privilege read access to configured projects, using an encrypted credential. Map each external project to a Forge service and explicit repository/environment mappings; preserve many-to-many service/repository relationships. Poll error groups, time-bucketed counts, release metadata and bounded event samples. Use group identity from Sentry for primary grouping; cross-group similarity is only a labeled suggestion.

Do not subtract lifetime group counters to synthesize exact interval counts or add repeated snapshots. Store the latest authoritative bucket result for its exact query scope. Fetch unique affected-user counts for the requested window/scope where supported; summing bucket or group uniques is invalid. Provider plan, retention, sampling and dimension support must be discovered and represented as coverage. Request-normalized error percentages remain unavailable without an independently collected request denominator.

Exact Sentry endpoints, granularity limits and authentication scopes will be verified against official API documentation and a test account in Phase 7. This blueprint deliberately does not promise a specific endpoint's availability or introduce a Sentry webhook signature contract before that choice.

## Future adapters

GitLab supplies alternate repository/CI identities; Jira/Linear supply issue references; Jenkins supplies workflow runs; SonarQube adds versioned quality observations; Playwright/Selenium can enter via JUnit first; AWS adds explicit deployment/resource observations. Each new adapter must define natural keys, timestamp semantics, permissions, coverage and contract fixtures before contributing to existing metrics.
