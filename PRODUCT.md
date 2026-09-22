# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

User-selected: Next.js, TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Recharts, Lucide; FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL. Docker Compose for local use.

## Users

Software development teams investigating engineering delivery and configuring pipeline responses.

## Product Purpose

Forge connects engineering activity, traces software lifecycles and turns measured changes into explainable insights and auditable automation.

## Operating Context

Issue → pull request → commits → CI → tests → deployment → production errors. Initial sources: GitHub, Actions, JUnit and Sentry. Organization isolation is mandatory.

## Capabilities and Constraints

Phase 2 implements accounts, sessions, organizations, invitations, roles and tenant isolation. The user subsequently authorized GitHub and Google sign-in, including explicit connections to existing verified accounts. Provider-issued credentials are required to enable each option. Phase 3 adds verified GitHub App connections, repository selection, signed webhooks and durable PR/commit history sync. Phase 4 adds database-backed PR timing, daily trends, pull request/commit details, review/lifecycle/file evidence and optional issue links. Phase 5 adds Actions attempts/jobs, CI outcomes and timing, independent deployment/status history and audited environment classification. Test and production-error analytics remain future work. No fabricated metrics, fake functioning controls or unimplemented provider connections.

## Brand Commitments

Forge. Dark-first, professional developer-tool interface; subtle borders, dense readable data layouts, excellent spacing, color mainly for state. These constraints are explicit in the user's brief.

The user authorized the public landing at `/` with a central SVG track using Anime.js createDrawable and createMotionPath. A thicker drawn line connects GitHub, Actions, JUnit and Sentry; a coral code packet follows delivery and returns to the test and code before ending in human review. Headings and explanations use persistent Anime.js splitText with scroll-driven entrances, a reading interval and animated exits that reverse when scrolling back. Realistic code/event previews and the Anime.js warm charcoal/coral palette remain. Integrations and automation are in development; examples are illustrative. Phase 2 preserves the approved landing and extends `/app` with compact forms and settings in its existing dark workbench style. The 3D logo remains deferred.

## Evidence on Hand

The approved architecture and milestone contracts live in docs/. Identity and organization records are real; opt-in demo organizations are explicitly synthetic. A private GitHub App is connected locally and one selected repository has imported engineering history. Opt-in generated history is restricted to marked demo organizations and repositories. No commercial claims or production deployment exists.

## Product Principles

- Show the evidence behind each insight.
- Preserve missing data and uncertainty.
- Keep tenant authorization at every boundary.
- Make pipeline responses inspectable and retry-safe.

## Open Decisions

Production hosting and provider account details are deferred to their scheduled phases. Typography and precise spacing are implementation choices within the approved visual brief.
