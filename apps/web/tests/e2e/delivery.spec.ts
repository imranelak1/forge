import { expect, test, type Page } from "@playwright/test";
import type {
  CIMetrics,
  Deployment,
  DeploymentMetrics,
  WorkflowRun,
} from "../../src/features/delivery/types";

const organization = "11111111-1111-1111-1111-111111111111";
const other = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const repository = "22222222-2222-2222-2222-222222222222";
const runId = "33333333-3333-3333-3333-333333333333";
const deploymentId = "44444444-4444-4444-4444-444444444444";
const window = { from: "2026-06-24T00:00:00Z", to: "2026-09-22T00:00:00Z" };
const evidence = { status: "complete" as const, observed_at: window.to, error_code: null };
const coverage = {
  status: "partial" as const,
  input_watermark: window.to,
  repository_count: 1,
  repositories_complete: 1,
  limitations: ["job_completion_proxy"],
  completion_unknown_count: 1,
  completion_proxy_count: 2,
  jobs_incomplete_count: 1,
};
const duration = {
  sample_count: 2,
  excluded_count: 0,
  mean_seconds: 600,
  median_seconds: 600,
  p75_seconds: 750,
  p95_seconds: 870,
  exclusions: {},
};
const queue = {
  sample_count: 1,
  excluded_count: 1,
  mean_seconds: 60,
  median_seconds: 60,
  p75_seconds: 60,
  p95_seconds: 60,
  exclusions: { queue_unknown: 1 },
};
const run: WorkflowRun = {
  id: runId,
  repository_id: repository,
  repository_name: "synthetic/api",
  provider_id: 300,
  workflow_id: 7,
  workflow_name: "Verify changes",
  run_number: 42,
  attempt: 2,
  event: "pull_request",
  status: "completed",
  conclusion: "success",
  head_sha: "a".repeat(40),
  head_branch: "change/retries",
  actor_login: "maya",
  created_at: "2026-09-21T10:00:00Z",
  queued_at: null,
  started_at: "2026-09-21T10:30:00Z",
  completed_at: "2026-09-21T10:40:00Z",
  completion_source: "jobs",
  html_url: null,
  duration_seconds: 600,
  queue_seconds: null,
  duration_exclusion: null,
  queue_exclusion: "queue_unknown",
  jobs_coverage: evidence,
  links_coverage: evidence,
};
const ci: CIMetrics = {
  formula_version: "ci-attempts-v1",
  as_of: window.to,
  window,
  scope: {
    repository_id: repository,
    selected_only: false,
    repository_count: 1,
    workflow_id: 7,
    branch: "change/retries",
  },
  completed_count: 3,
  decisive_count: 2,
  success_count: 1,
  failure_count: 1,
  success_fraction: 0.5,
  failure_fraction: 0.5,
  conclusions: { success: 1, failure: 1, cancelled: 1 },
  duration,
  queue,
  coverage,
  trend: [],
  recurring_failures: [],
};
const deployment: Deployment = {
  id: deploymentId,
  repository_id: repository,
  repository_name: "synthetic/api",
  provider_id: 501,
  environment: "production",
  classification: "production",
  classification_source: "provider",
  provider_production_environment: true,
  sha: "b".repeat(40),
  ref: "main",
  task: "deploy",
  creator_login: "maya",
  created_at: "2026-09-21T12:00:00Z",
  updated_at: "2026-09-21T12:30:00Z",
  first_success_at: "2026-09-21T12:10:00Z",
  latest_state: "inactive",
  success_eligible: true,
  success_exclusion: null,
  html_url: null,
  statuses_coverage: evidence,
  links_coverage: evidence,
};
const deploymentMetrics: DeploymentMetrics = {
  formula_version: "deployments-v1",
  as_of: window.to,
  window,
  scope: {
    repository_id: repository,
    selected_only: false,
    repository_count: 1,
    environment: null,
    classification: "production",
  },
  successful_count: 1,
  observed_success_count: 2,
  excluded_count: 1,
  exclusions: { incomplete_statuses: 1 },
  fully_covered_days: 0,
  frequency_per_day: null,
  created_count: 2,
  states: { inactive: 1, success: 1 },
  coverage: { ...coverage, limitations: ["incomplete_statuses"] },
  trend: [],
};

