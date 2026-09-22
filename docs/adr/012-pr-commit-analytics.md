# ADR 012: Evidence-backed pull request and commit analytics

Date: 2026-09-22. Status: Accepted for Phase 4 implementation.

## Decision

Calculate operational PR metrics in PostgreSQL over tenant-scoped imported records. Keep the metric definitions, evidence filters and exclusions consistent across summaries, trends and drill-down. No analytical warehouse or new scheduler is justified by this workload.

Use the same merged PR cohort for all three timing distributions: `merged_at >= from` and `merged_at < to`, in UTC. Cycle time is opening to merge, including drafts, closures and reopened intervals. Review waiting ends at the first submitted substantive review from a non-bot reviewer other than the author. Approval-to-merge starts at the first qualifying historical approval, not current merge authorization. Open PR age is a separate current queue measure.

Return mean, median, P75 and P95 using exact PostgreSQL distributions, together with the cohort size, eligible samples, exclusions and source coverage. A missing first review, unknown historical approval, incomplete review fetch or invalid timestamp sequence never becomes a zero-duration observation. Metric evidence uses the same eligibility predicates as the aggregate. A PR associated with several commits, or a commit associated with several PRs, contributes once at its own metric grain.

Persist reviews, lifecycle transitions, explicit PR/commit membership, merge-commit evidence, commit file metadata and available issue references under forced RLS and composite tenant/repository foreign keys. A source number or SHA is never sufficient authorization. Source URLs remain GitHub links constructed from verified repository identity.

Enrichment uses the existing durable PostgreSQL worker with bounded pages, retries, checkpoints and lease/access guards. Expose pending, incomplete and failed coverage. Preserve observed historical approvals when later dismissed, and disclose uncertainty when the provider only exposes a dismissed review whose earlier state was never observed. A newer PR snapshot invalidates stale enrichment coverage until reconciled.

The existing read permissions support PR reviews, timeline evidence and commit metadata. Issues need an additional read permission. Missing Issues permission reduces issue coverage explicitly without disabling PR/commit ingestion. Provider JSON may contain patch fields; drop them at the adapter boundary and never persist, log or display source patches.

## Demo data

Generated 90-day history belongs only to explicitly synthetic demo organizations and repositories. It uses the same normalized tables and SQL metric queries as real data. Synthetic source integrations remain disconnected and cannot issue GitHub requests. Seeding is idempotent and disabled in production. No generated record is added to the user's connected repository.

## Consequences and limits

The dashboard measures imported observations within the bounded history window. It cannot prove activity that GitHub no longer exposes or that permissions/pagination excluded. Draft-adjusted active time, reviewer productivity rankings, inferred causal relationships, Actions and deployment metrics are outside this phase. Historic first approval is an analytical observation, not permission to merge a PR now.

Provider caps and incomplete timestamps remain visible, including PR commit and commit-file limits. Live synchronization and the synthetic demo are separate validation paths. Later dbt/warehouse models must preserve these definitions or publish a separately versioned change.
