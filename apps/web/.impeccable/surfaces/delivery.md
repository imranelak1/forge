---
version: 1
slug: "delivery"
primary_target: "apps/web/src/features/delivery/delivery-pages.tsx"
related_targets: ["apps/web/src/features/delivery/delivery-details.tsx", "apps/web/src/features/delivery/environment-page.tsx", "apps/web/src/features/delivery/delivery-ui.tsx", "apps/web/src/features/delivery/delivery.css", "apps/web/src/app/app/ci/page.tsx", "apps/web/src/app/app/deployments/page.tsx"]
---

# Workflow attempts and deployment evidence

Mode: Operate. Scope: Phase 5 CI/deployment summaries, attempt/job and deployment/status details, environment policy. Extend Forge's approved dark Geist workbench, retaining the landing and PR surfaces.

THESIS: Trace a CI or deployment number to its source evidence, with retries, missing timestamps and classification decisions left visible.

OWN-WORLD: Existing flat divided sections, native fields, compact controls, neutral data tables and explicit semantic coverage text. No KPI tiles, inferred deployments or client-computed metric distributions.

STORY: Select a repository and UTC window; inspect coverage; open successful, failed or excluded attempts; read jobs and explicit PR/commit links. For deployments, follow first-success evidence and status history, then inspect the provider classification or an explicit Forge environment override. Verified managers may change Forge policy; readers inspect it.

FIRST VIEWPORT: Established navigation, page identity and refresh action, generated-history notice when applicable, shared filters and compact source coverage. Status, repository count, watermark and evidence counts remain visible; the coverage disclosure holds detailed limitations, provenance and setup instructions. Metric rows lead to exact cohort links. Mobile filters begin collapsed; records become labeled rows. Job/status sections and environment controls remain within the viewport width.

FORM: Code-led extension of the incumbent Operate surfaces. Native daily-value disclosures present outcome counts, timing samples and day coverage. Environment names never classify records; zero observations never turn an unavailable source into healthy coverage. Last-job completion is labeled as a proxy.

MOTION: Existing short hover/focus feedback. Explicit loading, retry and save states; no decorative animation or indefinite polling. Refresh data reloads scoped metrics and child evidence after asynchronous ingestion.

FINISH: Implementation includes meaningful UI and proxy tests for distinct retries, nullable rates/timing, cohort links, incomplete coverage and their disclosure, policy permissions, null override removal, paging retry and tenant isolation. All 159 frontend unit tests, typecheck, lint and changed-file formatting passed. The first bounded actual-DB demo pass produced 16 desktop/mobile frames with no overflow or browser errors. Review found source-coverage prose delayed the first metric; the single correction batch compacted that summary, retained visible counts and moved longer explanations into a native disclosure, with refresh beside summary heading actions. Attempt/job details, deployment/status histories and environment rows passed the first inspection.

The post-rebuild confirmation inspected all four affected summary frames at 1440×1000 and 390×844: `.impeccable/review/phase5-confirm-{desktop,mobile}-{ci,deployments}.png`. Desktop metrics now appear within the first viewport; mobile preserves readable controls and visible coverage before the metrics below the fold. `.impeccable/review/phase5-confirm-geometry.json` records no page errors or horizontal overflow. The confirmation passed without another correction cycle. The initial evidence views remain at `.impeccable/review/phase5-{desktop,mobile}-{attempts,attempt,jobs,deployment,statuses,environments}.png`. No new raster assets were introduced. Real provider collection still requires the GitHub App owner to grant and accept Actions/Deployments read access; the reviewed history is explicitly labeled generated demo data.
