# Circuit-board landing page

The public home page introduces Forge through a circuit board assembling on scroll. The existing application overview now lives at `/app`; `/guide`, `/system` and all API routes retain their URLs.

## Experience

Five chapters attach modules and draw connections: Connect, Trace, Understand, Investigate and Automate. During investigation, a red signal follows a path backward through the board. Native scroll position drives an Anime.js timeline; scrolling backward reverses assembly. Chapter links support direct navigation, and focus/hover highlights the corresponding circuit. All primary actions lead to the working foundation.

This is an illustrated product preview. Integration, intelligence and automation capabilities remain in development. The page makes this explicit and does not simulate customer data or live connections. The new 3D logo is deferred; the page uses a text wordmark and an illustrative chip mark.

## Implementation

- `apps/web/src/app/page.tsx`: landing route and metadata.
- `apps/web/src/features/landing/landing-page.tsx`: content, native scroll orchestration, reduced-motion handling and navigation.
- `apps/web/src/features/landing/circuit-board.tsx`: authored SVG board, components, traces and incident signal.
- `apps/web/src/features/landing/landing.css`: scoped marketing styles and responsive layouts.
- `apps/web/src/app/app/page.tsx`: preserved application overview.
- `apps/web/tests/e2e/landing.spec.ts`: motion sequencing, reverse scrolling, navigation, reduced motion and no-JavaScript coverage.

Anime.js 4.5.0 is pinned in the workspace lockfile. SVG and CSS provide the board materials and perspective; no external shader service, generated raster assets or WebGL context are required. Existing self-hosted Geist serves both surfaces. The application itself keeps its restrained foundation styling.

## Accessibility and resilience

The complete board and all narrative copy are server-rendered. JavaScript progressively adds animation. Reduced motion shows the assembled board without camera transforms, including when the operating-system preference changes while the page is open. A single requestAnimationFrame schedules scroll updates; listeners and timelines are removed on navigation. There is no scroll hijacking or decorative animation loop.

Desktop keeps the board beside the narrative. At widths below 900px it becomes a compact sticky board above the chapters; short mobile viewports use normal flow to preserve reading space. Chapter anchors have matching scroll offsets. Skip links, visible focus and descriptive headings preserve keyboard access. The SVG is decorative; the adjacent HTML explains the complete story.

## Run and verify

```powershell
docker compose up -d --build frontend
```

Open [the landing page](http://localhost:3000) or [the platform](http://localhost:3000/app). For frontend development:

```powershell
npm run dev --workspace @forge/web -- --port 3100
```

Checks: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`. Browser tests run with `npm run test:e2e`; set `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3000` and `FORGE_E2E_LIVE=1` to include the actual Compose readiness checks.

No database migration or backend change accompanies the landing page. Phase 2 remains unimplemented.

## Verification record

The production Compose build passed all 14 Chromium browser tests across 1440×1000 desktop and 390×844 mobile, including real database readiness. All three existing component tests, ESLint, TypeScript, formatting and the native production build passed. npm audit reported zero vulnerabilities. A short landscape viewport confirmed the board returns to normal flow without horizontal overflow.

The visual reviewer scored both identified fixes resolved: the mobile board no longer covers its labels or clips at the top, and redundant visual chapter labels were removed. All three Compose services are healthy. Verification does not include Safari/Firefox, assistive-technology testing or real-device performance profiling.
