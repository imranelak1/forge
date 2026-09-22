# Architecture Decision Records

These decisions were drafted on 2026-09-21 for the approved architecture. Implementation follows the separately authorized milestones: ADRs 002 and 003 now record the completed Phase 2 tenant/identity scope; ADR 011 records Phase 3 provider/pipeline implementation; analytical decisions remain future implementation. Later changes should supersede a record with a new ADR rather than erase its reasoning.

| ADR                                   | Decision                                                         |
| ------------------------------------- | ---------------------------------------------------------------- |
| [001](001-modular-monolith.md)        | Modular monolith and phase-scoped monorepo                       |
| [002](002-tenant-isolation.md)        | Shared PostgreSQL with layered tenant isolation                  |
| [003](003-authentication.md)          | First-party sessions and separate provider identity              |
| [004](004-provider-integration.md)    | GitHub App access and provider adapter contracts                 |
| [005](005-durable-processing.md)      | PostgreSQL inbox/jobs/outbox and at-least-once processing        |
| [006](006-metric-contracts.md)        | Database-backed versioned metrics and explicit missing data      |
| [007](007-lifecycle-evidence.md)      | Typed lifecycle links and separate temporal candidates           |
| [008](008-automation.md)              | Declarative rules and auditable signed webhook actions           |
| [009](009-data-platform-evolution.md) | dbt/Airflow first; Kafka/ClickHouse only after evidence          |
| [011](011-github-phase-3.md)          | Verified GitHub installations, tenant routing and resumable jobs |
| [010](010-delivery-and-demo.md)       | Alembic-owned schema, incremental delivery and synthetic demo    |

The detailed contracts are maintained in the main documents linked from the [repository README](../../README.md). ADRs explain why those contracts were chosen.
