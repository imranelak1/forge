# Landing page: optical payload to satellite

The public home page explains Forge with a persistent optical payload that assembles into an observation satellite. The user's [Conceptzilla reference](https://dribbble.com/shots/16467758-Satellite-Landing-Page-Animation) informs the exploded hardware, shared assembly axis and part callouts. All shipping geometry is authored procedurally; the reference video is not a shipping asset. The [Anime.js palette](https://animejs.com/) remains warm charcoal, off-white, coral controls and warm stone integrations.

## Story and examples

| Step        | Physical action                                    | Customer explanation                                                                                  |
| ----------- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Connect     | Electronics dock around the optical payload.       | Switch between sample GitHub, Actions, JUnit and Sentry data for PR #184 and commit 8f3a2c1.          |
| Trace       | The stack connects and a signal traverses its bus. | CI YAML and a delivery trail link the commit, run #928 and release.                                   |
| Understand  | The stack separates and the aperture opens.        | A developer-added null-coupon regression test reproduces the production error in run #929.            |
| Investigate | The payload slides out along its mounts.           | Inspect a candidate null-guard fix against the related change and verify it with the regression test. |
| Automate    | Components seat; panels and antenna deploy.        | Illustrative TypeScript requests review when evidence contains failures; a person decides what ships. |

Each preview contains selectable code, syntax highlighting, evidence lines, an explanation and a copy control with success/failure feedback. Long lines scroll locally. Examples are sample data and proposed behavior, never live customer data, functioning integration claims or a published Forge rule API. The original test report predates the regression reproduction; a related commit alone is not proof of causality. SHA values are marked as abbreviated. Event structures follow [GitHub's workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) and [Sentry's exception representation](https://docs.sentry.io/api/events/retrieve-an-issue-event/).

## Implementation and interaction

- core-model.ts builds shared/instanced mechanical geometry: lens rings, curved iris blades, sensor, circuit tracks, pin headers, heatsink, coils, fasteners, rails, solar cells and antenna. A GLSL signal travels along the bus.
- core-choreography.ts defines the persistent parts and five layouts. core-scene.tsx binds them to one paused Anime.js timeline, with native scroll, damping, direct rotation and a native story range. Default orientation stays fixed. Scroll reversal reverses assembly; there is no idle spin or permanent animation loop.
- code-preview.tsx supplies the five readable examples, source selection, token rendering, highlight feedback and clipboard behavior.
- text-motion.tsx reveals headings in 340ms with 35ms between lines; supporting copy starts immediately and finishes in 320ms. Text stays nearly opaque throughout. Passages can replay after leaving the viewport completely. Motion preferences, focus, exit and tab visibility finish or revert active animation.
- landing.css scopes the marketing palette and layout. The desktop grid has a 35% central illustration column; mobile places copy and code below the object. The whole mobile reading area has an opaque background. Short viewports retain code previews. Story resize observation keeps scroll mapping aligned when a source preview changes height.

Rendering stops at rest, outside the story and in hidden tabs. Pixel ratios are capped at 1.6 desktop / 1.25 mobile. Resources, timelines, reflection textures, listeners, observers and the WebGL context are disposed on teardown. All copy, code and native anchors are server-rendered. Static SVG artwork remains for no JavaScript, reduced motion, WebGL failure and context loss; live preferences and context restoration are supported. The canvas is decorative; controls have keyboard-accessible names and focus treatment.

Initial integrations remain GitHub, Actions, JUnit reports and Sentry, in development. Roadmap logos remain in their separate labeled section. Source provenance is in apps/web/public/integrations/SOURCES.md. The working application at /app, /guide, /system and API endpoints retain their existing behavior. A future 3D logo and Phase 2 backend remain separate work.

## Run and verify

Run docker compose up -d --build --no-deps frontend, then open [the landing](http://localhost:3000). Development runs with npm run dev --workspace @forge/web -- --port 3100.

Lint, typecheck, production build and Playwright cover navigation, rendering, reversible motion, source selection, clipboard, reduced motion, WebGL failure/restoration and the actual Compose readiness endpoint. Set PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000 and FORGE_E2E_LIVE=1 for production browser checks. Chromium uses two workers and software WebGL in tests; these checks do not establish real-device frame rates or Safari/Firefox compatibility.
