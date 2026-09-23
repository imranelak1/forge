---
version: 1
slug: "test-intelligence"
primary_target: "apps/web/src/features/test-intelligence/tests-page.tsx"
related_targets:
  [
    "apps/web/src/features/test-intelligence/report-page.tsx",
    "apps/web/src/features/test-intelligence/history-page.tsx",
    "apps/web/src/features/test-intelligence/settings-page.tsx",
    "apps/web/src/app/app/tests/page.tsx",
  ]
---

# Test reports and outcome evidence

Mode: Operate. Scope: Phase 6 test metrics, uploaded reports, suite/case details, potential-flakiness history, repository policy and upload credentials. Extend the existing dark Geist workbench; preserve the landing and previously implemented analytics.

THESIS: Inspect the test reports behind a pass rate or potential-flakiness signal, with retries, skipped outcomes, missing reports and policy thresholds visible.

OWN-WORLD: Existing neutral canvas, divided sections, compact native controls and tables. Reuse the analytics loading/error/empty/pagination states and responsive labeled rows. No ornamental metric cards, healthy-looking placeholder values or client-calculated statistics.

STORY: Select a repository and observation window; inspect report coverage and outcome counts; evaluate potential-flakiness evidence before browsing the longer report feed; open a report's suites and cases or a test's chronological outcome evidence. Inspect policy thresholds separately from measured results. Verified managers can change repository policy and issue/revoke scoped CI credentials.

FIRST VIEWPORT: Established navigation, page heading with refresh and setup/settings actions, explicit generated-history notice where applicable, compact filters and source coverage. Longer method and coverage explanations use native disclosures. Mobile filters collapse without losing scope; metric and record tables become divided labeled rows.

FORM: Code-led extension of the incumbent Operate surfaces. Authoritative backend counts, denominators, flips and policy classifications remain explicit. Reports are distinct from workflow success. Empty states explain direct report upload and link to the guide. Repository selection is required for policy and credentials.

MOTION: Existing short hover/focus feedback only. Loading, save, retry, copy and revoke feedback communicate task state. The upload credential is displayed only in local component memory after issue, never in URLs, persistent storage or query caches; dismissal/navigation clears it.

FINISH: The Phase 6 implementation and bounded visual review are complete. The fresh `phase6_finish_review` agent inspected ten actual-demo screenshots and seven feature files and reported no blockers. The parent separately reviewed the overview and mobile settings; the frontend builder reviewed report/history details and corrected repository settings at desktop/mobile sizes. The one hierarchy finding was resolved by placing potential-flakiness evidence before the longer report feed. Confirmation verified the resulting table order and readable responsive rows. The supplementary mobile investigation capture now uses the actual viewport to avoid an offscreen fixed-link artifact from element screenshots; no interface change was needed.

## Validation receipt

- Production captures: `.artifacts/phase6/{desktop,mobile}-{tests,report,history,settings,potential}.png`. Overview captures show the first viewport; potential captures show the investigation section. Report, history and settings captures preserve the corresponding page content. Browser capture checks reported no page errors or horizontal overflow.
- Frontend validation: 199 unit tests passed, including 40 test-intelligence UI/proxy checks. TypeScript, ESLint, formatting and the production build passed. The 16 affected UI tests passed again after the hierarchy and completion-coverage copy corrections.
- Browser validation: all 78 production regression checks passed, including ten new desktop/mobile test-intelligence flows for report/history navigation, policy and token handling, viewer restrictions, organization switching, retryable failures and empty states.
- The parent reported 372 passing backend tests. This frontend receipt does not substitute for the API/security review recorded in `docs/phase-6-review.md`.
- The final Impeccable detector scan of changed UI targets returned no findings. DESIGN.md, the workspace surface brief and `.impeccable/design.json` describe the completed Phase 6 behavior. No design tokens or raster assets were introduced. The approved landing remains unchanged.

## Truth and limits

Screenshots use explicitly labeled generated records in the actual seeded database. Metrics, denominators, classifications and policy evidence come from the API. Coverage is limited to uploaded reports; missing workflow completion is distinct from an absent parent link. Potential-flakiness thresholds identify evidence to investigate, not a proven defect. Demo repositories cannot issue live upload credentials. One-time token behavior and mutations were exercised with controlled browser fixtures; this visual review does not claim a real hosted CI upload. The parent's final handoff records the detector and deployment checks.
