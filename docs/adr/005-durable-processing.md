# ADR 005: PostgreSQL inbox, durable jobs and action outbox

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Accepted webhooks must survive process crashes, source retries and partial syncs. External actions can time out after a receiver has already acted.

## Decision

Commit inbox/job records before acknowledging acceptance. Run leased jobs from a separate Python worker using unique dedup keys, heartbeat/fencing and idempotent domain upserts. Commit action requests with incident state in a transactional outbox. Deliver at least once using stable receiver idempotency keys; expose ambiguous outcomes.

## Alternatives and consequences

In-process background callbacks cannot provide the chosen durability contract. A broker would add operational work before needed. PostgreSQL provides transactional acceptance and a manageable initial queue but competes with application queries, so queue age, contention and throughput must be measured. No design claims exactly-once external side effects; receivers must cooperate.

## Verification and revisit

Kill workers at transaction boundaries, expire leases, replay deliveries and simulate a receiver timeout after acceptance. Revisit Kafka when independent consumer replay/fan-out or measured throughput warrants it, retaining the transactional outbox boundary.
