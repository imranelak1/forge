# ADR 009: Evidence-led data infrastructure growth

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

The requested roadmap includes dbt, Airflow, Kafka and ClickHouse, but installing every component at foundation time would obscure their purpose and slow local development.

## Decision

Use PostgreSQL operational queries and durable workers first. Phase 10 adds dbt's reproducible staging/dimension/fact/metric models and Airflow's scheduled dependency/retry management. Phase 11 Kafka requires measured stream replay/fan-out or queue pressure. Phase 12 ClickHouse requires measured analytical limits after PostgreSQL tuning. Defer either phase explicitly if its need is unproven.

## Alternatives and consequences

A full platform on day one adds failure modes without useful data. Avoiding all analytical tooling forever would make backfills and evolving historical metrics difficult. Preserve versioned events, source-grain facts and an analytics repository interface now, so later tools can enter without replacing auth or action transactions. Derived storage must preserve tenant constraints, deletion semantics and freshness.

## Verification and revisit

Use incremental/full-refresh parity, late-change fixtures, replay tests and capacity benchmarks. Record actual migration triggers in a new capacity ADR before adding the relevant runtime infrastructure.
