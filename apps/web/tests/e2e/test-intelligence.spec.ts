import { expect, test, type Page } from "@playwright/test";
import * as f from "../fixtures/test-intelligence";

async function fixture(
  page: Page,
  options: { manager?: boolean; empty?: boolean; fail?: boolean } = {},
) {
  const requests: URL[] = [],
    writes: { method: string; path: string; body: unknown }[] = [];
  let available = !options.fail,
    nextAvailable = false,
    policy = { ...f.testPolicy };
  const tokens = [{ ...f.testToken }],
    credential = "fixture_only_visible_once",
    issuedId = "77777777-7777-7777-7777-777777777777";
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "fixture-user",
          name: "Report fixture",
          email: "fixture@example.com",
          email_verified: true,
        },
        session_id: "fixture-session",
        organizations: [
          {
            id: f.testOrg,
            name: "Synthetic test history",
            slug: "test-fixture",
            role: options.manager ? "owner" : "viewer",
            is_demo: false,
          },
          {
            id: f.testOther,
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
    const url = new URL(route.request().url()),
      method = route.request().method(),
      path = url.pathname.split(`/organizations/${f.testOrg}/`)[1];
    requests.push(url);
    const paged = (items: unknown[], cursor: string | null = null) =>
      route.fulfill({ json: f.testPage(items, cursor) });
    const emptyMetrics = {
      ...f.testMetrics,
      passed_count: 0,
      failed_count: 0,
      error_count: 0,
      skipped_count: 0,
      eligible_count: 0,
      pass_fraction: null,
      report_count: 0,
      coverage: { ...f.testMetrics.coverage, status: "unavailable", with_reports_count: 0 },
    };
    if (url.pathname.includes(f.testOther))
      return url.pathname.endsWith("/metrics/tests")
        ? route.fulfill({ json: emptyMetrics })
        : paged([]);
    if (path === "repositories") return paged([f.testRepository]);
    if (path === "metrics/tests")
      return route.fulfill(
        !available
          ? { status: 503, json: { detail: "Test metrics temporarily unavailable." } }
          : { json: options.empty ? emptyMetrics : f.testMetrics },
      );
    if (path === "test-runs") {
      if (options.empty) return paged([]);
      if (!url.searchParams.has("cursor")) return paged([f.testReport], "next-reports");
      if (!nextAvailable)
        return route.fulfill({ status: 503, json: { detail: "Next report page unavailable." } });
      return paged([{ ...f.testReport, id: f.testWorkflow, report_key: "integration-tests" }]);
    }
    if (path === `test-runs/${f.testReportId}`) return route.fulfill({ json: f.reportDetail });
    if (path === `test-runs/${f.testReportId}/suites`) return paged([f.testSuite]);
    if (path === `test-runs/${f.testReportId}/cases`) return paged([f.testCase]);
    if (path === "tests") return paged(options.empty ? [] : [f.testEvidence]);
    if (path === `tests/${f.testCaseId}/history`) return route.fulfill({ json: f.testHistory });
    if (path === `repositories/${f.testRepo}/test-policy`) {
      if (method === "PATCH") {
        const body = route.request().postDataJSON();
        writes.push({ method, path, body });
        policy = { ...policy, ...body, version: 2, updated_at: f.testWindow.to };
      }
      return route.fulfill({ json: policy });
    }
    if (path === `repositories/${f.testRepo}/service-tokens`) {
      if (method === "POST") {
        const body = route.request().postDataJSON();
        writes.push({ method, path, body });
        const token = { ...f.testToken, id: issuedId, name: body.name };
        tokens.push(token);
        return route.fulfill({ status: 201, json: { token, credential } });
      }
      return paged(tokens);
    }
    if (path === `service-tokens/${issuedId}` && method === "DELETE") {
      writes.push({ method, path, body: null });
      tokens[tokens.length - 1].revoked_at = f.testWindow.to;
      return route.fulfill({ status: 204 });
    }
    return route.fulfill({ status: 404, json: { detail: "Fixture endpoint not found." } });
  });
  return {
    requests,
    writes,
    credential,
    allow: () => {
      available = true;
    },
    allowNext: () => {
      nextAvailable = true;
    },
  };
}

