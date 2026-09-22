---
version: 1
slug: "identity"
primary_target: "apps/web/src/features/auth/auth-pages.tsx"
related_targets: ["apps/web/src/features/auth/account-settings.tsx", "apps/web/src/features/organizations/create-organization.tsx", "apps/web/src/features/organizations/organization-settings.tsx", "apps/web/src/features/auth/account.css"]
---

# Identity and organization access

Mode: Operate. Scope: Phase 2 accounts, email links, organization onboarding/settings and active sessions. Preserve the existing dark developer workbench and leave the approved public landing unchanged.

THESIS: A direct route into the right organization, with visible permission and session state.

OWN-WORLD: Geist UI type, neutral charcoal, fine rules, compact rectangular controls. Color communicates errors, verification and status. No invented activity or decorative imagery.

STORY: Create an account or sign in, verify the email, create or join a team, then manage organization access and active sessions. Recovery paths must explain the next action.

FIRST VIEWPORT: Public identity forms use a 400px column with a clear heading, persistent labels, one submit action and appropriate recovery/account links. Workspace settings inherit the navigation rail and use divided two-column sections that stack on mobile. Empty, busy, failed and successful states remain legible and announced. Focus is visible; controls support keyboard input and mobile touch.

FORM: Code-led extension of the incumbent Operate surface; no redesign, raster asset or new brand metaphor.

MOTION: Keep work forms stable and use the existing short color transitions. Submitting disables conflicting controls and announces the result. Reduced motion follows the global preference. Anime.js landing choreography is outside this surface.

FINISH: Confirm desktop/mobile layout, exercise real browser/API flows and record the implemented forms in DESIGN.md and its sidecar.
