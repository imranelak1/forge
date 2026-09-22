# Phase 2 — Authentication and SaaS foundation

Date: 2026-09-22. Scope: accounts, sessions, organization tenancy and membership. The approved public landing is preserved. GitHub integration is the next phase.

## Delivered behavior

Users can register, sign in, verify their address, reset a password and sign out. Protected `/app` routes load a real server identity before displaying workspace content. New users create an organization or accept an invitation sent to their verified email. Owners/admins manage allowed member roles; an organization always retains at least one owner. Switching organizations clears tenant query state. Account settings lists active sessions and can revoke another browser immediately.

The organization settings page supports renaming, inviting teammates, role changes, member removal and activity history. Owners may deactivate an organization after explicitly confirming its slug; members immediately lose access while records are retained. Integrations and engineering data remain empty and clearly described as planned.

## Implementation and changed files

| Area          | Files and responsibility                                                                                                                                                                                                                            |
| ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Migration     | `apps/api/migrations/versions/0002_identity.py` — tables, constraints, grants and FORCE RLS                                                                                                                                                         |
| Backend       | `src/forge/api/v1/identity.py`, `domain/identity.py`, `services/identity.py`, `services/organizations.py`, `repositories/identity.py`, `security/identity.py`, `integrations/mail.py`, `seed.py`; configuration and application composition updated |
| Web           | Auth routes and `/app` layout; `features/auth`, `features/organizations`, `lib/auth-client.ts`, `lib/auth-types.ts`, allowlisted same-origin API forwarding, application navigation and guide                                                       |
| Verification  | Backend config/policy/auth/DB tests, frontend auth-client/proxy tests, desktop/mobile identity workflows, updated public navigation checks, `scripts/configure.test.mjs`                                                                            |
| Operations    | `.env.example`, safe configuration upgrade, Compose email mount and origin settings, runtime directory ownership, ignored outbox, Docker context exclusions and CI                                                                                  |
| Documentation | README, development guide, APIs, data model, architecture, security, identity/tenant ADRs and application design reference                                                                                                                          |

## Database migration

`0002_identity` follows `0001_foundation`. It adds nine tables: `users`, `auth_sessions`, `refresh_tokens`, `identity_tokens`, `rate_limits`, `organizations`, `memberships`, `invitations`, `audit_events`.

Tenant tables enforce RLS for reads and writes. Organization discovery is user-bound, and invitation discovery is restricted to the verified actor's normalized email. Authorized writes set transaction-local tenant context. Membership/inviter references preserve organization boundaries. Runtime cannot update or delete audit records, create tables or bypass RLS. Migration roundtrips and pooled connection reuse are tested on PostgreSQL.

Passwords use Argon2id (64 MiB, three iterations, parallelism four). Refresh, verification, reset and invitation tokens are stored as SHA-256 hashes; raw tokens appear only in session cookies or delivered identity links. Access JWTs expire after ten minutes; refresh families have a thirty-day maximum and rotate with strict replay revocation. Every protected request checks current session and membership state. Password reset revokes all sessions. Verification links expire after 24 hours, reset links after one hour, invitations after seven days.

## Implemented endpoints

All paths below use `/api/v1`. Mutations require the exact configured browser Origin and a CSRF header/cookie binding. `GET /auth/csrf` establishes either a signed anonymous binding or the active session binding.

| Routes                                                  | Behavior                                            |
| ------------------------------------------------------- | --------------------------------------------------- |
| `POST /auth/register`, `/auth/login`                    | Create/sign in; set HttpOnly access/refresh cookies |
| `POST /auth/refresh`, `/auth/logout`                    | Rotate or revoke the current session                |
| `GET /auth/me`, `/auth/csrf`                            | Current identity/memberships and CSRF token         |
| `POST /auth/verify-email/request`, `/confirm`           | Deliver and consume one-use verification            |
| `POST /auth/password-reset/request`, `/confirm`         | Deliver and consume one-use reset                   |
| `GET /auth/sessions`, `DELETE /auth/sessions/{id}`      | List and revoke active sessions                     |
| `GET, POST /organizations`                              | Membership-visible list and creation                |
| `GET, PATCH, DELETE /organizations/{id}`                | Read, rename, deactivate                            |
| `GET /organizations/{id}/members`                       | Paginated member list                               |
| `PATCH, DELETE /organizations/{id}/members/{member_id}` | Change role/remove membership                       |
| `POST /organizations/{id}/invitations`                  | Deliver an email-bound invitation                   |
| `POST /invitations/accept`                              | Consume a verified matching-email invitation        |
| `GET /organizations/{id}/audit`                         | Authorized organization activity                    |

Lists use bounded signed-cursor pagination. Cross-tenant resources return generic 404s. See [the API contract](apis.md) and generated development OpenAPI for complete fields.

