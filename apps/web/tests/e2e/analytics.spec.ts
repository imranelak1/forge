import { expect, test, type Page } from "@playwright/test";
import type {
  Commit,
  Distribution,
  Metrics,
  PullRequest,
} from "../../src/features/analytics/types";

const organization = "11111111-1111-1111-1111-111111111111";
const otherOrganization = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const repository = "22222222-2222-2222-2222-222222222222";
const prId = "33333333-3333-3333-3333-333333333333";
const commitId = "44444444-4444-4444-4444-444444444444";
const complete = {
  status: "complete" as const,
  observed_at: "2026-09-22T00:00:00Z",
  error_code: null,
};
const window = { from: "2026-06-24T00:00:00Z", to: "2026-09-22T00:00:00Z" };
const distribution: Distribution = {
  sample_count: 1,
  excluded_count: 0,
  mean_seconds: 86400,
  median_seconds: 86400,
  p75_seconds: 86400,
  p95_seconds: 86400,
  exclusions: {},
};
const missing: Distribution = {
  sample_count: 0,
  excluded_count: 1,
  mean_seconds: null,
  median_seconds: null,
  p75_seconds: null,
  p95_seconds: null,
  exclusions: { missing_approval: 1 },
};
const pr: PullRequest = {
  id: prId,
  repository_id: repository,
  repository_name: "synthetic/api",
  number: 4,
  title: "Preserve context across retries",
  state: "closed",
  draft: false,
  author_login: "maya",
  html_url: "",
  opened_at: "2026-09-20T12:00:00Z",
  updated_at: "2026-09-21T12:00:00Z",
  closed_at: "2026-09-21T12:00:00Z",
  merged_at: "2026-09-21T12:00:00Z",
  head_sha: "a".repeat(40),
  base_ref: "main",
  merge_commit_sha: "b".repeat(40),
  durations: { cycle_time: 86400, review_wait: 7200, approval_to_merge: null },
  exclusions: { cycle_time: null, review_wait: null, approval_to_merge: "missing_approval" },
  first_review_at: "2026-09-20T14:00:00Z",
  first_approved_at: null,
  approval_dismissed: false,
  unknown_dismissed_review_count: 0,
  coverage: {
    reviews: complete,
    transitions: complete,
    commits: complete,
    issues: { status: "unavailable", observed_at: null, error_code: "issues_permission_missing" },
  },
};
const commit: Commit = {
  id: commitId,
  repository_id: repository,
  repository_name: "synthetic/api",
  sha: "a".repeat(40),
  message: "Bound retries without losing context",
  author_login: "maya",
  authored_at: "2026-09-20T13:00:00Z",
  committed_at: "2026-09-20T13:00:00Z",
  html_url: "",
  additions: 12,
  deletions: 4,
  changed_files: 1,
  files_coverage: complete,
  pull_request_count: 1,
};
const metrics: Metrics = {
  formula_version: "pr-flow-v1",
  as_of: window.to,
  window,
  scope: { repository_id: repository, selected_only: false, repository_count: 1 },
  merged_count: 1,
  metrics: {
    cycle_time: distribution,
    review_wait: {
      ...distribution,
      mean_seconds: 7200,
      median_seconds: 7200,
      p75_seconds: 7200,
      p95_seconds: 7200,
    },
    approval_to_merge: missing,
  },
  trend: [
    {
      date: "2026-09-21",
      merged_count: 1,
      metrics: { cycle_time: distribution, review_wait: distribution, approval_to_merge: missing },
    },
  ],
  open_queue: { count: 0, age: { ...missing, excluded_count: 0, exclusions: {} }, oldest: [] },
  coverage: {
    status: "partial",
    input_watermark: complete.observed_at,
    repository_count: 1,
    repositories_synced: 1,
    reviews_complete: 1,
    reviews_incomplete: 0,
    dismissed_approval_count: 0,
    unknown_dismissed_review_count: 0,
    unknown_reviewer_count: 0,
    limitations: ["history_window_partial"],
  },
};

