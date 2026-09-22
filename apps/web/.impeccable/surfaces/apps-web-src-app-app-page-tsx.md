---
version: 1
slug: "apps-web-src-app-app-page-tsx"
primary_target: "apps/web/src/app/app/page.tsx"
related_targets: ["apps/web/src/app/system/page.tsx","apps/web/src/app/guide/page.tsx","apps/web/src/features/github/repositories-page.tsx"]
---

# Workspace surface

Scope: protected /app overview, repositories, organizations, members and account settings; public /system and /guide in apps/web. Mode: Operate, with Read for the guide.
Use the user's approved dark developer-tool brief directly; no separate image comp or invented demo data. This is a session implementation choice, not a stored workflow preference.

## Direction contract

THESIS: A repository-oriented workbench with honest availability and inspectable service health.

OWN-WORLD: Neutral charcoal surfaces, fine gray rules, Geist UI type, compact square controls; green and amber carry state only.

STORY: Sign in, create or join an organization, connect GitHub, select repositories, inspect synchronization and imported history, and manage access.

FIRST VIEWPORT: A 240px navigation rail with an organization switcher, 56px context bar, 24px heading and compact controls. Overview shows the selected repository list or an honest empty state, plus the service-health strip. Repository data uses a desktop table and compact labeled rows on mobile, keeping synchronization and its expanded history inside the viewport. Settings use divided rows with a label/description column and forms or member/session lists; mobile stacks the sections. Public auth screens use one 400px form column and a Forge home link. Protected content waits for the server identity; unrecognized sessions lead to sign in. Source and service states expose real outcomes without invented activity.

FORM: Preserve the approved source-control workbench. Phase 3 extends its forms and divided rows with GitHub connection management and repository history. No replacement visual world or raster comp is needed for this extension.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
