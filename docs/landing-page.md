# Landing page: the SVG delivery path

The public home page follows one illustrative checkout commit along a clean SVG line. The line draws between authentic GitHub, Actions, JUnit and Sentry logos, with a coral marker following the same path. The [Anime.js palette](https://animejs.com/) remains warm charcoal, off-white, coral controls and warm stone integrations.

## Story and examples

| Step        | Path action                                             | Explanation                                                                                        |
| ----------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Connect     | The coral line draws through four tool checkpoints.     | Select sample events for PR #184 and commit 8f3a2c1.                                               |
| Trace       | The marker follows the path from code to production.    | CI #928 and the original tests pass before the production error.                                   |
| Understand  | The marker returns to the test checkpoint.              | A new no-coupon regression test reproduces the failure in CI #929.                                 |
| Investigate | The marker traces back to the pull request.             | Review a candidate null guard and verify it with the failing test.                                 |
| Automate    | The marker follows the evidence to the review endpoint. | A proposed review request includes the commit and failed test; a person decides what happens next. |

Code previews retain selectable syntax-highlighted examples, evidence lines, source selection and copy feedback. They are sample data and proposed behavior, not live integrations or a published Forge API. The original test report predates the regression reproduction; a related commit alone is not proof of causality. Event structures follow [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [Sentry exceptions](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

## Animation and interaction

`core-scene.tsx` uses Anime.js [createDrawable](https://animejs.com/documentation/svg/createdrawable/) to draw the line and [createMotionPath](https://animejs.com/documentation/svg/createmotionpath/) for the follower's coordinates. The follower is inside the same SVG viewBox as the path, preserving alignment after resize. A paused five-part timeline is driven by native scrolling with bounded, frame-rate-independent smoothing. Reverse scrolling retraces the path. The keyboard-accessible range and Restart control seek native scroll. ResizeObserver keeps chapter mapping aligned when a source preview changes height. Animation frames stop at rest, outside the story and in hidden tabs.

`track-labels.tsx` and its stylesheet provide native checkpoint buttons with authentic source logos, names, pressed states and keyboard focus. Selection changes the Connect preview and source explanation. Checkpoint controls remain available throughout the story. Contextual captions explain the regression, candidate fix and review request.

`text-motion.tsx` uses Anime.js [splitText](https://animejs.com/documentation/text/splittext/). Heading characters rise through clipped word wrappers, with a reversed entrance for Investigate. Explanations reveal word by word through clipping masks. Headings use 440ms plus at most 180ms of stagger; supporting words start after 60ms, use 330ms and at most 230ms of stagger. Both finish within 620ms. Original DOM is restored on completion, exit, focus, resize, hidden tabs and cleanup. Re-entry can replay after the passage fully leaves the viewport. Text remains server-rendered and readable before initialization.

The same SVG is present with JavaScript disabled. Reduced motion shows the complete path, updates chapter state immediately and leaves text unsplit. Preference changes work without reloading. WebGL, Three.js and the earlier rail geometry are removed. Timelines, frames, listeners and observers are cleaned up on unmount.

`landing.css` scopes the palette and layout. A flex column prevents the sticky layers' negative margins from displacing the hero. The desktop grid keeps a central illustration column. Mobile places the track above the chapter copy and code; short viewports use normal document flow. Tool logos remain labeled as initial integrations in development or roadmap items. Provenance is in `apps/web/public/integrations/SOURCES.md`.

## Verification

Run `docker compose up -d --build --no-deps frontend`, then open [the landing](http://localhost:3000). Development uses `npm run dev --workspace @forge/web -- --port 3100`.

Lint, typecheck, production build and Playwright cover the drawn SVG, reversible scroll, resize alignment, distinct heading and paragraph animation, source selection, clipboard, navigation, no-JavaScript content, live reduced-motion changes and Compose readiness. For production tests set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` and `FORGE_E2E_LIVE=1` before `npm run test:e2e`. Desktop and mobile Chromium checks do not establish real-device frame rates or Safari/Firefox compatibility.

The working `/app`, `/guide`, `/system` and API behavior retain their existing scope. A future 3D logo and Phase 2 backend remain separate work.

Verified on 2026-09-22: lint, typecheck, production Docker build and all 30 desktop/mobile Chromium tests passed. The visual review covered desktop, mobile, tablet and short landscape layouts. The design detector reported no primary findings; its advisory type sizes and accent colors belong to the existing landing typography and palette.