async function fixture(page: Page, failMetrics = false) {
  let metricsAllowed = !failMetrics;
  let nextPageFailed = false;
  const requests: URL[] = [];
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "fixture-user",
          name: "Analytics fixture",
          email: "fixture@example.com",
          email_verified: true,
        },
        session_id: "fixture-session",
        organizations: [
          {
            id: organization,
            name: "Synthetic analytics",
            slug: "analytics-fixture",
            role: "viewer",
            is_demo: true,
          },
          {
            id: otherOrganization,
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
  await page.route("**/api/v1/organizations/**", async (route) => {
    const url = new URL(route.request().url());
    requests.push(url);
    const path = url.pathname.split(`/organizations/${organization}/`)[1];
    const paged = (items: unknown[], next_cursor: string | null = null) =>
      route.fulfill({ json: { items, next_cursor, window } });
    if (url.pathname.includes(otherOrganization)) return paged([]);
    if (path === "repositories") return paged([{ id: repository, full_name: "synthetic/api" }]);
    if (path === "metrics/pull-requests") {
      if (!metricsAllowed) {
        return route.fulfill({
          status: 503,
          json: { detail: "Analytics temporarily unavailable." },
        });
      }
      return route.fulfill({ json: metrics });
    }
    if (path === "pull-requests") return paged([pr]);
    if (path === `pull-requests/${prId}`)
      return route.fulfill({
        json: { pull_request: pr, counts: { reviews: 1, transitions: 1, commits: 1, issues: 0 } },
      });
    if (path === `pull-requests/${prId}/reviews`)
      return paged([
        {
          id: "review",
          provider_id: 7,
          reviewer_login: "alex",
          reviewer_type: "User",
          state: "COMMENTED",
          submitted_at: pr.first_review_at,
          approved_at: null,
          dismissed_at: null,
          html_url: null,
          qualifies: true,
          approval_known: false,
        },
      ]);
    if (path === `pull-requests/${prId}/transitions`)
      return paged([
        {
          id: "event",
          provider_id: 9,
          kind: "reopened",
          occurred_at: pr.first_review_at,
          actor_login: "maya",
          html_url: null,
        },
      ]);
    if (path === `pull-requests/${prId}/commits`)
      return paged([{ ...commit, relationship: "member" }]);
    if (path === `pull-requests/${prId}/issues`) return paged([]);
    if (path === "commits") {
      if (!url.searchParams.has("cursor")) return paged([commit], "next-fixture-page");
      if (!nextPageFailed) {
        nextPageFailed = true;
        return route.fulfill({ status: 503, json: { detail: "The next page could not load." } });
      }
      return paged([
        {
          ...commit,
          id: "55555555-5555-5555-5555-555555555555",
          message: "Second imported commit",
        },
      ]);
    }
    if (path === `commits/${commitId}`) return route.fulfill({ json: { commit } });
    if (path === `commits/${commitId}/files`)
      return paged([
        {
          id: "file",
          filename: "src/services/retries.py",
          previous_filename: null,
          status: "modified",
          additions: 12,
          deletions: 4,
          changes: 16,
          blob_url: null,
        },
      ]);
    if (path === `commits/${commitId}/pull-requests`)
      return paged([{ ...pr, relationship: "member" }]);
    return route.fulfill({ status: 404, json: { detail: "No fixture for this endpoint." } });
  });
  return {
    requests,
    allowMetrics: () => {
      metricsAllowed = true;
    },
  };
}

test("metric exclusions retain the exact cohort and open record evidence", async ({ page }) => {
  const { requests } = await fixture(page);
  await page.goto(`/app?repository=${repository}&author=maya`);
  await expect(page.getByRole("heading", { name: "Merged pull requests" })).toBeVisible();
  const approvalRow = page
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: /Approval to merge/ }) });
  await expect(approvalRow.getByText("Not available", { exact: true })).toHaveCount(4);
  await approvalRow.getByRole("link", { name: "1 excluded" }).click();
  await expect(page.getByRole("heading", { name: "Approval to merge evidence" })).toBeVisible();
  const filterToggle = page.getByRole("button", { name: /^Filters / });
  if (await filterToggle.isVisible()) await filterToggle.click();
  await expect(page.getByRole("combobox", { name: "Samples", exact: true })).toHaveValue(
    "excluded",
  );
  await expect(page.getByRole("link", { name: pr.title })).toBeVisible();
  const request = requests.find(
    (url) => url.pathname === `/api/v1/organizations/${organization}/pull-requests`,
  );
  expect(Object.fromEntries(request!.searchParams)).toMatchObject({
    repository,
    author: "maya",
    from: window.from,
    to: window.to,
    metric: "approval_to_merge",
    eligibility: "excluded",
    cohort: "merged",
  });
  await page.getByRole("link", { name: pr.title }).click();
  await expect(page.getByRole("heading", { name: "Reviews (1)" })).toBeVisible();
  await expect(page.getByText("alex", { exact: true })).toBeVisible();
  await expect(page.getByText("Reopened", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: commit.message })).toBeVisible();
  await expect(page.getByRole("link", { name: "View on GitHub", exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("commit pagination retries preserve loaded records and show file evidence", async ({
  page,
}) => {
  await fixture(page);
  await page.goto("/app/commits");
  await expect(page.getByRole("link", { name: commit.message })).toBeVisible();
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "The next page could not load.",
  );
  await expect(page.getByRole("link", { name: commit.message })).toBeVisible();
  await page.getByRole("button", { name: "Retry loading more" }).click();
  await expect(page.getByRole("link", { name: "Second imported commit" })).toBeVisible();
  await page.getByRole("link", { name: commit.message }).click();
  await expect(page.getByRole("heading", { name: "Changed files" })).toBeVisible();
  await expect(page.getByText("src/services/retries.py", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: pr.title })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test("analytics failures offer a working retry and organization changes clear history", async ({
  page,
}) => {
  const { allowMetrics } = await fixture(page, true);
  await page.goto("/app");
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(
    "Analytics temporarily unavailable.",
  );
  allowMetrics();
  await page.getByRole("button", { name: "Try again" }).click();
  await expect(page.getByRole("heading", { name: "Merged pull requests" })).toBeVisible();
  await page.goto("/app/pull-requests");
  await expect(page.getByRole("link", { name: pr.title })).toBeVisible();
  await page
    .getByRole("combobox", { name: "Organization", exact: true })
    .selectOption(otherOrganization);
  await expect(page.getByRole("link", { name: pr.title })).toHaveCount(0);
  await expect(page.getByText("0 records loaded", { exact: true })).toBeVisible();
});
