# ADR 011: Verified GitHub App installations and resumable ingestion

Date: 2026-09-22. Status: Accepted for Phase 3 implementation.

## Decision

Keep social sign-in separate from repository authorization. An authenticated, verified Forge organization administrator starts GitHub App user authorization with one-use state, browser/session/organization binding and PKCE. GitHub's returned issuer is checked against `https://github.com/login/oauth` when present. A short-lived user token is encrypted using a purpose-derived key and bound to one authorization ID; binding consumes it. Installation tokens are minted when needed and are never stored.

Binding requires fresh provider proof that the app owns the installation and the authorizing user owns its personal account or is an active administrator of its GitHub organization. A mere repository reader cannot authorize ingestion of the installation's other repositories. Organization membership read permission is justified by this check. One installation belongs to one Forge organization; disconnecting does not silently make the source transferable.

Tenant payloads, repositories, sync runs, jobs, PRs, commits and normalized events use forced PostgreSQL RLS and composite tenant foreign keys. Global tables contain only installation routing, temporary session-bound authorization attempts, and minimal webhook deduplication receipts. A bounded security-definer function claims one job and returns routing/lease metadata. It exposes no event payload and has an explicit search path and runtime-only execute grant. All remaining worker queries run under transaction-local tenant context with active organization/source checks.

Each worker lease processes one provider page, then atomically persists upserts, counters, the checkpoint and job progress. Lease tokens and monotonically increasing fences reject stale workers. Retries have a finite per-page budget and respect rate-limit delays. The independent worker process is now justified by historical fetches and asynchronous webhooks; no broker, Redis or scheduler is introduced.

The single configured GitHub App has one fixed webhook endpoint. Its configured signing secret selects the app; no tenant ID from the body is trusted. Verified installation routing and repository selection determine tenant scope. HMAC verification precedes JSON parsing. Duplicate delivery IDs must have the same body digest and event; receipt and job writes commit together. Unsupported future event types are explicitly ignored. Access revocations are applied before acknowledgement, cancel matching inbox/sync work, and advance an access revision checked again before committing fetched data. Repository natural keys include their integration so reinstallations preserve separate source histories.

## Consequences and limits

Users must register/configure a GitHub App and expose a reachable webhook URL before live delivery can be verified. Phase 3 has bounded 90-day seed history and manual/webhook-driven reconciliation. Page cursors are resumable, but provider pagination is not a snapshot; overlapping reads and idempotent upserts mitigate concurrent updates without claiming an immutable point-in-time export. Default-branch history and provided push commits do not imply complete history of every branch. Analytics, review timing, Actions and deployments remain later milestones.

The API and worker share the constrained runtime DB role; worker discovery is a narrow function, not a bypass-RLS credential. Separate runtime roles may be added when deployment policy requires them. The worker receives no migration credentials, mail credentials, or social-login client secrets. Moving workloads to Airflow/Kafka still requires the later capacity/dependency gates.

## Verification

Provider transport tests validate fixed hosts, permissions, PKCE, token privacy and rate-limit handling. Real PostgreSQL tests cover account/session-bound installation authorization, cross-tenant access, atomic webhook deduplication, invalid signatures, replay, revocation, idempotent page processing, restart lease recovery, stale-worker fencing and checkpoint-preserving retries. Frontend tests cover the transport allowlist and functional integration/repository states. Live sandbox authorization requires the user's GitHub App configuration and remains separately reported.
