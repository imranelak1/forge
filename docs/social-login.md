# GitHub and Google sign-in

Forge supports GitHub and Google sign-in on `/login` and `/register`. Both create the same server-owned Forge sessions as password sign-in. Existing users can connect either provider from `/app/account` after verifying their Forge email address.

This is account authentication. Connecting GitHub here does not grant repository access or install the future Forge GitHub App.

## Local setup

Run `node scripts/configure.mjs --upgrade` to add missing settings without rotating existing credentials. Register applications with the providers, then set their issued credentials in the ignored root `.env`:

```dotenv
FORGE_PUBLIC_ORIGIN=http://localhost:3000
FORGE_GITHUB_CLIENT_ID=
FORGE_GITHUB_CLIENT_SECRET=
FORGE_GOOGLE_CLIENT_ID=
FORGE_GOOGLE_CLIENT_SECRET=
```

Provide both values for each enabled provider. Leaving a pair blank disables that provider; supplying only one fails startup validation. Client secrets stay on the API server and must never use a `NEXT_PUBLIC_` variable. Do not paste secrets into chat, commit them, or put them in browser code.

| Provider | Application type              | Exact local callback                                      |
| -------- | ----------------------------- | --------------------------------------------------------- |
| GitHub   | OAuth App                     | `http://localhost:3000/api/v1/auth/oauth/github/callback` |
| Google   | OAuth client: Web application | `http://localhost:3000/api/v1/auth/oauth/google/callback` |

For GitHub, register an OAuth App in your personal or organization developer settings. Set the homepage URL to `http://localhost:3000` and the callback above; copy the client ID and generate a client secret. Use a separate app for a production hostname. [GitHub registration instructions](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app)

For Google, configure the consent screen and audience in your Google Cloud project, then create a Web application OAuth client with the exact authorized redirect URI above. If the app is in testing, add the Google accounts you will use as test users. Forge uses the server authorization-code flow; a browser SDK is not required. [Google OpenID Connect setup](https://developers.google.com/identity/openid-connect/openid-connect)

Apply the configuration and migrations:

```powershell
docker compose up -d --build --wait --wait-timeout 180
```

Open `http://localhost:3000/login`. Always use the hostname and port from `FORGE_PUBLIC_ORIGIN`; mixing `localhost` and `127.0.0.1` breaks the browser binding. For deployment, replace the origin and both registered callback URLs with your HTTPS domain and configure the existing production mail settings.

## Account behavior

- First sign-in creates an account without a password. The user can later set a password through the existing password-reset email flow.
- Returning sign-in identifies the account by the provider's stable subject, not by an editable email address.
- An email matching an existing Forge account does not automatically connect it. Sign in using the existing method, verify the Forge email, and choose **Connect GitHub** or **Connect Google** in account settings.
- A connection requires the same active Forge session throughout the redirect and cannot be transferred from another user.
- GitHub requires a verified primary email. Google signup requires a verified Gmail or authoritative Workspace address. For third-party addresses, first create a Forge account with email/password, verify the address, then connect Google from account settings. A previously connected Google identity can sign in normally.
- Sign-in grants no organization membership. Existing invitations and tenant permissions retain their checks.
- Connection removal is not included in this change. Provider-side authorization can be revoked in the provider's account settings.

## Security and API contract

| Method and route under `/api/v1`      | Result                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `GET /auth/providers`                 | `{providers: [{id, enabled}]}`; no credentials exposed                                            |
| `POST /auth/oauth/{provider}/start`   | CSRF-protected `{intent: "login" or "link", return_to: "/app..."}`; returns `{authorization_url}` |
| `GET /auth/oauth/{provider}/callback` | Consumes the browser-bound state and code, sets Forge cookies, redirects locally                  |
| `GET /auth/connections`               | Authenticated `{connections: [{provider, email, created_at}]}`                                    |

Only `github` and `google` are accepted. The flow uses ten-minute, one-use database state bound to an HttpOnly SameSite=Lax cookie, S256 PKCE, and a nonce for Google. Google ID tokens are checked against Google's signing keys, issuer, audience, expiration and nonce. Provider HTTP destinations are fixed, bounded and do not follow redirects. Neither provider access tokens nor refresh tokens are retained. [GitHub web flow and PKCE](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps), [Google token validation](https://developers.google.com/identity/openid-connect/openid-connect)

Migration `0003_oauth` adds global external identity and short-lived OAuth state tables, and permits a null password hash for accounts created with a provider. Runtime database grants remain separate from migration privileges. Organization RLS is unchanged.

Errors use fixed codes and readable recovery messages; provider error text is not reflected. Callback responses disable caching and referrers. Application logs record paths without query strings; reverse proxies in a deployed environment must also omit OAuth callback queries.

Callbacks accept the standard `iss` field and validate any supplied issuer against the selected provider before exchanging the code. Google uses `https://accounts.google.com`; GitHub's optional local policy is `https://github.com`. Omission remains compatible with providers that do not send it. The proxy discards unknown response extensions, as OAuth requires, while retaining callback size limits, duplicate-field rejection and the normal API query allowlist. Error metadata such as `error_uri` is never followed. [OAuth response handling](https://www.rfc-editor.org/rfc/rfc6749#section-4.1.2), [issuer validation](https://www.rfc-editor.org/rfc/rfc9207#section-2.4)

## Verification

`node scripts/test-backend.mjs` exercises the real PostgreSQL identity and session stack against mocked provider HTTP endpoints and locally signed test ID tokens. These tests cover state, browser binding, replay, PKCE, signature/claims, account collision and explicit linking. Frontend tests cover the transport allowlist, safe redirects, provider availability and recovery states. Browser checks cover the sign-in controls on desktop and mobile.

Live provider consent and token exchange require registered client credentials. They cannot be verified with the blank local defaults. After configuring each provider, complete one new-user sign-in, sign out and sign in again, then test connecting that provider from an existing verified account. Also cancel a consent screen and confirm Forge offers a retry.

Initial implementation validation on 2026-09-22: 114 backend tests passed against the isolated PostgreSQL test database; 58 frontend unit tests and the configuration-helper test passed. All 44 desktop/mobile browser cases passed across the full run and the targeted OAuth rerun after correcting a test locator that also matched Next.js's route announcer. The production Docker build, TypeScript, ESLint, Ruff, mypy and formatting checks passed. The running stack migrated to `0003_oauth` without clearing existing data.

The scoped visual review recorded `ship` for login, registration and account settings. It ran inline because the harness's agent thread limit prevented a separate reviewer; desktop/mobile captures are in ignored `.impeccable/review/oauth-*.png`. Enabled-provider captures use a discovery fixture and are not evidence of real provider consent. No live credentials were supplied or external authorization performed during that initial validation.

After provider configuration, the callback compatibility fix reproduced a `400 Unsupported query parameters` response for Google's `iss` field. The same request now reaches the API and produces the expected safe redirect for invalid state. Validation: 121 backend tests, 25 proxy unit tests and 12 OAuth desktop/mobile browser checks passed; production build, lint and type checks passed. The isolated backend runner explicitly clears live provider credentials so fixtures control all test authorization exchanges. Real user consent remains an interactive sign-in step.
