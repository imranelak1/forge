# ADR 013: Actions attempts and explicit deployment evidence

Date: 2026-09-22. Status: Accepted for Phase 5 implementation.

## Decision

Extend the existing PostgreSQL worker and tenant-scoped operational query layer with GitHub Actions attempts, jobs and independent deployment/status history. A provider run ID plus attempt number identifies a workflow attempt; reruns never replace earlier attempts. Preserve original provider statuses and conclusions and link only explicit same-repository PR associations and full commit SHAs. Successful CI alone never establishes a deployment.

Decisive completed attempts are success, failure, timed_out, startup_failure and action_required. Calculate success/failure fractions from the same eligible completion cohort; return excluded conclusions and missing timestamp coverage. Duration and queue distributions have their own valid-timestamp eligibility and exact PostgreSQL percentiles. Group repeated failures by provider workflow identity, with observed job/step evidence and unknown cause when the provider does not establish one. Do not download build logs or infer root cause from a step name.

GitHub's workflow attempt response does not supply a completion timestamp; job responses do. Derive the attempt's observed completion only when a complete terminal job set provides valid completion evidence. Report `completion_source=jobs` and explain that this is the last-job-completion proxy. Missing evidence remains null and cannot be assigned an invented completion window. A rerun's original run creation time is not its queue start: queue timing remains unavailable without an attempt-specific queued timestamp. [Workflow runs](https://docs.github.com/en/rest/actions/workflow-runs), [workflow jobs](https://docs.github.com/en/rest/actions/workflow-jobs)

Count a deployment once at its first successful status in the UTC window. Require complete status history to establish first success; subsequent success or inactive statuses do not create additional deployments. Preserve status history and current state separately. Production scope uses an explicit provider production-environment flag or an audited repository/environment classification set by a verified manager. Missing classification is unknown; Forge does not infer production from environment names. [Deployments](https://docs.github.com/en/rest/deployments/deployments), [deployment statuses](https://docs.github.com/en/rest/deployments/statuses)

Request Actions and Deployments read permissions only when the installation grants them. Missing access reduces that source's coverage without interrupting PR/commit ingestion. Reconcile from paginated provider reads through the existing fenced jobs, with bounded attempts/pages and atomic evidence/checkpoint writes. Webhook deliveries schedule authoritative reconciliation; they are not an ordering authority over newer source state.

## Consequences and limits

All added engineering tables force tenant RLS and composite same-repository references. Analytics reads use coherent database snapshots, not synchronous provider calls. Interface results expose source permissions, sample counts, timestamp provenance, gaps and query windows. The opt-in local demo extends the existing generated PR/commit history with stable attempt/deployment facts under its existing anchor; no customer records or live source jobs are created by seeding.

Source pagination and retention are bounded and are not immutable snapshots. Unfiltered retained workflow catalogs avoid GitHub's 1,000-result filtered search ceiling; each stage remains bounded at 100 pages and each run at 100 discovered attempts. Hitting a bound remains partial coverage. A bounded local reconciliation job repairs explicit PR/full-SHA links after their parent facts arrive, without refetching CI or inventing associations. Webhooks and manual synchronization supply refreshes; scheduled polling, artifact/test-report ingestion, release/error correlation and deployment automation remain later phases.
