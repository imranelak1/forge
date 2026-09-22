import { expect, test, type Page } from "@playwright/test";

const orgId = "11111111-1111-1111-1111-111111111111";
const connectionId = "22222222-2222-2222-2222-222222222222";
const repositoryId = "33333333-3333-3333-3333-333333333333";

async function githubFixture(page: Page, role = "owner", failFirst = false) {
  let selected = false;
  let failed = false;
  const writes: unknown[] = [];
  const run = {
    id: "44444444-4444-4444-4444-444444444444",
    kind: "history",
    status: "queued",
    stage: "pull_requests",
    since: "2026-06-24T00:00:00Z",
    until: "2026-09-22T00:00:00Z",
    repositories_processed: 0,
    pull_requests_processed: 7,
    commits_processed: 12,
    created_at: "2026-09-22T00:00:00Z",
    started_at: null,
    finished_at: null,
    next_retry_at: null,
    error_code: null,
  };
  const repository = () => ({
    id: repositoryId,
    integration_id: connectionId,
    provider_id: 42,
    full_name: "fixture-team/api-service",
    html_url: "https://github.com/fixture-team/api-service",
    description: "Synthetic browser test repository",
    language: "Python",
    default_branch: "main",
    is_private: true,
    archived: false,
    authorized: true,
    selected,
    pushed_at: "2026-09-21T18:00:00Z",
    last_synced_at: null,
    pull_request_count: 7,
    open_pull_request_count: 2,
    commit_count: 12,
    latest_sync: selected ? run : null,
  });
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "test-user",
          name: "Fixture owner",
          email: "fixture@example.com",
          email_verified: true,
        },
        session_id: "fixture-session",
        organizations: [
          { id: orgId, name: "Synthetic GitHub fixture", slug: "fixture", role, is_demo: true },
        ],
        organizations_page: { next_cursor: null, has_more: false },
      },
    }),
  );
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ json: { csrf_token: "browser-fixture" } }),
  );
  await page.route("**/api/v1/organizations/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/integrations/github")) {
      if (failFirst && !failed) {
        failed = true;
        await route.fulfill({
          status: 503,
          json: { detail: "The GitHub integration could not be reached. Please retry." },
        });
        return;
      }
      await route.fulfill({
        json: {
          configured: true,
          install_url: "https://github.com/apps/forge-fixture/installations/new",
          authorization: null,
          connections: [
            {
              id: connectionId,
              installation_id: 42,
              account_login: "fixture-team",
              account_type: "Organization",
              status: "active",
              created_at: "2026-09-22T00:00:00Z",
              last_error: null,
              catalog_sync: null,
            },
          ],
        },
      });
    } else if (path.endsWith("/selection")) {
      const body = route.request().postDataJSON();
      writes.push(body);
      selected = body.changes[0].selected;
      await route.fulfill({ json: { updated: 1 } });
    } else if (path.endsWith("/sync-runs"))
      await route.fulfill({ json: { items: [run], next_cursor: null } });
    else if (path.endsWith("/repositories"))
      await route.fulfill({
        json: {
          items: path.includes("/connections/") || selected ? [repository()] : [],
          next_cursor: null,
        },
      });
    else await route.fulfill({ status: 404, json: { detail: "No fixture for this endpoint." } });
  });
  return writes;
}

test("select repositories and inspect their queued history import", async ({ page }) => {
  const writes = await githubFixture(page);
  await page.goto("/app/integrations");
  await expect(page.getByRole("heading", { name: "Integrations", exact: true })).toBeVisible();
  await expect(page.getByText("This organization contains demonstration data.")).toBeVisible();
  const choice = page.getByRole("checkbox", { name: /fixture-team\/api-service/ });
  await expect(choice).not.toBeChecked();
  await choice.check();
  await page.getByRole("button", { name: "Save repositories" }).click();
  await expect(
    page.getByText("Repository selection saved. New selections are queued for history import."),
  ).toBeVisible();
  expect(writes).toEqual([{ changes: [{ id: repositoryId, selected: true }] }]);
  await page.getByRole("link", { name: "View repositories" }).click();
  await expect(page.getByText("2 open PRs")).toBeVisible();
  await expect(page.getByText("7 total PRs")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sync in progress" })).toBeDisabled();
  await page.getByRole("button", { name: "Sync details" }).click();
  await expect(
    page.getByRole("heading", { name: "Sync history · fixture-team/api-service" }),
  ).toBeVisible();
  await expect(page.getByText("7 pull requests and 12 commits processed")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("viewer can inspect repositories but cannot change integration access", async ({ page }) => {
  await githubFixture(page, "viewer");
  await page.goto("/app/integrations");
  await expect(page.getByRole("checkbox", { name: /fixture-team\/api-service/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Authorize GitHub" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save repositories" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Disconnect", exact: true })).toHaveCount(0);
});

test("integration loading failures have a working retry", async ({ page }) => {
  await githubFixture(page, "owner", true);
  await page.goto("/app/integrations");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "The GitHub integration could not be reached. Please retry.",
  );
  await page.getByRole("button", { name: "Retry GitHub integration" }).click();
  await expect(page.getByRole("checkbox", { name: /fixture-team\/api-service/ })).toBeEnabled();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
});
