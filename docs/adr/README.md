# Architecture Decision Records

All records are **Proposed — pending Phase 0 approval**, dated 2026-09-21. Approval changes their status to Accepted; implementation still follows the separately approved milestones. Later changes should supersede a record with a new ADR rather than erase its reasoning.

| ADR                                   | Decision                                                      |
| ------------------------------------- | ------------------------------------------------------------- |
| [001](001-modular-monolith.md)        | Modular monolith and phase-scoped monorepo                    |
| [002](002-tenant-isolation.md)        | Shared PostgreSQL with layered tenant isolation               |
| [003](003-authentication.md)          | First-party sessions and separate provider identity           |
| [004](004-provider-integration.md)    | GitHub App access and provider adapter contracts              |
| [005](005-durable-processing.md)      | PostgreSQL inbox/jobs/outbox and at-least-once processing     |
| [006](006-metric-contracts.md)        | Database-backed versioned metrics and explicit missing data   |
| [007](007-lifecycle-evidence.md)      | Typed lifecycle links and separate temporal candidates        |
| [008](008-automation.md)              | Declarative rules and auditable signed webhook actions        |
| [009](009-data-platform-evolution.md) | dbt/Airflow first; Kafka/ClickHouse only after evidence       |
| [010](010-delivery-and-demo.md)       | Alembic-owned schema, incremental delivery and synthetic demo |

The detailed contracts are maintained in the main documents linked from the [repository README](../../README.md). ADRs explain why those contracts were chosen.
