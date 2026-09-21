# WebGL cable landing page

The public home page uses a centered, procedural cable to explain Forge. The user selected this replacement for the earlier circuit board and specified smooth movement, real WebGL/shaders, and a black-and-white landing palette. The application remains at `/app` with its existing dark palette; `/guide`, `/system` and API URLs are unchanged. The 3D logo remains a separate future discussion.

## Experience

Five strands join during Connect, carry a signal during Trace, open for Understand and Investigate, and form a closed loop during Automate. The investigation signal reverses direction. Native scroll position drives continuous shader deformation, with frame-rate-independent damping rather than scroll hijacking. A small pointer response changes the cable's orientation; keyboard or pointer focus on chapter links emphasizes an individual strand.

The page is a product preview. Integration, intelligence and automation capabilities are explicitly in development. Calls to action open the real foundation; the story contains no synthetic metrics, customer claims or simulated live connections.

## Implementation

- `apps/web/src/app/page.tsx`: route and metadata.
- `apps/web/src/features/landing/landing-page.tsx`: semantic content, chapter navigation and links.
- `apps/web/src/features/landing/cable-scene.tsx`: lazy Three.js initialization, procedural mesh, scroll damping, lifecycle and static fallback.
- `apps/web/src/features/landing/cable-shaders.ts`: GLSL vertex deformation, surface lighting, monochrome signal and background grain.
- `apps/web/src/features/landing/landing.css`: scoped monochrome styling and responsive composition.
- `apps/web/tests/e2e/landing.spec.ts`: real WebGL rendering, motion reversal, navigation, palette isolation, reduced motion, context failure and no-JavaScript coverage.

Three.js and its types are pinned to 0.186.0. The previous unused Anime.js dependency and circuit SVG were removed. The renderer is dynamically imported only for this surface, and only when reduced motion is not requested. The five-strand mesh has 26,400 triangles and two draw calls including its background. Desktop pixel ratio is capped at 1.75 and mobile at 1.25. Rendering stops when motion settles, when the story leaves view, and when the tab is hidden. Geometry, materials, observers, event listeners and the WebGL context are disposed on navigation or preference changes.

## Accessibility and resilience

All text and navigation are server-rendered HTML; the canvas is decorative. A static SVG cable remains visible without JavaScript, with reduced motion, when WebGL cannot initialize, and during context loss. Restoring a context resumes rendering without duplicating the canvas. Live reduced-motion preference changes dispose or initialize the renderer. Keyboard links and focus rings work independently of WebGL.

Desktop places the cable centrally with alternating narrative columns. Below 800px the cable occupies the upper reading area and copy sits below it. Short viewports use normal flow so the artwork cannot trap the reading area. The actual application palette is explicitly tested independently of the landing surface.

## Run and verify

```powershell
docker compose up -d --build frontend
```

Open [the landing page](http://localhost:3000) or [the platform](http://localhost:3000/app). For frontend development:

```powershell
npm run dev --workspace @forge/web -- --port 3100
```

Checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, and `npm run test:e2e`. Set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` and `FORGE_E2E_LIVE=1` to include actual Compose readiness checks. Chromium tests enable its software WebGL fallback so shader compilation and rendering are exercised in headless environments; this is test configuration, not a browser requirement for visitors.

No database migration or backend change accompanies this redesign. Browser automation and screenshot review do not replace Safari/Firefox, assistive-technology or real-device performance testing.
