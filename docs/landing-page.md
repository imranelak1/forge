# Precision-core landing page

The public home page uses a centered, procedural mechanism to explain Forge. The user selected this replacement for the rejected circuit and cable designs after a browser study of Anime.js. The surrounding landing is black, white and grayscale; the user authorized color on the mechanism to preserve module identity during transformations. The existing application remains at `/app`; `/guide`, `/system` and API URLs are unchanged. A future 3D logo is deferred.

## Experience

Four source modules and one evidence module retain their identities through five chapters. Connect withdraws the covers and unfolds the stack into a source map. Trace arranges those parts into a code/build/tests/production/evidence path, then passes a signal along its connections. Understand parks the sources and opens the evidence housing into four physical quadrants. Investigate closes the housing, restores the path and retraces it to code. Automate returns the modules to their slots before closing the covers. Orientation stays fixed through the open stages; the object only tilts as it unfolds or in response to direct user input. A single paused Anime.js timeline coordinates the sequence. Native scroll maps to continuous timeline progress with frame-rate-independent damping, without scroll hijacking.

Visitors can drag the core horizontally or focus its rotation control and use arrow keys. Home or the Reset button beside the story range returns its orientation. The range scrubs the complete story; chapter anchors work independently. The source-logo ports move with their modules, captions remain eight pixels beyond each projected rim, and selecting a source explains it. Playable, explicitly illustrative workflow sequences highlight code, builds, tests and production in order; investigation reverses the sequence.

GitHub, GitHub Actions, JUnit XML reports and Sentry are labeled as initial integrations in development. GitLab, Jira, Linear, Jenkins, SonarQube, Playwright, Selenium and AWS are labeled as roadmap tools. SVGs are served locally, with sources in `apps/web/public/integrations/SOURCES.md`. No synthetic metrics or functioning integration claims are introduced.

Headings and supporting paragraphs use short Anime.js timelines when they enter view. Hero, Automate and closing lines converge; Trace reads forward, Investigate reverses the word sequence, and Understand resolves a small blur. Each passage runs once per visit with at most 180ms of word staggering, then restores ordinary text styles. Buttons stay available. Leaving view, focusing a control or hiding the tab finishes the sequence; reduced motion restores static text immediately. React owns the word spans, preserving wrapping, selectable text and accessible heading names without client-side text replacement.

## Implementation

- `landing-page.tsx`: semantic content, tool selection, native navigation, story scrubber and integration roadmap.
- `core-scene.tsx`: lazy WebGL initialization, Anime.js master timeline, native scroll mapping, DOM logo projection, rotation interaction and lifecycle.
- `core-choreography.ts`: persistent module state and source-map, delivery-path and inspection layouts.
- `core-model.ts`: five machined assemblies, colored faceplates, separable housing quadrants, instanced teeth and fasteners, environment-lit surfaces and custom GLSL connection material.
- `integrations.tsx`: tool metadata, local source SVGs and user-initiated Anime.js workflow examples.
- `text-motion.tsx`: React word spans, viewport-triggered Anime.js text timelines and motion-preference cleanup.
- `landing.css`: scoped grayscale palette, responsive composition, interaction states and readable mobile layout.
- `tests/e2e/landing.spec.ts`: actual rendering, reversible movement, controls, source-logo loading, reduced motion, context failure and navigation.

Three.js and types are pinned to 0.186.0; Anime.js to 4.5.0. Scene imports are deferred and skipped for reduced motion. The scene uses shared geometry and instancing. Pixel ratio is capped at 1.6 desktop and 1.25 mobile. Rendering stops after motion settles, outside the story and in hidden tabs. Geometry, materials, instance resources, reflection texture, observers, listeners, timelines and WebGL context are disposed on unmount or preference changes.

## Accessibility and fallback

All copy and links are server-rendered HTML. A static SVG mechanism is visible without JavaScript, with reduced motion, when WebGL fails, and during context loss. Context restoration resumes rendering; live motion preferences recreate or dispose the renderer. Canvas content is decorative. Rotation has a labeled keyboard control; the scrubber supports native keyboard and touch interaction. Tool selection exposes explanatory text and pressed state.

Desktop places narrative and tool explanations beside the central scene. Mobile places the scene above the text, with persistent controls in their own stacking layer. Short viewports return the scene and controls to normal document flow. The dark application palette is tested separately.

## Run and verify

```powershell
docker compose up -d --build --no-deps frontend
```

Open [the landing](http://localhost:3000) or [the platform](http://localhost:3000/app). For development:

```powershell
npm run dev --workspace @forge/web -- --port 3100
```

Run lint, typecheck, unit tests, production build and Playwright. Set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` and `FORGE_E2E_LIVE=1` to include actual Compose readiness checks. Browser checks use two workers and Chromium's software WebGL fallback to avoid concurrent software-rendering contention. This flag is a test setting, not a visitor requirement.

No backend change or migration accompanies this redesign. Chromium checks do not establish Safari/Firefox compatibility, assistive-technology behavior or real-device frame rates.
