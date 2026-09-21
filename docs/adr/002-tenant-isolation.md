# ADR 002: Shared database with explicit tenant isolation

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Organization data crosses many joins, background jobs and analytical queries. A missing predicate or a valid ID from another organization must not expose or link customer data.

## Decision

Put `organization_id` on every tenant-owned row. Require verified membership/RBAC, scoped repositories, composite tenant foreign keys and PostgreSQL RLS with write checks. Runtime roles are non-owner/non-bypass. Set tenant context only within an authorized transaction. Global identity, membership discovery, app-webhook routing and queue claiming have narrow documented control-plane paths, not general cross-tenant access.

## Alternatives and consequences

Database-per-tenant increases isolation but complicates migrations and operations before there is an enterprise requirement. Application-only predicates are too easy to omit. RLS adds policy/testing cost and does not protect against a fully compromised trusted application role; it remains one layer of the security boundary. Analytical serving tables require the same policies as operational tables.

## Verification and revisit

Test cross-tenant reads/writes, nested joins, cursor tampering, workers and pooled context reset on PostgreSQL. Revisit dedicated databases for contractual isolation or noisy-neighbor requirements. See [PostgreSQL policy behavior](https://www.postgresql.org/docs/17/ddl-rowsecurity.html).
