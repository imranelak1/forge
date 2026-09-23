---
version: 1
slug: "apps-web-src-app-app-page-tsx"
primary_target: "apps/web/src/app/app/page.tsx"
related_targets:
  [
    "apps/web/src/app/system/page.tsx",
    "apps/web/src/app/guide/page.tsx",
    "apps/web/src/features/github/repositories-page.tsx",
    "apps/web/src/features/analytics/overview-page.tsx",
    "apps/web/src/features/analytics/history-pages.tsx",
  ]
---

# Workspace surface

Scope: protected /app analytics overview, repositories, PR/commit evidence, CI attempts, deployments, environment policy, test reports and outcome histories, repository test policy and upload credentials, organizations, members and account settings; public /system and /guide in apps/web. Mode: Operate, with Read for the guide.
Use the user's approved dark developer-tool brief directly; no separate image comp or invented demo data. This is a session implementation choice, not a stored workflow preference.

## Direction contract

THESIS: A repository-oriented workbench with honest availability and inspectable service health.

OWN-WORLD: Neutral charcoal surfaces, fine gray rules, Geist UI type, compact square controls; green and amber carry state only.

STORY: Sign in, create or join an organization, connect GitHub, select repositories, inspect synchronization and imported history, follow timing summaries into source evidence, and manage access.

FIRST VIEWPORT: A 240px navigation rail with an organization switcher, 56px context bar, 24px heading and compact controls. Overview shows shared UTC filters, a timing-distribution table and sample evidence links, with source coverage directly below. PR, commit and repository data use desktop tables and compact labeled rows on mobile. Settings use divided rows with a label/description column and forms or member/session lists; mobile stacks the sections. Public auth screens use one 400px form column and a Forge home link. Protected content waits for the server identity; unrecognized sessions lead to sign in. Generated demo organizations are explicitly labeled. Source and service states expose real outcomes without invented activity.

FORM: Preserve the approved source-control workbench. Phase 6 extends its forms and divided rows with uploaded test outcomes, inspectable reports and potential-flakiness evidence, repository policy and scoped CI credentials. Investigation candidates precede the longer report feed. The PR overview links directly to delivery and test evidence. No replacement visual world or raster comp is needed for this extension.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
