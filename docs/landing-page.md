# Landing page: follow the change

The public home page follows one checkout change through a connected delivery investigation. A persistent pull request joins its CI run, tests and production error, then exposes the evidence behind a proposed review request. Native HTML records preserve readable source identities while Three.js relationship paths and an Anime.js timeline animate their connections. The [Anime.js palette](https://animejs.com/) remains warm charcoal, off-white, coral controls and warm stone integrations.

## Story and examples

| Step        | Visible action                                                           | Customer explanation                                                                      |
| ----------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Connect     | Four source records connect around their shared commit.                  | Select sample GitHub, Actions, JUnit and Sentry events for PR #184 and commit 8f3a2c1.    |
| Trace       | Records arrange into a delivery trail; a packet follows the connections. | CI YAML links the change, original run #928 and release.                                  |
| Understand  | The regression report opens within the same diagram.                     | A developer-added null-coupon test reproduces the production error in run #929.           |
| Investigate | The production error and candidate fix open side by side.                | Review the related code, then verify a proposed null guard with the failing test.         |
| Automate    | The evidence sources collect above a review request.                     | Illustrative logic proposes a review when tests fail; a person decides what happens next. |

Each preview contains selectable code, syntax highlighting, evidence lines, an explanation and a copy control with success/failure feedback. Long lines scroll locally. Examples are sample data and proposed behavior, never live customer data, functioning integration claims or a published Forge rule API. The original test report predates the regression reproduction; a related commit alone is not proof of causality. SHA values are marked as abbreviated. Event structures follow [GitHub's workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [Sentry's exception representation](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

## Implementation and interaction

- core-model.ts creates four cubic B?zier relationship paths and a packet marker. A GLSL highlight follows the active segment. Paths interpolate between chapter layouts.
- core-choreography.ts defines five persistent records and their layouts. core-scene.tsx binds them to one paused Anime.js timeline with native scroll, damping and a keyboard-accessible story range. Restart returns to the opening pull request. Reverse scrolling reverses the sequence; rendering stops at rest.
- delivery-records.tsx and delivery-records.css render native source records, selection states, expanded evidence and the final illustrative review request. Hidden records are inert.
- code-preview.tsx supplies the five readable examples, source selection, token rendering, highlight feedback and clipboard behavior.
- text-motion.tsx reveals headings in 340ms with 35ms between lines; supporting copy starts immediately and finishes in 320ms. Text stays nearly opaque throughout. Passages can replay after leaving the viewport completely. Motion preferences, focus, exit and tab visibility finish or revert active animation.
- landing.css scopes the marketing palette and layout. The desktop grid has a 35% central illustration column; mobile places copy and code below the diagram. The whole mobile reading area has an opaque background. Short viewports retain code previews. Story resize observation keeps scroll mapping aligned when a source preview changes height.

Rendering stops at rest, outside the story and in hidden tabs. Pixel ratios are capped at 1.6 desktop / 1.25 mobile. Resources, timelines, listeners, observers and the WebGL context are disposed on teardown. All copy, code and native anchors are server-rendered. A labeled static SVG delivery diagram remains for no JavaScript, reduced motion, WebGL failure and context loss; live preferences and context restoration are supported. The canvas is decorative; native record buttons expose source names and pressed states, and hidden records are inert. Controls retain focus treatment.

Initial integrations remain GitHub, Actions, JUnit reports and Sentry, in development. Roadmap logos remain in their separate labeled section. Source provenance is in apps/web/public/integrations/SOURCES.md. The working application at /app, /guide, /system and API endpoints retain their existing behavior. A future 3D logo and Phase 2 backend remain separate work.

## Run and verify

Run docker compose up -d --build --no-deps frontend, then open [the landing](http://localhost:3000). Development runs with npm run dev --workspace @forge/web -- --port 3100.

Lint, typecheck, production build and Playwright cover navigation, rendering, reversible motion, source selection, clipboard, reduced motion, WebGL failure/restoration and the actual Compose readiness endpoint. Set PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 and FORGE_E2E_LIVE=1 for production browser checks. Chromium uses two workers and software WebGL in tests; these checks do not establish real-device frame rates or Safari/Firefox compatibility.