test("test outcomes lead to report cases and policy evidence without inventing complete coverage", async ({
  page,
}) => {
  const server = await fixture(page);
  await page.goto(
    `/app/tests?repository=${f.testRepo}&branch=main&environment=ci&from=${f.testWindow.from}&to=${f.testWindow.to}`,
  );
  await expect(page.getByRole("heading", { name: "Test intelligence", exact: true })).toBeVisible();
  const rate = page
    .getByRole("row")
    .filter({ has: page.getByRole("rowheader", { name: "Pass rate", exact: true }) });
  await expect(rate).toContainText("80%");
  await expect(rate).toContainText("10 eligible executions");
  await expect(page.getByText("Uploaded reports only", { exact: true })).toBeVisible();
  expect(
    server.requests
      .find((u) => u.pathname.endsWith("/tests") && !u.pathname.endsWith("/metrics/tests"))
      ?.searchParams.has("from"),
  ).toBe(false);
  await page.getByRole("link", { name: "unit-tests · linux", exact: true }).click();
  await expect(page.getByRole("heading", { name: "unit-tests", exact: true })).toBeVisible();
  await expect(page.getByText("Last-job completion proxy", { exact: true })).toBeVisible();
  await expect(page.getByText("API / Checkout", { exact: true })).toBeVisible();
  await page.getByText("Read failure message", { exact: true }).click();
  await expect(page.getByText(f.testCase.failure_message!, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: f.testCase.name, exact: true }).click();
  await expect(page.getByRole("heading", { name: f.testCase.name, exact: true })).toBeVisible();
  await expect(page.getByRole("cell", { name: /12 eligible samples/ })).toBeVisible();
  await expect(page.getByRole("cell", { name: /4 flips/ })).toBeVisible();
  await expect(page.getByText(/Evaluation uses the current policy lookback/)).toBeVisible();
});
test("verified managers save policy then issue, dismiss and revoke an upload token", async ({
  page,
}) => {
  const server = await fixture(page, { manager: true });
  await page.goto(`/app/tests/settings?repository=${f.testRepo}`);
  await page.getByRole("spinbutton", { name: "Lookback days" }).fill("21");
  await page.getByRole("textbox", { name: "Excluded branches" }).fill("maintenance");
  await page.getByRole("button", { name: "Save test policy", exact: true }).click();
  await expect(page.getByText("Test policy saved.", { exact: true })).toBeVisible();
  expect(server.writes[0]).toMatchObject({
    method: "PATCH",
    body: { window_days: 21, excluded_branches: ["maintenance"] },
  });
  await page.getByRole("textbox", { name: "Token name", exact: true }).fill("New uploader");
  await page.getByRole("button", { name: "Issue upload token", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "CI upload credential", exact: true }),
  ).toHaveValue(server.credential);
  expect(
    await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage })),
  ).not.toContain(server.credential);
  await page.getByRole("button", { name: "Dismiss credential", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "CI upload credential", exact: true }),
  ).toHaveCount(0);
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "CI upload credential", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Revoke New uploader", exact: true }).click();
  expect(server.writes.some((w) => w.method === "DELETE")).toBe(false);
  await page.getByRole("button", { name: "Confirm revoke", exact: true }).click();
  await expect(page.getByText(/Revoked New uploader/)).toBeVisible();
  expect(server.writes.some((w) => w.method === "DELETE")).toBe(true);
});
test("viewers inspect settings and organization switching removes prior test data", async ({
  page,
}) => {
  await fixture(page);
  await page.goto(`/app/tests/settings?repository=${f.testRepo}`);
  await expect(page.getByRole("spinbutton", { name: "Lookback days" })).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Issue upload token", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Revoke Build uploader", exact: true }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "Tests", exact: true }).click();
  await expect(page.getByRole("link", { name: "unit-tests · linux", exact: true })).toBeVisible();
  await page.getByRole("combobox", { name: "Organization", exact: true }).selectOption(f.testOther);
  await expect(page.getByRole("link", { name: "unit-tests · linux", exact: true })).toHaveCount(0);
  await expect(
    page
      .getByRole("row")
      .filter({ has: page.getByRole("rowheader", { name: "Pass rate", exact: true }) }),
  ).toContainText("Not available");
});
test("metric and report-page retry preserve already imported records", async ({ page }) => {
  const server = await fixture(page, { fail: true });
  await page.goto("/app/tests");
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Test metrics temporarily unavailable.",
  );
  server.allow();
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(
    page
      .getByRole("row")
      .filter({ has: page.getByRole("rowheader", { name: "Pass rate", exact: true }) }),
  ).toContainText("80%");
  await page.getByRole("button", { name: "Load more", exact: true }).click();
  await expect(page.getByText("Next report page unavailable.", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "unit-tests · linux", exact: true })).toBeVisible();
  server.allowNext();
  await page.getByRole("button", { name: "Retry loading more", exact: true }).click();
  await expect(
    page.getByRole("link", { name: "integration-tests · linux", exact: true }),
  ).toBeVisible();
});
test("missing reports explain upload setup and do not produce a healthy zero rate", async ({
  page,
}) => {
  await fixture(page, { empty: true });
  await page.goto("/app/tests");
  await expect(
    page
      .getByRole("row")
      .filter({ has: page.getByRole("rowheader", { name: "Pass rate", exact: true }) }),
  ).toContainText("Not available");
  await expect(page.getByText("Reports unavailable", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Set up report uploads", exact: true }),
  ).toHaveAttribute("href", "/app/tests/settings");
  await page.getByRole("link", { name: "Read the upload guide", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Upload JUnit test reports", exact: true }),
  ).toBeVisible();
});
