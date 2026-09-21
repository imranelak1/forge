# ADR 001: Modular monolith in a phased monorepo

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

Forge spans ingestion, analytics and automation but starts without proven scale or an established team. Distributed services would multiply deployment and consistency work before product behavior exists.

## Decision

Use Next.js/TypeScript for the web product and a Python/FastAPI modular monolith with PostgreSQL. Separate API, services, domain, repositories, integrations, analytics, automation and worker entrypoints. Keep UI, API, data jobs, infrastructure and documentation in the requested monorepo. A worker shares backend services and image but runs separately when Phase 3 creates expensive durable work.

## Alternatives and consequences

Microservices provide independent scaling but require network contracts and cross-service transaction handling prematurely. A single flat application is quicker initially but makes provider logic, analytics and authorization hard to test. Module interfaces retain a future extraction path without making every interface a remote service. Phase 1 has three Compose services only; frontend queries remain server-authorized and business logic does not move into route handlers.

## Verification and revisit

Check route/service boundaries in review and test use cases without HTTP. Revisit service extraction only with independently measured scaling, ownership or deployment needs.
