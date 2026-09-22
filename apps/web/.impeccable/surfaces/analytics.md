---
version: 1
slug: "analytics"
primary_target: "apps/web/src/features/analytics/overview-page.tsx"
related_targets: ["apps/web/src/features/analytics/history-pages.tsx", "apps/web/src/features/analytics/analytics-ui.tsx", "apps/web/src/features/analytics/analytics.css", "apps/web/src/app/app/page.tsx", "apps/web/src/app/app/pull-requests/page.tsx", "apps/web/src/app/app/commits/page.tsx"]
---

# Pull request flow and source evidence

Mode: Operate. Scope: Phase 4 overview, pull request and commit lists/details, explicit issue references. Extend Forge's approved neutral dark workbench; preserve the landing and identity surfaces.

THESIS: Every timing summary leads to the contributing or excluded source records, within the same repository, author and UTC merge window.

OWN-WORLD: Geist, flat divided sections, compact native filters, left-aligned data tables, tabular numbers and text-supported coverage. No ornamental KPI cards, fabricated zeros or client-computed percentiles.

STORY: Choose a repository and period; compare timing distributions and sample coverage; open an included or excluded cohort; inspect reviews, lifecycle, member/merge commits and explicit issue associations. Refresh data after a worker completes enrichment. The live open queue remains independent of the historical merge window.

FIRST VIEWPORT: Existing rail and context bar, compact heading, shared filter form and a distribution table. Mobile filters start behind a labeled disclosure so the merged cohort appears in the first screen. Source coverage directly follows the summary. Desktop tables become labeled divided records on mobile. Details retain source identity, timestamps and coverage before their evidence lists. Missing history offers a repository-import route.

FORM: Scoped code-led extension of the established Operate surface. The backend owns all distributions and cohort eligibility. One monochrome daily chart plots observed medians with gaps and evidence links; an accessible daily-values table carries exact samples. Generated demo history is labeled, persisted and queried through the same API.

MOTION: Stable task UI with existing hover/focus feedback. Loading skeletons, disabled refresh controls and retry feedback communicate state. No decorative transitions; no indefinite polling of partial history.

FINISH: 117 frontend unit checks pass, including authoritative nullable values, exact cohort links, date validation, pagination recovery, organization isolation, permission coverage, source URL safety and refresh of child evidence. The parent agent's production desktop/mobile suite passed all 58 checks; 12 analytics/foundation checks passed again after the final build. A bounded inspection of the actual seeded demo database covered overview, PR lists/details/reviews, commit files, repository history and daily trends at 1440px and 390px. One correction collapsed mobile filters and restored visible field boundaries; the confirmation pass found no page errors or horizontal overflow and verified disclosure interaction. Artifacts: `.impeccable/review/phase4-{desktop,mobile}-*.png` and `phase4-geometry.json`. The parent independently reviewed the desktop overview and mobile commit. Live PR review timing is not claimed when the connected source has no PRs; the persisted generated history is explicitly labeled.