async function fixture(page: Page, options: { manager?: boolean; fail?: boolean } = {}) {
  let allow = !options.fail;
  let override: string | null = null;
  let nextAllowed = false;
  const requests: URL[] = [];
  const writes: unknown[] = [];
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "fixture-user",
          name: "Delivery fixture",
          email: "fixture@example.com",
          email_verified: true,
        },
        session_id: "fixture-session",
        organizations: [
          {
            id: organization,
            name: "Synthetic delivery",
            slug: "delivery-fixture",
            role: options.manager ? "owner" : "viewer",
            is_demo: true,
          },
          {
            id: other,
            name: "Other empty organization",
            slug: "other-fixture",
            role: "viewer",
            is_demo: false,
          },
        ],
        organizations_page: { next_cursor: null, has_more: false },
      },
    }),
  );
  await page.route("**/api/v1/auth/csrf", (route) =>
    route.fulfill({ json: { csrf_token: "fixture-csrf" } }),
  );
  await page.route("**/api/v1/organizations/**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    const path = url.pathname.split(`/organizations/${organization}/`)[1];
    const paged = (items: unknown[], next_cursor: string | null = null) =>
      route.fulfill({ json: { items, next_cursor, window, coverage } });
    if (url.pathname.includes(other)) {
      if (url.pathname.endsWith("/metrics/ci"))
        return route.fulfill({
          json: {
            ...ci,
            completed_count: 0,
            decisive_count: 0,
            success_count: 0,
            failure_count: 0,
            success_fraction: null,
            failure_fraction: null,
          },
        });
      return paged([]);
    }
    if (path === "repositories") return paged([{ id: repository, full_name: "synthetic/api" }]);
    if (path === "metrics/ci")
      return route.fulfill(
        allow ? { json: ci } : { status: 503, json: { detail: "CI temporarily unavailable." } },
      );
    if (path === "metrics/deployments") return route.fulfill({ json: deploymentMetrics });
    if (path === "workflow-runs") {
      if (!url.searchParams.has("cursor")) return paged([run], "second-page");
      if (!nextAllowed)
        return route.fulfill({
          status: 503,
          json: { detail: "The next attempt page is unavailable." },
        });
      return paged([
        { ...run, id: "55555555-5555-5555-5555-555555555555", attempt: 1, conclusion: "failure" },
      ]);
    }
    if (path === `workflow-runs/${runId}`)
      return route.fulfill({
        json: { workflow_run: run, counts: { jobs: 1, pull_requests: 0, commits: 0 } },
      });
    if (path === `workflow-runs/${runId}/jobs`)
      return paged([
        {
          id: "job",
          provider_id: 12,
          name: "Unit tests",
          status: "completed",
          conclusion: "success",
          started_at: run.started_at,
          completed_at: run.completed_at,
          duration_seconds: 600,
          html_url: null,
        },
      ]);
    if (path?.startsWith(`workflow-runs/${runId}/`)) return paged([]);
    if (path === "deployments") return paged([deployment]);
    if (path === `deployments/${deploymentId}`)
      return route.fulfill({ json: { deployment, counts: { statuses: 3, commits: 0 } } });
    if (path === `deployments/${deploymentId}/statuses`)
      return paged(
        ["success", "success", "inactive"].map((state, index) => ({
          id: `status-${index}`,
          provider_id: index + 1,
          state,
          created_at: `2026-09-21T12:${10 + index * 5}:00Z`,
          creator_login: "maya",
          description: null,
          html_url: null,
        })),
      );
    if (path === `deployments/${deploymentId}/commits`) return paged([]);
    if (path === `repositories/${repository}/environments`)
      return paged([
        {
          environment: "production",
          override,
          deployment_count: 2,
          production_count: override === "nonproduction" ? 0 : 2,
          nonproduction_count: override === "nonproduction" ? 2 : 0,
          unknown_count: 0,
        },
      ]);
    if (
      path === `repositories/${repository}/environments/classification` &&
      route.request().method() === "PUT"
    ) {
      const body = route.request().postDataJSON();
      writes.push(body);
      override = body.classification;
      return route.fulfill({ json: { environment: body.environment, override } });
    }
    return route.fulfill({ status: 404, json: { detail: "Fixture endpoint not found." } });
  });
  return {
    requests,
    writes,
    allow: () => {
      allow = true;
    },
    allowNext: () => {
      nextAllowed = true;
    },
  };
}

