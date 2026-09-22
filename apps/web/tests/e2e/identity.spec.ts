import { randomUUID } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { resolve } from "node:path";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const password = "Browser test account password 2026";
const outbox = resolve(process.cwd(), "../../.local/mail");

async function write(
  request: APIRequestContext,
  origin: string,
  route: string,
  data?: unknown,
  method = "POST",
) {
  const csrf = await request.get("/api/v1/auth/csrf");
  expect(csrf.ok()).toBe(true);
  return request.fetch(`/api/v1${route}`, {
    method,
    data,
    headers: { Origin: origin, "X-CSRF-Token": (await csrf.json()).csrf_token },
  });
}

async function mailLink(email: string, route: string) {
  let link = "";
  await expect
    .poll(
      async () => {
        const files = await readdir(outbox);
        const messages = await Promise.all(
          files
            .filter((name) => name.endsWith(".eml"))
            .map(async (name) => {
              const path = resolve(outbox, name);
              return { time: (await stat(path)).mtimeMs, body: await readFile(path, "utf8") };
            }),
        );
        for (const { body } of messages.sort((a, b) => b.time - a.time)) {
          if (!body.includes(`To: ${email}`)) continue;
          const decoded = body
            .replace(/=\r?\n/g, "")
            .replace(/=([\dA-F]{2})/gi, (_, hex: string) => String.fromCharCode(parseInt(hex, 16)));
          const match = decoded.match(new RegExp(`https?://[^\\s]+/${route}#token=[A-Za-z0-9_-]+`));
          if (match) {
            link = match[0];
            return true;
          }
        }
        return false;
      },
      { message: `A ${route} message is delivered to the local outbox`, timeout: 10_000 },
    )
    .toBe(true);
  return link;
}

async function signup(request: APIRequestContext, origin: string, email: string, name: string) {
  const response = await write(request, origin, "/auth/register", { name, email, password });
  expect(response.status()).toBe(201);
}

async function verify(request: APIRequestContext, origin: string, email: string) {
  expect((await write(request, origin, "/auth/verify-email/request", { email })).status()).toBe(
    202,
  );
  const url = new URL(await mailLink(email, "verify-email"));
  expect(
    (
      await write(request, origin, "/auth/verify-email/confirm", {
        token: new URLSearchParams(url.hash.slice(1)).get("token"),
      })
    ).ok(),
  ).toBe(true);
}

async function login(page: Page, email: string, secret = password) {
  await page.goto("/login");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(secret);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
}

test.beforeEach(() => {
  test.skip(
    process.env.FORGE_E2E_LIVE !== "1",
    "Identity workflows require the real Compose stack and local mail outbox",
  );
});

