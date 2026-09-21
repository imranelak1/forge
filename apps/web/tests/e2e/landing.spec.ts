import { expect, test, type Page } from "@playwright/test";

async function assembleChapter(page: Page, id: string) {
  await page.locator(`#${id}`).evaluate((element) => {
    const bounds = element.getBoundingClientRect();
    const anchor = innerHeight * (innerWidth < 900 ? 0.68 : 0.52);
    const span = Math.min(bounds.height * 0.7, innerHeight * 0.65);
    scrollTo(0, bounds.top + scrollY - anchor + span * 0.95);
  });
  await expect(page.locator(".board-stage")).toHaveAttribute("data-active", id);
}

test("circuit assembles in order and reverses with native scrolling", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Every change.Every signal.Connected.",
  );
  await expect(page.locator(".board-stage")).toHaveAttribute("data-progress", "0");
  for (let i = 0; i < 5; i++) await expect(page.locator(`.module-${i}`)).toHaveCSS("opacity", "0");
  await assembleChapter(page, "connect");
  await expect(page.locator(".module-0")).toHaveCSS("opacity", "1");
  await expect(page.locator(".module-1")).toHaveCSS("opacity", "0");
  await assembleChapter(page, "investigate");
  await expect(page.locator(".incident-path")).toHaveCSS("stroke-dashoffset", "0px");
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "0");
  await assembleChapter(page, "automate");
  for (let i = 0; i < 5; i++) await expect(page.locator(`.module-${i}`)).toHaveCSS("opacity", "1");
  await expect(page.locator(".incident-path")).toHaveCSS("opacity", "0");
  await page.evaluate(() => scrollTo(0, 0));
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "0");
  await expect(page.locator(".module-0")).toHaveCSS("opacity", "0");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("chapter links, keyboard highlights and platform navigation work", async ({ page }) => {
  await page.goto("/");
  const chapter = page
    .getByRole("navigation", { name: "Circuit chapters" })
    .getByRole("link", { name: /Understand/ });
  await chapter.focus();
  await expect(page.locator(".board-stage")).toHaveAttribute("data-highlight", "understand");
  await chapter.press("Enter");
  await expect(page).toHaveURL(/#understand$/);
  await expect(
    page.getByRole("heading", { name: "Find where progress gets stuck." }),
  ).toBeInViewport();
  await page.evaluate(() => scrollTo(0, 0));
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await page.getByRole("link", { name: "Forge home" }).click();
  await expect(page.locator(".board-stage")).toHaveAttribute("data-progress", "0");
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "0");
});

test("reduced motion shows a complete static board and responds to preference changes", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator(".board-stage")).toHaveAttribute("data-reduced-motion", "true");
  for (let i = 0; i < 5; i++) await expect(page.locator(`.module-${i}`)).toHaveCSS("opacity", "1");
  await expect(page.locator(".circuit-object")).toHaveCSS("transform", "none");
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "0");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "1");
});

test("the tour and its links remain available without JavaScript", async ({
  browser,
  baseURL,
}, testInfo) => {
  const context = await browser.newContext({
    javaScriptEnabled: false,
    viewport: testInfo.project.use.viewport,
  });
  const page = await context.newPage();
  await page.goto(`${baseURL}/`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".module-4")).toHaveCSS("opacity", "1");
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await context.close();
});
