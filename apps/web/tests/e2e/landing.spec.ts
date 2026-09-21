import { expect, test, type Page } from "@playwright/test";

async function goToChapter(page: Page, id: string, progress: number) {
  await page
    .locator(`#${id}`)
    .evaluate((element) => scrollTo(0, element.getBoundingClientRect().top + scrollY));
  await expect(page.locator(".core-stage")).toHaveAttribute("data-active", id);
  await expect
    .poll(async () => Number(await page.locator(".core-renderer").getAttribute("data-progress")))
    .toBeGreaterThan(progress);
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-moving", "false");
}

test("WebGL core renders, changes with scroll and reverses without a permanent render loop", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
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
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "webgl");
  await expect(page.locator(".core-renderer canvas")).toHaveCount(1);
  await expect(page.locator(".landing")).toHaveCSS("background-color", "rgb(250, 250, 250)");
});

test("reduced motion uses static artwork and supports live preference changes", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
  await expect(renderer).toHaveAttribute("data-reduced-motion", "true");
  await expect(renderer).toHaveAttribute("data-renderer", "static");
  await expect(renderer.locator("canvas")).toHaveCount(0);
  await expect(page.locator(".core-fallback")).toBeVisible();
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
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "fallback");
  await expect(page.locator(".core-fallback")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open platform", exact: true })).toBeVisible();
});

test("WebGL context loss falls back and restores without duplicate canvases", async ({ page }) => {
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  await renderer.locator("canvas").evaluate((node) => {
    const canvas = node as HTMLCanvasElement & { testContext?: WEBGL_lose_context };
    const extension = canvas.getContext("webgl2")?.getExtension("WEBGL_lose_context");
    if (!extension) throw new Error("Test requires WEBGL_lose_context");
    canvas.testContext = extension;
    extension.loseContext();
  });
  await expect(renderer).toHaveAttribute("data-renderer", "fallback");
  await expect(page.locator(".core-fallback")).toBeVisible();
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
  await expect(page.locator(".core-fallback")).toBeVisible();
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Engineering overview" })).toBeVisible();
  await context.close();
});

test("the core responds to keyboard rotation, drag and reset", async ({ page }) => {
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "webgl");
  const grip = page.getByRole("button", { name: "Rotate mechanical core", exact: false });
  await grip.focus();
  await grip.press("ArrowRight");
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-rotation")))
    .toBeGreaterThan(0.19);
  const bounds = await grip.boundingBox();
  if (!bounds) throw new Error("Missing rotation control");
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width / 2 + 55, bounds.y + bounds.height / 2, {
    steps: 8,
  });
  await page.mouse.up();
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-rotation")))
    .toBeGreaterThan(0.5);
  await page.getByRole("button", { name: "Reset core rotation", exact: true }).click();
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-rotation")))
    .toBeLessThan(0.01);
});

test("scrubber navigates the story and authentic local integration logos load", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "webgl");
  await page.getByRole("button", { name: "Sentry", exact: true }).click();
  await expect(page.locator(".core-port-note")).toContainText("Production errors and releases");
  const range = page.getByRole("slider", { name: "Story progress" });
  await range.focus();
  await range.press("End");
  await expect(page.locator(".core-stage")).toHaveAttribute("data-active", "automate");
  await range.press("Home");
  await expect(page.locator(".core-stage")).toHaveAttribute("data-active", "intro");
  await page
    .locator("#connect")
    .evaluate((el) => scrollTo(0, el.getBoundingClientRect().top + scrollY));
  await page
    .locator("#connect")
    .getByRole("button", { name: "Inspect GitHub Actions", exact: true })
    .click();
  await expect(page.locator("#connect .tool-explanation")).toContainText("Workflow runs");
  await page.locator(".integration-section").scrollIntoViewIfNeeded();
  await expect(
    page.getByRole("heading", { name: "Initial integrations (in development)" }),
  ).toBeVisible();
  await expect
    .poll(() =>
      page
        .locator(".integration-section img")
        .evaluateAll(
          (nodes) =>
            nodes.length === 12 &&
            nodes.every(
              (node) =>
                (node as HTMLImageElement).complete && (node as HTMLImageElement).naturalWidth > 0,
            ),
        ),
    )
    .toBe(true);
});

test("story controls clear the integration heading and workflow copy keeps contrast", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator("#connect .tool-explanation p")).toHaveCSS(
    "color",
    "rgb(102, 102, 102)",
  );
  await expect(page.locator("#connect .chapter-endpoint > p")).toHaveCSS(
    "color",
    "rgb(102, 102, 102)",
  );
  await page
    .locator(".integration-section")
    .evaluate((el) => scrollTo(0, el.getBoundingClientRect().top + scrollY));
  await expect
    .poll(() =>
      page.locator(".core-stage-footer").evaluate((el) => el.getBoundingClientRect().bottom),
    )
    .toBeLessThanOrEqual(1);
  await expect(
    page.getByRole("heading", { name: "Built around your engineering stack." }),
  ).toBeInViewport();
});

test("illustrated delivery plays forward and investigation reverses to its source", async ({
  page,
}) => {
  await page.goto("/");
  await page.locator("#connect").scrollIntoViewIfNeeded();
  await page.locator("#connect").getByRole("button", { name: "Play a delivery example" }).click();
  await expect(page.locator("#connect .flow-demo")).toHaveAttribute("data-playing", "false");
  await expect(page.locator("#connect .tool-explanation strong")).toHaveText("Sentry");
  await page.locator("#investigate").scrollIntoViewIfNeeded();
  await page
    .locator("#investigate")
    .getByRole("button", { name: "Trace an example backward" })
    .click();
  await expect(page.locator("#investigate .flow-demo")).toHaveAttribute("data-playing", "false");
  await expect(page.locator("#investigate .tool-explanation strong")).toHaveText("GitHub");
});
