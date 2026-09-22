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

test("SVG track draws, follows scroll and reverses without a permanent animation loop", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "svg");
  await expect(renderer).toHaveAttribute("data-moving", "false");
  const note = await page.locator(".preview-note").boundingBox();
  const firstStop = await renderer.locator('[data-checkpoint="0"]').boundingBox();
  expect(firstStop!.y).toBeGreaterThan(note!.y + note!.height);
  const initial = await renderer.locator(".track-art").screenshot();
  await goToChapter(page, "connect", 0.99);
  await goToChapter(page, "investigate", 3.99);
  await goToChapter(page, "automate", 4.99);
  const loop = await renderer.locator(".track-art").screenshot();
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
  if (process.env.FORGE_E2E_LIVE !== "1") {
    await page.route("**/api/v1/auth/**", (route) =>
      route.fulfill({
        status: route.request().url().endsWith("/csrf") ? 200 : 401,
        contentType: "application/json",
        body: JSON.stringify(
          route.request().url().endsWith("/csrf")
            ? { csrf_token: "test-only" }
            : { detail: "Sign in to continue." },
        ),
      }),
    );
  }
  await page.goto("/");
  const chapter = page
    .getByRole("navigation", { name: "Story chapters" })
    .getByRole("link", { name: "Understand" });
  await chapter.focus();
  await chapter.press("Enter");
  await expect(page).toHaveURL(/#understand$/);
  await expect(
    page.getByRole("heading", { name: "Make the failure understandable." }),
  ).toBeInViewport();
  await page.evaluate(() => scrollTo(0, 0));
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(17, 17, 17)");
  await page.getByRole("link", { name: "Forge home" }).click();
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "svg");
  await expect(page.locator(".core-renderer .track-art")).toHaveCount(1);
  await expect(page.locator(".landing")).toHaveCSS("background-color", "rgb(37, 36, 35)");
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
  await expect(page.locator(".track-art")).toBeVisible();
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await expect(renderer).toHaveAttribute("data-renderer", "svg");
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
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "svg");
  await expect(page.locator(".track-art")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open platform", exact: true })).toBeVisible();
});

test("headings and explanations scrub into view, exit, and reverse with scroll", async ({
  page,
}) => {
  await page.goto("/");
  const landing = page.locator(".landing");
  const scene = page.locator('[data-text-scene="connect"]');
  await expect(landing).toHaveAttribute("data-text-motion", "ready");
  const positionText = async (fraction: number) => {
    await scene.locator("h2").evaluate((heading, fraction) => {
      scrollTo(0, heading.getBoundingClientRect().top + scrollY - innerHeight * fraction);
    }, fraction);
    await expect(landing).toHaveAttribute("data-text-moving", "false");
  };
  const letter = scene.locator("[data-char]").first();
  const word = scene.locator("[data-text-copy] [data-word]").first();
  await positionText(0.76);
  await expect(scene).toHaveAttribute("data-text-state", "entering");
  const entrance = await letter.evaluate((el) => Number(getComputedStyle(el).opacity));
  expect(entrance).toBeGreaterThan(0);
  expect(entrance).toBeLessThan(1);
  await expect(word).not.toHaveCSS("transform", "none");
  await positionText(0.4);
  await expect(scene).toHaveAttribute("data-text-state", "visible");
  await expect(letter).toHaveCSS("opacity", "1");
  await expect(word).toHaveCSS("opacity", "1");
  await expect(scene.locator("h2")).toHaveAccessibleName("Connect the tools. Keep the context.");
  await positionText(0.14);
  await expect(scene).toHaveAttribute("data-text-state", "exiting");
  const leaving = await scene
    .locator("[data-char]")
    .evaluateAll(
      (letters) =>
        letters.reduce((sum, el) => sum + Number(getComputedStyle(el).opacity), 0) / letters.length,
    );
  expect(leaving).toBeGreaterThan(0);
  expect(leaving).toBeLessThan(1);
  await positionText(-0.05);
  await expect(scene).toHaveAttribute("data-text-state", "after");
  await expect(letter).toHaveCSS("opacity", "0");
  await expect(word).toHaveCSS("opacity", "0");
  // The explanation's box is still on screen: its departure is animation, not scrolling out.
  await expect(scene.locator("[data-text-copy]")).toBeInViewport();
  await positionText(0.4);
  await expect(scene).toHaveAttribute("data-text-state", "visible");
  await expect(letter).toHaveCSS("opacity", "1");
  await expect(word).toHaveCSS("opacity", "1");
  await positionText(0.76);
  await expect(scene).toHaveAttribute("data-text-state", "entering");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(landing).toHaveAttribute("data-text-motion", "static");
  await expect(page.locator("[data-char], [data-word]")).toHaveCount(0);
  await expect(scene.locator("[data-text-copy]")).toHaveText(
    "Bring a pull request, its CI run, test report and production error together. Forge is being built to link them by the change they share.",
  );
});

