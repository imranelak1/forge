# ADR 007: Separate explicit links from temporal correlations

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

The lifecycle is a graph: a commit can appear in multiple PRs, deployments can lack workflow metadata, and several deployments can precede an error spike.

## Decision

Keep authoritative typed foreign keys/junctions for known provider links. Store candidate correlations with tenant-validated endpoints, evidence, method version and ambiguity. Display both classes separately. Never equate release association with defect causation, and never use a temporal candidate to authorize an action target.

## Alternatives and consequences

A single forced linear chain is easy to display but invents certainty. A graph database is unnecessary for the initial bounded lifecycle traversals. PostgreSQL typed relations plus an evidence-link index preserve correctness and flexibility; polymorphic candidate endpoints require service validation and integrity audits.

## Verification and revisit

Test squash/rebase, shared commits, missing reports, overlapping deployments, stale source data and cross-tenant endpoints. Revisit a graph engine only after measured traversal needs exceed the relational approach.