test("CI queue exclusions preserve metric filters and expose attempt job evidence", async ({
  page,
}) => {
  const { requests } = await fixture(page);
  await page.goto(`/app/ci?repository=${repository}&workflow=7&branch=change%2Fretries`);
  await expect(page.getByRole("heading", { name: "Completed attempt metrics" })).toBeVisible();
  const row = page
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: "Queue time", exact: true }) });
  await row.getByRole("link", { name: "1 excluded" }).click();
  await expect(page).toHaveURL(/metric=queue/);
  await expect
    .poll(() =>
      requests.some(
        (url) =>
          url.pathname.endsWith("/workflow-runs") &&
          url.searchParams.get("eligibility") === "excluded",
      ),
    )
    .toBe(true);
  const request = requests.find(
    (url) =>
      url.pathname.endsWith("/workflow-runs") && url.searchParams.get("eligibility") === "excluded",
  )!;
  expect(Object.fromEntries(request.searchParams)).toMatchObject({
    repository,
    workflow: "7",
    branch: "change/retries",
    ...window,
    metric: "queue",
    cohort: "completed",
  });
  await page.getByRole("link", { name: "Verify changes #42 · attempt 2" }).click();
  await expect(page.getByRole("heading", { name: "Verify changes · attempt 2" })).toBeVisible();
  await expect(page.getByText("Unit tests", { exact: true })).toBeVisible();
  await expect(page.getByText(/Last-job completion proxy/i).first()).toBeVisible();
  await expect(page.getByRole("link", { name: "View on GitHub", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("deployment cohort links retain classification and repeated status evidence", async ({
  page,
}) => {
  const { requests } = await fixture(page);
  await page.goto(`/app/deployments?repository=${repository}&classification=production`);
  await page.getByRole("link", { name: "View included deployments" }).click();
  await expect
    .poll(() =>
      requests.some(
        (url) =>
          url.pathname.endsWith("/deployments") && url.searchParams.get("cohort") === "success",
      ),
    )
    .toBe(true);
  const request = requests.find(
    (url) => url.pathname.endsWith("/deployments") && url.searchParams.get("cohort") === "success",
  )!;
  expect(Object.fromEntries(request.searchParams)).toMatchObject({
    repository,
    classification: "production",
    cohort: "success",
    eligibility: "eligible",
    ...window,
  });
  await page.getByRole("link", { name: /production.*501/ }).click();
  await expect(page.getByRole("heading", { name: "Status history (3)" })).toBeVisible();
  await expect(
    page.locator(".analytics-timeline strong").filter({ hasText: /^success$/ }),
  ).toHaveCount(2);
  await expect(
    page.getByText("Provider production_environment flag", { exact: true }),
  ).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("verified managers can set and remove an environment override", async ({ page }) => {
  const { writes } = await fixture(page, { manager: true });
  await page.goto(`/app/deployments/environments?repository=${repository}`);
  const select = page.getByRole("combobox", { name: "Classification for production" });
  await select.selectOption("nonproduction");
  await page.getByRole("button", { name: "Save classification", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Classification saved for production");
  await expect(select).toHaveValue("nonproduction");
  expect(writes).toEqual([{ environment: "production", classification: "nonproduction" }]);
  await select.selectOption("provider");
  await page.getByRole("button", { name: "Save classification", exact: true }).click();
  await expect(select).toHaveValue("provider");
  await expect.poll(() => writes.length).toBe(2);
  expect(writes[1]).toEqual({ environment: "production", classification: null });
});

test("viewers cannot edit policies and switching tenants clears attempt history", async ({
  page,
}) => {
  await fixture(page);
  await page.goto(`/app/deployments/environments?repository=${repository}`);
  await expect(
    page.getByRole("combobox", { name: "Classification for production" }),
  ).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save classification" })).toBeDisabled();
  await page.goto("/app/ci");
  await expect(page.getByRole("link", { name: "Verify changes #42 · attempt 2" })).toBeVisible();
  await page.getByRole("combobox", { name: "Organization", exact: true }).selectOption(other);
  await expect(page.getByRole("link", { name: "Verify changes #42 · attempt 2" })).toHaveCount(0);
  await expect(page.getByText("0 records loaded", { exact: true })).toBeVisible();
});

test("CI failure and pagination retry preserve already loaded attempts", async ({ page }) => {
  const control = await fixture(page, { fail: true });
  await page.goto("/app/ci");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText("CI temporarily unavailable.");
  control.allow();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Completed attempt metrics" })).toBeVisible();
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "The next attempt page is unavailable.",
  );
  await expect(page.getByRole("link", { name: "Verify changes #42 · attempt 2" })).toBeVisible();
  control.allowNext();
  await page.getByRole("button", { name: "Retry loading more" }).click();
  await expect(page.getByRole("link", { name: "Verify changes #42 · attempt 1" })).toBeVisible();
});