test("the SVG follower stays on its route after resizing", async ({ page }) => {
  await page.goto("/");
  await goToChapter(page, "automate", 4.99);
  for (const width of [390, 1024]) {
    await page.setViewportSize({ width, height: 844 });
    await goToChapter(page, "automate", 4.99);
    const distance = await page.locator(".track-art").evaluate((node) => {
      const svg = node as SVGSVGElement;
      const route = svg.querySelector<SVGPathElement>("[data-motion-route]")!;
      const packet = svg.querySelector<SVGGElement>(".track-packet")!;
      const end = route
        .getPointAtLength(route.getTotalLength())
        .matrixTransform(route.getScreenCTM()!);
      const center = new DOMPoint(0, 0).matrixTransform(packet.getScreenCTM()!);
      return Math.hypot(center.x - end.x, center.y - end.y);
    });
    expect(distance).toBeLessThan(1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
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
  await expect(page.locator(".track-art")).toBeVisible();
  await page.getByRole("link", { name: "Open platform", exact: true }).click();
  await expect(page.locator("noscript").getByRole("link", { name: "Sign in" })).toBeVisible();
  await context.close();
});

test("track checkpoints expose evidence and the commit follows the delivery story", async ({
  page,
}) => {
  await page.goto("/");
  const renderer = page.locator(".core-renderer");
  await expect(renderer).toHaveAttribute("data-renderer", "svg");
  await expect(renderer).toHaveAttribute("data-configuration", "commit-on-track");
  await expect(renderer.locator('[data-checkpoint="3"]')).toBeEnabled();
  await goToChapter(page, "connect", 0.99);
  const record = page.getByRole("button", { name: "Select Sentry checkpoint" });
  await record.focus();
  await record.press("Enter");
  await expect(record).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("#connect figcaption")).toContainText("sentry-event.json");
  await goToChapter(page, "understand", 2.99);
  await expect(renderer.locator(".track-detail")).toContainText("total(100, null)");
  await expect(renderer).toHaveAttribute("data-branch", "reproduction");
  await goToChapter(page, "investigate", 3.99);
  await expect(renderer.locator(".track-detail")).toContainText("coupon?.percent ?? 0");
  for (const checkpoint of await renderer.getByRole("button").all()) {
    await expect(checkpoint).toBeInViewport({ ratio: 1 });
  }
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-journey")))
    .toBeGreaterThan(2.99);
  await goToChapter(page, "automate", 4.99);
  await expect(renderer.locator(".track-detail")).toContainText("Human review required");
  await expect(renderer).toHaveAttribute("data-branch", "review");
  await expect
    .poll(async () => Number(await renderer.getAttribute("data-journey")))
    .toBeGreaterThan(3.99);
  await page.getByRole("button", { name: "Restart story", exact: true }).click();
  await expect(renderer).toHaveAttribute("data-configuration", "commit-on-track");
  await expect(renderer).toHaveAttribute("data-moving", "false");
});

test("scrubber navigates the story and authentic local integration logos load", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "svg");
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
    "rgb(180, 177, 175)",
  );
  await expect(page.locator("#connect .chapter-endpoint > p")).toHaveCSS(
    "color",
    "rgb(180, 177, 175)",
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

test("code previews explain every step and tool selection copies the displayed example", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.goto("/");
  await expect(page.locator(".code-preview")).toHaveCount(5);
  await expect(page.locator("#trace pre")).toContainText("npm test");
  await expect(page.locator("#understand pre")).toContainText("total(100, null)");
  await expect(page.locator("#investigate pre")).toContainText("coupon?.percent ?? 0");
  await expect(page.locator("#automate .example-note")).toContainText("not a published Forge API");
  await page
    .locator("#connect")
    .getByRole("button", { name: "Inspect GitHub Actions", exact: true })
    .click();
  await expect(page.locator("#connect figcaption")).toContainText("workflow_run.json");
  await expect(page.locator("#connect .preview-result")).toContainText("CI run #928");
  await page.getByRole("button", { name: "Copy workflow_run.json", exact: true }).click();
  await expect(page.locator("#connect [role=status]")).toHaveText("Example copied");
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain('"run_number": 928');
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator(".core-renderer")).toHaveAttribute("data-renderer", "static");
  await expect(page.locator(".code-preview")).toHaveCount(5);
});
