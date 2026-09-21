# ADR 008: Declarative rules and traceable external actions

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Forge must do more than display data, but an alert threshold alone is insufficient justification to claim a deployment was rolled back or a pipeline stopped.

## Decision

Rules are typed, versioned predicates over named metrics, baseline/quality gates and configured scopes. Store evaluations and evidence. Create deduplicated incidents and durable action requests atomically. Initial actions are HIGH alerts, advisory rollback-candidate flags and signed webhooks to administrator-configured pipeline receivers. Enablement is an audited admin operation; previews and historical replay do not produce external effects.

## Alternatives and consequences

Arbitrary scripts or SQL would make safety, isolation and reproducibility harder. Native rollback requires provider-specific target semantics and privileges absent from the MVP. A signed webhook creates a useful automation boundary but needs a receiver contract, SSRF/egress controls and idempotency. Delivery acceptance and confirmed business outcome remain different states.

## Verification and revisit

Test freshness/zero-baseline gates, cooldown, incident deduplication, disablement, malicious destinations and receiver ambiguity. Add native pipeline actions only through a new adapter/permission decision and explicit user scope.
