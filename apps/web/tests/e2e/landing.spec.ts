import { expect, test, type Page } from "@playwright/test";

async function goToChapter(page: Page, id: string, progress: number) {
  await page
    .locator(`#${id}`)
    .evaluate((element) => scrollTo(0, element.getBoundingClientRect().top + scrollY));
  await expect(page.locator(".cable-stage")).toHaveAttribute("data-active", id);
  await expect
    .poll(async () => Number(await page.locator(".cable-renderer").getAttribute("data-progress")))
    .toBeGreaterThan(progress);
  await expect(page.locator(".cable-renderer")).toHaveAttribute("data-moving", "false");
}

test("WebGL cable renders, changes with scroll and reverses without a permanent render loop", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const renderer = page.locator(".cable-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  await expect(renderer).toHaveAttribute("data-moving", "false");
  const initial = await renderer.locator("canvas").screenshot();
  await goToChapter(page, "connect", 0.99);
  await goToChapter(page, "investigate", 3.99);
  await goToChapter(page, "automate", 4.99);
  const loop = await renderer.locator("canvas").screenshot();
  expect(initial.equals(loop)).toBe(false);
  await page.evaluate(() => scrollTo(0, 0));
  await expect(renderer).toHaveAttribute("data-moving", "false");
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-progress")))
    .toBeLessThan(0.01);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test("chapter links and platform navigation work with the landing palette scoped", async ({
  page,
}) => {
  await page.goto("/");
  const chapter = page
    .getByRole("navigation", { name: "Story chapters" })
    .getByRole("link", { name: "Understand" });
  await chapter.focus();
  await chapter.press("Enter");
  await expect(page).toHaveURL(/#understand$/);
  await expect(
    page.getByRole("heading", { name: "See what’s holding you back." }),
  ).toBeInViewport();
  await page.evaluate(() => scrollTo(0, 0));
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(17, 17, 17)");
  await page.getByRole("link", { name: "Forge home" }).click();
  await expect(page.locator(".cable-renderer")).toHaveAttribute("data-renderer", "webgl");
  await expect(page.locator(".cable-renderer canvas")).toHaveCount(1);
  await expect(page.locator(".landing")).toHaveCSS("background-color", "rgb(250, 250, 250)");
});

test("reduced motion uses static artwork and supports live preference changes", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const renderer = page.locator(".cable-renderer");
  await expect(renderer).toHaveAttribute("data-reduced-motion", "true");
  await expect(renderer).toHaveAttribute("data-renderer", "static");
  await expect(renderer.locator("canvas")).toHaveCount(0);
  await expect(page.locator(".cable-fallback")).toBeVisible();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(renderer).toHaveAttribute("data-renderer", "static");
  await expect(renderer.locator("canvas")).toHaveCount(0);
});

test("unavailable WebGL preserves the artwork and content", async ({ page }) => {
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    Object.defineProperty(HTMLCanvasElement.prototype, "getContext", {
      value: function (this: HTMLCanvasElement, type: string, ...args: unknown[]) {
        return type.includes("webgl") ? null : Reflect.apply(original, this, [type, ...args]);
      },
    });
  });
  await page.goto("/");
  await expect(page.locator(".cable-renderer")).toHaveAttribute("data-renderer", "fallback");
  await expect(page.locator(".cable-fallback")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open platform", exact: true })).toBeVisible();
});

test("WebGL context loss falls back and restores without duplicate canvases", async ({ page }) => {
  await page.goto("/");
  const renderer = page.locator(".cable-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  await renderer.locator("canvas").evaluate((node) => {
    const canvas = node as HTMLCanvasElement & { testContext?: WEBGL_lose_context };
    const extension = canvas.getContext("webgl2")?.getExtension("WEBGL_lose_context");
    if (!extension) throw new Error("Test requires WEBGL_lose_context");
    canvas.testContext = extension;
    extension.loseContext();
  });
  await expect(renderer).toHaveAttribute("data-renderer", "fallback");
  await expect(page.locator(".cable-fallback")).toBeVisible();
  await renderer
    .locator("canvas")
    .evaluate((node) =>
      (
        node as HTMLCanvasElement & { testContext?: WEBGL_lose_context }
      ).testContext?.restoreContext(),
    );
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  await expect(renderer.locator("canvas")).toHaveCount(1);
});

test("the tour remains readable and navigable without JavaScript", async ({
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
  await expect(page.locator(".cable-fallback")).toBeVisible();
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await context.close();
});
