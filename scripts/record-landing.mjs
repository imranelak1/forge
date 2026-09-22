// Record the running, signed-out landing page; raw video stays in ignored .artifacts/.
import { chromium } from "@playwright/test";
import { mkdir, stat, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = fileURLToPath(new URL("../", import.meta.url));
const origin = new URL(process.env.FORGE_RECORD_ORIGIN ?? "http://localhost:3000");
if (!["localhost", "127.0.0.1"].includes(origin.hostname)) {
  throw new Error("Record a local Forge instance, without a signed-in browser session.");
}
const scratch = path.join(root, ".artifacts", "landing-recording");
const media = path.join(root, "docs", "media");
await mkdir(scratch, { recursive: true });
await mkdir(media, { recursive: true });

function ffmpeg(args) {
  const result = spawnSync("ffmpeg", args, { cwd: root, encoding: "utf8", windowsHide: true });
  if (result.error || result.status !== 0) {
    throw new Error(result.error?.message ?? result.stderr);
  }
}
ffmpeg(["-version"]);

const browser = await chromium.launch();
let video;
let trim;
let duration;
const errors = [];
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
    colorScheme: "dark",
    reducedMotion: "no-preference",
    recordVideo: { dir: scratch, size: { width: 1440, height: 1000 } },
  });
  const opened = Date.now();
  const page = await context.newPage();
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(origin.href, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForSelector('.core-renderer[data-renderer="svg"]');
  await page.waitForSelector('.landing[data-text-motion="ready"]');
  await page.mouse.move(1439, 999);
  await page.waitForTimeout(500);
  trim = (Date.now() - opened) / 1000;
  const started = Date.now();
  await page.evaluate(async () => {
    const hold = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const scroll = (top, duration) =>
      new Promise((resolve) => {
        const from = scrollY;
        const started = performance.now();
        function frame(now) {
          const t = Math.min(1, (now - started) / duration);
          const eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
          scrollTo({ top: from + (top - from) * eased, behavior: "instant" });
          if (t < 1) requestAnimationFrame(frame);
          else resolve();
        }
        requestAnimationFrame(frame);
      });
    await hold(1500);
    for (const chapter of document.querySelectorAll("[data-chapter]")) {
      await scroll(chapter.getBoundingClientRect().top + scrollY - innerHeight * 0.08, 1700);
      await hold(1700);
    }
    const tools = document.querySelector(".integration-section");
    await scroll(tools.getBoundingClientRect().top + scrollY - 50, 1300);
    await hold(1700);
    await scroll(0, 1500);
    await hold(1300);
  });
  duration = (Date.now() - started) / 1000;
  if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) {
    throw new Error("Landing overflows the recording viewport.");
  }
  if (errors.length) throw new Error(`Browser errors: ${errors.join("; ")}`);
  video = await page.video().path();
  await context.close();
} finally {
  await browser.close();
}

const output = path.join(media, "forge-landing.gif");
ffmpeg([
  "-hide_banner",
  "-loglevel",
  "error",
  "-y",
  "-ss",
  trim.toFixed(3),
  "-t",
  duration.toFixed(3),
  "-i",
  video,
  "-filter_complex",
  "fps=10,scale=840:-1:flags=lanczos,mpdecimate=hi=768:lo=320:frac=0.33,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
  "-loop",
  "0",
  output,
]);
const bytes = (await stat(output)).size;
const report = {
  source: origin.origin,
  output: "docs/media/forge-landing.gif",
  duration_seconds: Number(duration.toFixed(2)),
  width: 840,
  max_fps: 10,
  bytes,
  browser_errors: errors,
  raw_video: path.relative(root, video).replaceAll("\\", "/"),
  trim_seconds: Number(trim.toFixed(3)),
};
await writeFile(path.join(scratch, "capture.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify(report));
