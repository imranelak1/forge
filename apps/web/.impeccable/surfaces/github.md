---
version: 1
slug: "github"
primary_target: "apps/web/src/features/github/integrations-page.tsx"
related_targets: ["apps/web/src/features/github/repositories-page.tsx", "apps/web/src/features/github/github-ui.tsx", "apps/web/src/features/github/github.css", "apps/web/src/app/app/integrations/page.tsx", "apps/web/src/app/app/repositories/page.tsx"]
---

# GitHub repository access and history

Mode: Operate. Scope: Phase 3 GitHub App connection, installation choice, catalog selection and imported repository history. Inherit Forge's approved neutral charcoal workbench; preserve the public landing.

THESIS: Connect only the repositories the organization authorizes, then show what Forge has actually imported and what needs attention.

OWN-WORLD: Geist UI type, flat divided sections, native selects and checkboxes, compact buttons and a readable data table. State color always accompanies text; no charts or summary metrics beyond stored records.

STORY: An installation administrator configures the GitHub App. A verified Forge owner or admin installs and authorizes it, chooses an installation, selects repositories and saves. The repository view shows import progress, stored counts and retry/history controls. Access changes stop ingestion explicitly.

FIRST VIEWPORT: Integrations uses the established settings grid, leading with honest app availability. Connected accounts extend into catalog checkboxes and explicit save/confirmation controls. Repositories uses a desktop table with name/branch/language, last push, imported counts and synchronization. On mobile, each record becomes a flat labeled row with two compact detail columns and full-width sync controls. Expanded history stays inside the viewport.

FORM: Code-led extension of the incumbent Operate surface. No new palette, display typography, animation metaphor or raster asset.

MOTION: Keep task controls stable. Poll active work every four seconds; use existing short hover/focus transitions. Busy and unavailable controls explain their state. No decorative entrances or spinners.

FINISH: Desktop/mobile actual disabled and empty states, plus explicitly synthetic populated catalog, repository and sync-history fixtures were captured. One mobile correction replaced horizontal clipping of expanded history with labeled responsive rows. Browser workflows verify selection persistence, read-only roles and failed-load recovery; no live GitHub App credentials were available for external authorization.
