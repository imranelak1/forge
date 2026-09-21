# ADR 010: Migration-owned schemas and honest incremental demos

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Forge should be locally bootable and demonstrate months of activity while remaining honest about what each phase actually implements.

## Decision

Alembic owns every operational schema change. dbt later owns derived models under explicit tenant-policy rules. Compose starts with only frontend/backend/postgres. Each milestone includes relevant tests, documentation and a completion/approval gate. Demo history is deterministic synthetic data inserted into real tenant-scoped tables, prominently labeled and opt-in; credentials are operator-supplied or generated, and external effects are disabled or directed to a test receiver.

## Alternatives and consequences

Runtime schema auto-creation hides upgrades, and manually edited production tables cannot be reproduced. Hardcoded dashboard values make a demo attractive but untestable. Full seeded history therefore arrives progressively with implemented models; early phases show real empty/unavailable states. Production readiness is earned by migration, security, load and recovery checks, not a visual demo.

## Verification and revisit

Test clean/upgrade migrations, idempotent seed reruns, two-tenant isolation and production seed guards. Maintain a source-controlled environment example with no usable secrets. Revisit deployment topology in Phase 13 without weakening the local startup contract.
