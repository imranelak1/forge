# Connect GitHub repositories

GitHub and Google **sign-in** use the settings in [social-login.md](social-login.md). Repository access uses a separate **GitHub App**. Signing in does not grant repository access. Forge imports PR/review/commit evidence, Actions attempts/jobs and independent deployment/status history. Issues, Actions and Deployments each use optional read permissions; missing grants are reported independently. Test report ingestion arrives in Phase 6.

## Register the GitHub App

Create a GitHub App under the account that will own the integration. A private app is suitable for your own sandbox account. Use a public app when other GitHub accounts need to install it. [Registration instructions](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)

| Setting                                        | Local value                                                 |
| ---------------------------------------------- | ----------------------------------------------------------- |
| Homepage URL                                   | `http://localhost:3000`                                     |
| Callback URL                                   | `http://localhost:3000/api/v1/integrations/github/callback` |
| Setup URL                                      | `http://localhost:3000/app/integrations`                    |
| Request user authorization during installation | Off; Forge starts authorization explicitly                  |
| Webhook URL                                    | Your reachable HTTPS API URL plus `/api/v1/webhooks/github` |
| Webhook secret                                 | A new random secret of at least 32 bytes                    |

GitHub cannot deliver to `localhost`. For local webhooks, forward a reachable HTTPS endpoint to `http://localhost:8000/api/v1/webhooks/github`, preserving the exact request body and GitHub headers. The frontend proxy does not expose this endpoint. Backfill works without a public webhook URL, but new events will not arrive until delivery is configured. Do not label a connection as fully live merely because its backfill succeeds.

Grant only these read permissions:

- **Repository metadata:** Read (GitHub supplies this automatically).
- **Repository contents:** Read, for commit history.
- **Repository pull requests:** Read.
- **Repository issues:** Read, optional for issue records and explicit PR references. Missing permission leaves issue coverage unavailable and does not stop PR/commit ingestion.
- **Repository actions:** Read, for workflow attempts and jobs. Missing permission leaves CI coverage unavailable.
- **Repository deployments:** Read, for deployment objects and their status histories. Missing permission leaves deployment coverage unavailable.
- **Organization members:** Read, to prove that an organization installation is authorized by a GitHub organization owner. Personal installations require the authenticated GitHub user to own the installation account instead.

Subscribe to **Push**, **Pull request**, **Pull request review**, **Issues** (when granted), **Workflow run**, **Deployment**, **Deployment status**, and installation/repository access events available in the app settings. Installation events are delivered automatically where GitHub manages the subscription. Existing installations must accept newly requested permissions after saving the App configuration. Then run a normal repository sync in Forge to reconcile historical records. Unsupported deliveries are acknowledged as ignored with a reason. [GitHub App permissions](https://docs.github.com/en/apps/creating-github-apps/setting-up-a-github-app/choosing-permissions-for-a-github-app), [webhook events](https://docs.github.com/en/webhooks/webhook-events-and-payloads)

Generate a client secret and download an RSA private key. Put these six values in the ignored root `.env`; they are distinct from `FORGE_GITHUB_CLIENT_ID` and `FORGE_GITHUB_CLIENT_SECRET` used for sign-in:

```dotenv
FORGE_GITHUB_APP_ID=<numeric app ID>
FORGE_GITHUB_APP_SLUG=<slug in github.com/apps/your-app>
FORGE_GITHUB_APP_CLIENT_ID=<app client ID>
FORGE_GITHUB_APP_CLIENT_SECRET=<app client secret>
FORGE_GITHUB_APP_PRIVATE_KEY_BASE64=<base64 of the complete downloaded PEM file>
FORGE_GITHUB_APP_WEBHOOK_SECRET=<same secret configured in GitHub>
```

All six values must be provided together. The private key must be RSA, at least 2048 bits. Keep the PEM, base64 value and secrets outside Git, browser code, screenshots and chat. Base64 encodes the PEM; it is not encryption. Store production values in a secret manager. Installation tokens are generated server-side and kept only in memory. [Installation authentication](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation)

Apply configuration without rotating existing credentials:

```powershell
node scripts/configure.mjs --upgrade
docker compose up -d --build --wait --wait-timeout 180
```

## Connect and synchronize

1. Sign in to Forge, verify your email, and select an organization where you are an owner or admin.
2. Open **Integrations**. Install the GitHub App into the intended GitHub account and select its allowed repositories.
3. Authorize the app from Forge. Use the GitHub account owner or a GitHub organization owner; access to only one repository is insufficient to authorize all repositories in an installation.
4. Select the verified installation. It can belong to only one Forge organization. A durable catalog sync starts immediately.
5. Select repositories from the catalog and save. Each selected repository gets a background sync.
6. Open **Repositories** to inspect stored PR/commit counts, coverage dates, sync stages, retries and errors. Counts come from PostgreSQL, and cover imported records rather than all historical GitHub activity.

The first sync looks back 90 days: PRs updated within the window and commits on the default branch within the window. Subsequent webhook reconciliation uses a ten-minute overlap. Manual sync also provides recovery when webhooks were missed. History is resumable by page; no percentage is shown when the total is unknown. Upserts and source timestamps prevent duplicate or older PR snapshots from inflating data.

Disconnecting retains imported history but disables further ingestion. Removed repository access and suspended/deleted installations stop affected work. Reconnecting requires fresh authorization. Uninstalling and reinstalling creates a separate source history, preserving the old records without merging them into the new connection. A partial or failed run can be retried from its saved checkpoint; permission errors require resolving the GitHub permission or installation issue first.

## Verify and troubleshoot

```powershell
node scripts/test-backend.mjs
npm run test --workspace @forge/web
docker compose ps
docker compose logs --tail=80 worker
```

The backend runner uses an isolated temporary database and clears live provider credentials. Tests replace external GitHub HTTP responses while exercising real authentication, transactions, RLS, normalization, checkpoints and leases. They do not prove access to a customer's GitHub account.

For a live sandbox check, finish a catalog and repository sync, create or update a pull request, then inspect GitHub's recent webhook deliveries. Redelivering the same delivery should return the original receipt and create no second job. A changed body signed with the wrong secret is rejected. Restart the worker during a multi-page sync and confirm it continues from its saved page after its lease expires.

An installation request awaiting a GitHub organization owner's approval is not a connected source. Missing app configuration disables connection actions. `access_denied`, `permissions_required`, or a suspended installation requires correction in GitHub and a catalog refresh or fresh connection. Rate limits preserve the checkpoint and show a scheduled retry. If a GitHub sign-in email matches an existing Forge account, use that account's existing sign-in method and connect GitHub in Account settings.

Current bounds: 1 MiB uncompressed webhook bodies, 8 MiB provider responses, 100 records per page, at most 100 pages per stage, eight attempts per failing page, and a 60-second worker lease. Capacity limits remain explicit failures/partial coverage; they are not reported as a complete import. This phase does not implement automated provider delivery-log recovery or scheduled polling. PR reviews and analytics are now implemented. Existing installations need to accept newly requested Issues permission, and existing App registrations need the review/issue event subscriptions enabled. Use a manual repository sync to reconcile existing records after changing access.

Processed raw webhook payloads are cleared opportunistically after seven days, at most 100 per tenant job. Idle tenants wait for their next job; failed/queued payloads and receipt deduplication metadata are retained. A scheduled purge and replay operator interface are not included.
