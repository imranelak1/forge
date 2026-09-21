import { expect, test } from "@playwright/test";

test("foundation navigation and layout are usable", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await expect(page.getByText("Your engineering history starts here")).toBeVisible();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Setup guide" })
    .click();
  await expect(page.getByRole("heading", { name: "Start your installation" })).toBeVisible();
  await expect(
    page.getByRole("navigation").getByRole("link", { name: "Setup guide" }),
  ).toHaveAttribute("aria-current", "page");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

test("outage state gives a recovery path", async ({ page }) => {
  await page.route("**/api/v1/health/*", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/problem+json",
      body: JSON.stringify({ code: "upstream_unavailable" }),
    }),
  );
  await page.goto("/system");
  await expect(page.getByText("Some services need attention")).toBeVisible();
  await expect(page.getByText("Healthy", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Open troubleshooting" }).click();
  await expect(page.getByRole("heading", { name: "When a service is unavailable" })).toBeVisible();
});

test("running stack reports actual database readiness", async ({ page }) => {
  test.skip(process.env.FORGE_E2E_LIVE !== "1", "Enable for a running Compose stack");
  await page.goto("/system");
  await expect(page.getByText("Healthy", { exact: true })).toHaveCount(3);
  await page.getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByRole("button", { name: "Run checks" })).toBeEnabled();
});
