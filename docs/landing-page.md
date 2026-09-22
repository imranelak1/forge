# Landing page: the SVG delivery path

The public home page follows one illustrative checkout commit along a centered SVG line. The line draws between authentic GitHub, Actions, JUnit and Sentry logos, with a coral code packet following the same path. Its authored bracket glyph identifies the moving change. The [Anime.js palette](https://animejs.com/) remains warm charcoal, off-white, coral controls and warm stone integrations.

## Story and examples

| Step        | Path action                                                  | Explanation                                                                                        |
| ----------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Connect     | The coral line draws through four tool checkpoints.          | Select sample events for PR #184 and commit 8f3a2c1.                                               |
| Trace       | The code packet follows the path from code to production.    | CI #928 and the original tests pass before the production error.                                   |
| Understand  | The code packet returns to the test checkpoint.              | A new no-coupon regression test reproduces the failure in CI #929.                                 |
| Investigate | The code packet traces back to the pull request.             | Review a candidate null guard and verify it with the failing test.                                 |
| Automate    | The code packet follows the evidence to the review endpoint. | A proposed review request includes the commit and failed test; a person decides what happens next. |

Code previews retain selectable syntax-highlighted examples, evidence lines, source selection and copy feedback. They are sample data and proposed behavior, not live integrations or a published Forge API. The original test report predates the regression reproduction; a related commit alone is not proof of causality. Event structures follow [GitHub workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [Sentry exceptions](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

## Animation and interaction

`core-scene.tsx` uses Anime.js [createDrawable](https://animejs.com/documentation/svg/createdrawable/) to draw the line and [createMotionPath](https://animejs.com/documentation/svg/createmotionpath/) for the code packet coordinates. The drawn line is 4 SVG units thick over a 2.5-unit guide. The coral packet is 32 by 22 SVG units with a native bracket glyph; its center and the path share one SVG viewBox, preserving alignment after resize. A paused five-part timeline is driven by native scrolling with bounded, frame-rate-independent smoothing. Reverse scrolling retraces the path. The keyboard-accessible range and Restart control seek native scroll. ResizeObserver keeps chapter mapping aligned when a source preview changes height. Animation frames stop at rest, outside the story and in hidden tabs.

`track-labels.tsx` and its stylesheet provide native checkpoint buttons with authentic source logos, names, pressed states and keyboard focus. Labels sit 15px below the path to leave room for the code packet. Selection changes the Connect preview and source explanation. Checkpoint controls remain available throughout the story. Contextual captions explain the regression, candidate fix and review request.

`text-motion.tsx` uses Anime.js [splitText](https://animejs.com/documentation/text/splittext/) with persistent clipped heading characters and explanatory words. Each passage has a paused entrance, reading interval and exit timeline; native scrolling continuously seeks it with bounded smoothing. Text animates in, stays readable, then animates out as scrolling continues. Reverse scrolling plays those same states backward. Chapter evidence metadata animates in and out with its explanation. Investigate reverses the heading travel direction. The visible hero animates in on initialization. Reading thresholds account for paragraph height; resize lets words reflow and recalculates those thresholds. Focus reveals a visible passage. Splits remain in place during the tour and hidden tabs suspend frames. Reduced motion and unmount revert timelines and restore the original unsplit text. Server-rendered text is readable before initialization or with JavaScript disabled.

The same SVG is present with JavaScript disabled. Reduced motion shows the complete path, updates chapter state immediately and leaves text unsplit. Preference changes work without reloading. WebGL, Three.js and the earlier rail geometry are removed. Timelines, frames, listeners and observers are cleaned up on unmount.

`landing.css` scopes the palette and layout. A flex column prevents the sticky layers' negative margins from displacing the hero. The desktop grid keeps a central illustration column; chapter copy allows 336px to retain the intended heading lines with character splits. Mobile places the track above the chapter copy and code; short viewports use normal document flow. Tool logos remain labeled as initial integrations in development or roadmap items. Provenance is in `apps/web/public/integrations/SOURCES.md`.

## Verification

Run `docker compose up -d --build --no-deps frontend`, then open [the landing](http://localhost:3000). Development uses `npm run dev --workspace @forge/web -- --port 3100`.

Lint, typecheck, production build and Playwright cover the drawn SVG, reversible scroll, resize alignment, distinct heading and paragraph animation, source selection, clipboard, navigation, no-JavaScript content, live reduced-motion changes and Compose readiness. For production tests set `PLAYWRIGHT_BASE_URL=http://localhost:3000` and `FORGE_E2E_LIVE=1` before `npm run test:e2e`. Desktop and mobile Chromium checks do not establish real-device frame rates or Safari/Firefox compatibility.

The approved landing implementation is preserved by Phase 2. **Open platform** now reaches the protected workspace and sends signed-out users to the real sign-in flow. The landing remains readable without JavaScript; workspace account operations require it. The future 3D logo remains separate work. See [the Phase 2 handoff](phase-2-review.md) for account and tenant behavior.

Verified on 2026-09-22: lint, typecheck, production Docker build and all 30 desktop/mobile Chromium tests passed. The text test verifies partial entrance, a fully readable interval, animated departure while the paragraph box remains on screen, reverse scrolling and reduced-motion restoration. Desktop/mobile visual review confirmed the thicker path, code packet, label clearance and restored heading line breaks. The design detector reported no primary findings; advisory type sizes and colors belong to the established landing palette and typography.