## Run and manually verify

From the repository root, upgrade the existing local configuration and build:

```powershell
node scripts/configure.mjs --upgrade
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
```

Use `node scripts/configure.mjs` without `--upgrade` for a fresh installation. The helper creates independent secrets without printing them, preserves existing credentials and prepares the private local email outbox. Open **http://localhost:3000**; the exact origin matters.

1. Choose **Open platform**, then **Create an account**. Register and create an organization.
2. Open **Account settings**, send a verification link, and open its message in `.local/mail`. Follow the link and confirm verification.
3. Create a second organization; use the sidebar switcher and confirm settings/member lists follow the selected organization.
4. Invite another email from **Organization settings**. In a separate browser profile, create that account, verify its address and accept the invitation. Confirm the expected role.
5. Change that role or remove the membership from the owner's browser. Reload the recipient's workspace; removed access is denied immediately by the API.
6. Sign into the same account in a second browser profile. Revoke that session in **Account settings**; the second browser must sign in again.
7. Use **Forgot your password?**, open the reset message, change the password and sign in again. Existing sessions are revoked. Reusing the link fails.
8. As an owner, inspect organization activity and try removing/demoting the last owner. The API rejects the change. Deactivation requires typing the organization slug.

Optional synthetic demo identities:

```powershell
docker compose exec -T backend python -m forge.seed
```

The command creates two independent demo owners/organizations, labels them synthetic, and prints generated passwords only when created. Repeated runs keep existing passwords and rows. Production rejects seeding. No provider call, engineering history or outbound pipeline action is generated.

## Verification

```powershell
npm run format:check
npm run lint
npm run typecheck
npm test
npm run test:config
npm run build
npm audit --audit-level=high
node scripts/test-backend.mjs
npx playwright install chromium
$env:PLAYWRIGHT_BASE_URL = 'http://localhost:3000'
$env:FORGE_E2E_LIVE = '1'
npm run test:e2e
```

Backend native checks from `apps/api`: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src`, `uv run pytest -q -m 'not integration'`. Use `py -3.14 -m uv` instead of `uv` on this workstation.

The isolated PostgreSQL suite passes all 62 tests: 31 identity/security integration cases, two migration/privilege integration cases and 29 unit cases. It creates and drops only a randomly named temporary test database. All 21 frontend unit tests, the configuration preservation test and all 34 desktop/mobile browser tests pass. Formatting, ESLint, TypeScript, Ruff, mypy and the production Docker build pass; npm audit reports zero vulnerabilities. Browser checks use unique synthetic accounts in the local development database and the local outbox.

Compose reports all three services healthy. A PostgreSQL/backend restart preserves revision `0002_identity` and both demo organizations. The seed ran twice without duplicates or password replacement; initial credentials are stored locally in ignored `.local/demo-credentials.txt` on this workstation. Desktop/mobile captures of login, registration, overview, organization settings and account settings show no horizontal overflow or browser errors. The design detector reported no primary findings; its typography/color documentation advisories are recorded in the design handoff.

The independent finish review returned **ship** for those ten desktop/mobile captures and the related frontend accessibility/source checks, with no required fixes. This is a UI review at that scope, not a production security certification.

## Limits and next phase

- SMTP delivery is implemented but this local verification uses the file adapter. Production needs real SMTP credentials, TLS hosting, trusted proxy/IP configuration, secret operations and the Phase 13 acceptance checks.
- The API rate limiter uses its trusted ASGI peer plus an account key. All requests through the local Next.js forwarder share its IP budget (60 attempts per operation per 15 minutes); account limits are ten. Never trust arbitrary browser forwarding headers to bypass this limit.
- Email delivery is synchronous within the identity transaction. Delivery failure rolls back identity/token changes. A database commit failure after mail delivery can still produce an unusable link; durable delivery/retries need a later outbox worker. During SMTP outages, known-account delivery errors can differ from the generic missing-account response.
- Organization deletion is soft deactivation. Physical purge, backup expiry and provider/worker cancellation arrive with their respective data and operations phases. There is no pending invitation listing/revocation UI; links expire, are one-use and recheck the inviter's current authority before acceptance.
- `/auth/me` includes the first 100 organizations and a cursor; the switcher can load further pages. Organization/session/member/audit lists have cursor pagination in stable UUID order; audit rows are not yet sorted chronologically. Passwords are 12–128 characters. Browsers without Web Locks can use an active access session but must sign in again after access expiry instead of racing a refresh across tabs.
- Account operations require JavaScript; the public landing and its navigation remain readable without it. No SSO, MFA, GitHub OAuth, billing or account deletion is implemented in this phase.
- Phase 3 is GitHub identity/integration, authorized repository catalog, webhook inbox, durable jobs and sync. Stop at this phase gate until the next instruction.
