# ADR 004: GitHub App authorization and source adapters

Date: 2026-09-21. Status: Proposed — pending Phase 0 approval.

## Context

User login and organization repository access have different lifetimes and scopes. Future providers must not force GitHub-specific identifiers into the entire domain model.

## Decision

Use OAuth for GitHub user identity and GitHub App installation credentials for selected-repository access. Bind an installation to one Forge organization initially. Verify webhooks, reconcile polling/backfill through the same normalizer, and map provider DTOs into internal entities with preserved source identity and coverage. Adapter contracts expose permissions and unavailable capabilities.

## Alternatives and consequences

Broad personal access tokens or OAuth repository scopes couple collection to a person's broad permissions and lifecycle. GitHub Apps offer installation-oriented controls, at the cost of app registration and installation management. Supporting multiple Forge organizations per installation is deferred because it complicates authorization and webhook fan-out. Sentry remains a separately mapped service/error source. [GitHub's App/OAuth comparison](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)

## Verification and revisit

Contract-test permissions, installation binding/revocation, exact webhook signatures, repository transfers and paginated history. Revisit shared installations only with a defined customer use case and a separate routing decision.
