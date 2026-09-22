# Landing recording

[`forge-landing.gif`](forge-landing.gif) records the actual signed-out Forge landing page: the introduction, five animated delivery chapters, integration logos and return to the introduction. The sample events belong to the landing's illustrative story, not an imported customer repository.

The looping GIF is approximately 24 seconds, 840 × 583 pixels and 4.2 MiB. A limited palette, duplicate-frame removal and cropped frame differences keep the recording small. No audio, additional video download or external media host is required by the main README.

To regenerate it, start Forge at `http://localhost:3000`, install the project's Node dependencies and Chromium, and ensure `ffmpeg` is on your PATH:

```sh
npm ci
npx playwright install chromium
node scripts/record-landing.mjs
```

For another local port, set `FORGE_RECORD_ORIGIN` before running the script. The recorder uses a fresh browser context without account cookies and refuses non-local hostnames. Raw video and capture metadata stay in ignored `.artifacts/landing-recording/`; only the optimized GIF is included in the repository. The landing implementation and its accessibility behavior are described in [the landing handoff](../landing-page.md).
