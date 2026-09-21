# ADR 006: Versioned database metrics with evidence

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Apparently simple metrics become misleading when CI reruns, missing reports, incomplete reviews or nonadditive Sentry counters are mixed together.

## Decision

Define metric grains, cohorts, numerator/denominator, exclusions, timezone, coverage and versions before implementing queries. Compute from stored records on the server, attach evidence drill-down, and represent unknown/insufficient data separately from zero. Start with exact PostgreSQL percentiles. Error rate initially means occurrences per minute; request-normalized percentages require a measured denominator.

## Alternatives and consequences

Hardcoded demo metrics and frontend calculations look fast but break traceability. Persisting only daily ratios or percentiles prevents valid wider-window aggregation. Retaining source-grain facts and additive counts costs storage but supports correct historical queries. Dismissed approvals, retries and missing dimensions are explicit limitations rather than silently cleaned away.

## Verification and revisit

Use hand-calculated fixtures and compare input IDs for every metric. Require operational-SQL/dbt parity before changing serving sources. Approximate analytics requires an explicit definition/version change and documented error bounds.