test("register, verify, create and switch organizations, then reset password", async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(90_000);
  const origin = new URL(baseURL!).origin;
  const suffix = randomUUID().slice(0, 8);
  const email = `browser-${suffix}@example.com`;
  const name = `Browser team ${suffix}`;
  await page.goto("/register");
  await page.getByLabel("Full name").fill("Browser Owner");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Create your organization" })).toBeVisible();
  await page.getByLabel("Organization name").fill(name);
  await page.getByRole("button", { name: "Create organization", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  const identity = await (await page.request.get("/api/v1/auth/me")).json();
  const firstId = identity.organizations[0].id;

  await page.goto("/app/account");
  await page.getByRole("button", { name: "Send verification link" }).click();
  await expect(page.getByRole("status").filter({ hasText: "verification link" })).toBeVisible();
  await page.goto(await mailLink(email, "verify-email"));
  await expect(page).toHaveURL(/\/verify-email$/);
  await page.getByRole("button", { name: "Verify email address" }).click();
  await expect(page.getByText("Your email address is verified.", { exact: true })).toBeVisible();

  await page.goto("/app/organizations/new");
  await page.getByLabel("Organization name").fill(`Second team ${suffix}`);
  await page.getByRole("button", { name: "Create organization", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await page.getByRole("combobox", { name: "Organization", exact: true }).selectOption(firstId);
  await page.getByRole("link", { name: "Organization settings", exact: true }).click();
  await expect(page.getByLabel("Organization name")).toHaveValue(name);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);

  const second = await browser.newContext({ baseURL });
  try {
    expect((await write(second.request, origin, "/auth/login", { email, password })).ok()).toBe(
      true,
    );
    await page.goto("/app/account");
    await page.getByRole("button", { name: "Revoke session", exact: true }).click();
    await expect(page.getByText("Session revoked. That browser must sign in again.")).toBeVisible();
    expect((await second.request.get("/api/v1/auth/me")).status()).toBe(401);
    await page.getByRole("button", { name: "Sign out", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Sign in to Forge" })).toBeVisible();
    await login(page, email);

    await page.goto("/forgot-password");
    await page.getByLabel("Email address", { exact: true }).fill(email);
    await page.getByRole("button", { name: "Send reset link" }).click();
    await expect(page.getByRole("status").filter({ hasText: "password reset link" })).toBeVisible();
    await page.goto(await mailLink(email, "reset-password"));
    const newPassword = `${password} changed`;
    await page.getByLabel("New password", { exact: true }).fill(newPassword);
    await page.getByLabel("Confirm new password", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Change password", exact: true }).click();
    await expect(
      page.getByText("Your password was changed. Sign in with your new password."),
    ).toBeVisible();
    await login(page, email, newPassword);
    expect((await (await page.request.get("/api/v1/auth/me")).json()).organizations).toHaveLength(
      2,
    );
  } finally {
    await second.close();
  }
});

test("invitation joins a verified teammate, role changes and removal take effect", async ({
  page,
  browser,
  baseURL,
}) => {
  test.setTimeout(90_000);
  const origin = new URL(baseURL!).origin;
  const suffix = randomUUID().slice(0, 8);
  const owner = `owner-${suffix}@example.com`;
  const teammate = `teammate-${suffix}@example.com`;
  await signup(page.request, origin, owner, "Team Owner");
  const created = await write(page.request, origin, "/organizations", {
    name: `Invite team ${suffix}`,
    slug: `invite-${suffix}`,
  });
  expect(created.status()).toBe(201);
  const organization = await created.json();
  await page.goto("/app/settings");
  await page.getByLabel("Teammate email").fill(teammate);
  await page.getByLabel("Invitation role").selectOption("member");
  await page.getByRole("button", { name: "Send invitation", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: `Invitation sent to ${teammate}` }),
  ).toBeVisible();
  const invitation = await mailLink(teammate, "invite");

  const joined = await browser.newContext({ baseURL });
  try {
    await signup(joined.request, origin, teammate, "Teammate");
    await verify(joined.request, origin, teammate);
    const memberPage = await joined.newPage();
    await memberPage.goto(invitation);
    await expect(memberPage).toHaveURL(/\/invite$/);
    await memberPage.getByRole("button", { name: "Accept invitation", exact: true }).click();
    await expect(
      memberPage.getByText(`You joined ${organization.name}.`, { exact: true }),
    ).toBeVisible();
    await memberPage.goto("/app/settings");
    await expect(memberPage.getByRole("heading", { name: "Organization settings" })).toBeVisible();
    await expect(
      memberPage.getByRole("button", { name: "Send invitation", exact: true }),
    ).toHaveCount(0);
    await page.reload();
    await page
      .getByRole("combobox", { name: `Role for ${teammate}`, exact: true })
      .selectOption("viewer");
    await expect(page.getByText("Role updated for Teammate.", { exact: true })).toBeVisible();
    const memberIdentity = await (await joined.request.get("/api/v1/auth/me")).json();
    expect(memberIdentity.organizations[0].role).toBe("viewer");
    await page.getByRole("button", { name: `Remove ${teammate}`, exact: true }).click();
    await page.getByRole("button", { name: "Confirm removal", exact: true }).click();
    await expect(
      page.getByRole("combobox", { name: `Role for ${teammate}`, exact: true }),
    ).toHaveCount(0);
    expect((await joined.request.get(`/api/v1/organizations/${organization.id}`)).status()).toBe(
      404,
    );
    await memberPage.goto("/app");
    await expect(
      memberPage.getByRole("heading", { name: "Create your organization" }),
    ).toBeVisible();
  } finally {
    await joined.close();
  }
});
