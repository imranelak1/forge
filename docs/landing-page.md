# Landing page: the delivery track

The public home page follows one illustrative checkout commit along a dimensional track. Two metallic rails draw through GitHub, Actions, JUnit and Sentry checkpoints. A coral carrier follows the continuous route into a production error, then branches into reproduction, investigation and human review. All geometry is procedural; native source logos remain sharp. The [Anime.js palette](https://animejs.com/) remains warm charcoal, off-white, coral controls and warm stone integrations.

## Story and examples

| Step        | Track action                                                         | Customer explanation                                                                                |
| ----------- | -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Connect     | Rails draw through four tool checkpoints.                            | Select sample events for PR #184 and commit 8f3a2c1.                                                |
| Trace       | The coral commit carrier travels through build, tests and release.   | CI #928 and the original test suite pass before the production error.                               |
| Understand  | A continuous branch leads from the error to reproduction.            | A new no-coupon regression test reproduces the failure in CI #929.                                  |
| Investigate | The return route leads back toward the related code.                 | Review a candidate null guard and verify it with the failing test.                                  |
| Automate    | A junction tongue opens before the carrier enters the review branch. | A proposed review request includes the commit and failing test; a person decides what happens next. |

Each preview contains selectable code, syntax highlighting, evidence lines, an explanation and a copy control with success/failure feedback. Long lines scroll locally. Examples are sample data and proposed behavior, never live customer data, functioning integration claims or a published Forge rule API. The original test report predates the regression reproduction; a related commit alone is not proof of causality. SHA values are marked as abbreviated. Event structures follow [GitHub's workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [Sentry's exception representation](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

## Implementation and interaction

- core-model.ts builds connected Catmull-Rom routes, beveled rails, beds, instanced sleepers, light-bar checkpoints, a wheeled carrier and a pivoting junction. Custom GLSL reveals the rails and emphasizes the active route. The carrier uses curve distance and a tangent-aligned frame, including track elevation.
- core-choreography.ts defines the track and journey state. core-scene.tsx binds it to a paused Anime.js timeline with native scroll, damping and a keyboard-accessible story range. Each branch shares an endpoint with the preceding route. The view remains fixed; reversing scroll retraces the journey. Restart returns to the opening track.
- track-labels.tsx and track-labels.css supply native checkpoint controls, a commit label, contextual evidence captions and a static SVG track. Checkpoint labels move into a compact logo row as the branches open. Hidden checkpoints are inert.
- code-preview.tsx supplies the five readable examples, source selection, token rendering, highlight feedback and clipboard behavior.
- text-motion.tsx reveals headings in 340ms with 35ms between lines; supporting copy starts immediately and finishes in 320ms. Text stays nearly opaque throughout. Passages can replay after leaving the viewport completely. Motion preferences, focus, exit and tab visibility finish or revert active animation.
- landing.css scopes the marketing palette and layout. The desktop grid has a 35% central illustration column; mobile places copy and code below the track. The whole mobile reading area has an opaque background. Short viewports retain code previews. Story resize observation keeps scroll mapping aligned when a source preview changes height.

Rendering stops at rest, outside the story and in hidden tabs. Pixel ratios are capped at 1.6 desktop / 1.25 mobile. Resources, timelines, listeners, observers and the WebGL context are disposed on teardown. All copy, code and native anchors are server-rendered. A labeled static SVG track remains for no JavaScript, reduced motion, WebGL failure and context loss; live preferences and context restoration are supported. The canvas is decorative; native checkpoint buttons expose source names and pressed states, and hidden checkpoints are inert. Controls retain focus treatment.

Initial integrations remain GitHub, Actions, JUnit reports and Sentry, in development. Roadmap logos remain in their separate labeled section. Source provenance is in apps/web/public/integrations/SOURCES.md. The working application at /app, /guide, /system and API endpoints retain their existing behavior. A future 3D logo and Phase 2 backend remain separate work.

## Run and verify

Run docker compose up -d --build --no-deps frontend, then open [the landing](http://localhost:3000). Development runs with npm run dev --workspace @forge/web -- --port 3100.

Lint, typecheck, production build and Playwright cover navigation, rendering, reversible motion, source selection, clipboard, reduced motion, WebGL failure/restoration and the actual Compose readiness endpoint. Set PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 and FORGE_E2E_LIVE=1 for production browser checks. Chromium uses two workers and software WebGL in tests; these checks do not establish real-device frame rates or Safari/Firefox compatibility.
