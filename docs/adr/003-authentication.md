# ADR 003: First-party authentication and server-owned sessions

Date: 2026-09-21. Status: Accepted; email/password scope implemented in Phase 2 on 2026-09-22. GitHub identity linking remains Phase 3.

## Context

Forge needs email/password access before integrations, and users may join several organizations or later link GitHub identities.

## Decision

Hash passwords with Argon2id. Use short-lived access JWTs and rotating hashed opaque refresh tokens in Secure HttpOnly cookies behind one browser origin. FastAPI owns sessions; Next.js forwards requests. Enforce CSRF/origin checks, current session validity and current membership. OAuth identities link to global users; GitHub identity does not grant tenant membership or repository integration access.

## Alternatives and consequences

Browser localStorage tokens increase exposure to injected scripts. Long-lived stateless JWTs delay revocation. Server-checked sessions cost a database lookup but provide prompt revocation and a clear audit path. A managed identity provider remains possible later, but would change the requested email/password implementation and introduce an external dependency now.

## Verification and revisit

Test token rotation/reuse, concurrent refresh behavior, logout/reset revocation, role changes, CSRF and identity-linking attacks. Revisit external identity providers for SSO requirements; do not weaken tenant authorization when adding them.
