import { expect, test } from "@playwright/test";

test("social sign-in reports unavailable providers and preserves email access", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/providers", (route) =>
    route.fulfill({
      json: {
        providers: [
          { id: "github", enabled: false },
          { id: "google", enabled: false },
        ],
      },
    }),
  );
  await page.goto("/register");
  await expect(page.getByRole("button", { name: "Continue with GitHub" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeDisabled();
  await expect(page.getByText("Social sign-in is not configured yet.")).toBeVisible();
  await expect(page.getByLabel("Email address", { exact: true })).toBeEditable();
  await expect(page.getByRole("button", { name: "Create account", exact: true })).toBeEnabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
});

for (const provider of ["github", "google"] as const) {
  test(`${provider} button starts a protected flow and navigates to the provider`, async ({
    page,
  }) => {
    await page.route("**/api/v1/auth/providers", (route) =>
      route.fulfill({
        json: {
          providers: [
            { id: "github", enabled: true },
            { id: "google", enabled: true },
          ],
        },
      }),
    );
    await page.route("**/api/v1/auth/csrf", (route) =>
      route.fulfill({ json: { csrf_token: "browser-test-csrf" } }),
    );
    const destination =
      provider === "github"
        ? "https://github.com/login/oauth/authorize?client_id=browser-test"
        : "https://accounts.google.com/o/oauth2/v2/auth?client_id=browser-test";
    await page.route(`**/api/v1/auth/oauth/${provider}/start`, (route) => {
      expect(route.request().method()).toBe("POST");
      expect(route.request().postDataJSON()).toEqual({
        intent: "login",
        return_to: "/app/account",
      });
      expect(route.request().headers()["x-csrf-token"]).toBe("browser-test-csrf");
      return route.fulfill({ json: { authorization_url: destination } });
    });
    await page.route(destination, (route) =>
      route.fulfill({ contentType: "text/html", body: "<h1>Provider test boundary</h1>" }),
    );
    await page.goto("/login?returnTo=%2Fapp%2Faccount");
    await page
      .getByRole("button", {
        name: provider === "github" ? "Continue with GitHub" : "Continue with Google",
      })
      .click();
    await expect(page).toHaveURL(destination);
    await expect(page.getByRole("heading", { name: "Provider test boundary" })).toBeVisible();
  });
}

test("provider availability failures can be retried", async ({ page }) => {
  let requests = 0;
  await page.route("**/api/v1/auth/providers", (route) => {
    requests += 1;
    return requests === 1
      ? route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      : route.fulfill({
          json: {
            providers: [
              { id: "github", enabled: true },
              { id: "google", enabled: true },
            ],
          },
        });
  });
  await page.goto("/login");
  await page.getByRole("button", { name: "Retry sign-in options" }).click();
  await expect(page.getByRole("button", { name: "Continue with GitHub" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeEnabled();
});

test("invalid callback returns safely to login with a recovery message", async ({ page }) => {
  test.skip(process.env.FORGE_E2E_LIVE !== "1", "Requires the real API proxy");
  await page.goto("/api/v1/auth/oauth/github/callback?state=invalid&code=browser-test");
  await expect(page).toHaveURL(/\/login\?oauth_error=invalid_state/);
  await expect(
    page.getByRole("alert").filter({ hasText: /expired|restart|try again/i }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address", { exact: true })).toBeEditable();
});
