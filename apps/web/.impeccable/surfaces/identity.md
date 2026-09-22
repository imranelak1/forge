---
version: 1
slug: "identity"
primary_target: "apps/web/src/features/auth/auth-pages.tsx"
related_targets: ["apps/web/src/features/auth/account-settings.tsx", "apps/web/src/features/organizations/create-organization.tsx", "apps/web/src/features/organizations/organization-settings.tsx", "apps/web/src/features/auth/account.css"]
---

# Identity and organization access

Mode: Operate. Scope: Phase 2 accounts, email links, organization onboarding/settings and active sessions, extended by the requested GitHub and Google sign-in and explicit account linking. Preserve the existing dark developer workbench and leave the approved public landing unchanged.

THESIS: A direct route into the right organization, with visible permission and session state.

OWN-WORLD: Geist UI type, neutral charcoal, fine rules, compact rectangular controls. Color communicates errors, verification and status. No invented activity or decorative imagery.

STORY: Create an account or sign in, verify the email, create or join a team, then manage organization access and active sessions. Recovery paths must explain the next action.

FIRST VIEWPORT: Public identity forms use a 400px column with a clear heading, persistent labels, one submit action and appropriate recovery/account links. Workspace settings inherit the navigation rail and use divided two-column sections that stack on mobile. Empty, busy, failed and successful states remain legible and announced. Focus is visible; controls support keyboard input and mobile touch.

FORM: Code-led extension of the incumbent Operate surface; no redesign or new brand metaphor. Social sign-in uses equally prominent 44px actions, official GitHub SVG and current Google PNG marks. Google Sans Medium is scoped to the Google button to follow its provider branding; the surrounding UI remains Geist. Connected account rows inherit the existing divided settings layout.

MOTION: Keep work forms stable and use the existing short color transitions. Submitting disables conflicting controls and announces the result. Reduced motion follows the global preference. Anime.js landing choreography is outside this surface.

FINISH: Confirm desktop/mobile layout, exercise real browser/API flows and record the implemented forms in DESIGN.md and its sidecar.
