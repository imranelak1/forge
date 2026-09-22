---
name: Forge
description: A dark engineering workbench with an Anime.js-inspired landing and an SVG path that follows one commit through delivery and investigation.
colors:
  background: "#111111"
  foreground: "#ededed"
  muted: "#212121"
  muted-foreground: "#a6a6a6"
  border: "#303030"
  primary: "#ededed"
  primary-foreground: "#171717"
  ring: "#c8c8c8"
  surface: "#171717"
  success: "#8bceac"
  warning: "#dfba7b"
  field-border: "#666666"
  form-error: "#efb0a5"
  provider-background: "#131314"
  provider-border: "#8e918f"
  provider-text: "#e3e3e3"
  inset: "#191919"
  navigation-hover: "#242424"
  navigation-active: "#2a2a2a"
  navigation-text: "#b7b7b7"
  recovery-background: "#211d17"
  recovery-border: "#504330"
  recovery-text: "#c9bda9"
  landing-background: "#252423"
  landing-surface: "#2a2928"
  landing-subtle: "#93908d"
  landing-integrations: "#dad5d0"
  landing-integrations-muted: "#5b5855"
  landing-text: "#f6f4f2"
  landing-muted: "#b4b1af"
  landing-line: "#4a4847"
  landing-button: "#ff4b4b"
  landing-button-text: "#252423"
  landing-button-hover: "#ff718b"
  landing-module-code: "#ff4b4b"
  landing-module-build: "#ffa828"
  landing-module-tests: "#b7ff54"
  landing-module-production: "#05dbe9"
  landing-module-evidence: "#4d9cff"
typography:
  google-sign-in:
    fontFamily: '"Google Sans Sign In", "Geist Variable", sans-serif'
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
  landing-display:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "clamp(60px, 5.8vw, 84px)"
    fontWeight: 510
    lineHeight: 0.99
    letterSpacing: "-0.04em"
  landing-chapter:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "clamp(30px, 2.8vw, 40px)"
    fontWeight: 480
    lineHeight: 1.11
    letterSpacing: "-0.035em"
  headline:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.6px"
  title:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "14px"
    fontWeight: 600
    lineHeight: 1.55
  body:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  body-small:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.55
  settings-title:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "15px"
    fontWeight: 600
    lineHeight: 1.55
  label:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.55
  compact-label:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.55
  button:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "14px"
    fontWeight: 500
    lineHeight: "20px"
  code:
    fontFamily: 'ui-monospace, "Cascadia Code", monospace'
    fontSize: "12px"
rounded:
  landing-control: "3px"
  badge: "4px"
  navigation: "5px"
  control: "6px"
spacing:
  "4": "4px"
  "6": "6px"
  "8": "8px"
  "12": "12px"
  "14": "14px"
  "16": "16px"
  "18": "18px"
  "20": "20px"
  "24": "24px"
  "28": "28px"
  "32": "32px"
components:
  provider-button:
    backgroundColor: "{colors.provider-background}"
    textColor: "{colors.provider-text}"
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "44px"
  landing-button:
    backgroundColor: "{colors.landing-button}"
    textColor: "{colors.landing-button-text}"
    rounded: "{rounded.landing-control}"
    padding: "12px 20px"
  landing-button-hover:
    backgroundColor: "{colors.landing-button-hover}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.foreground}"
    typography: "{typography.button}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "36px"
  button-outline-hover:
    backgroundColor: "{colors.muted}"
  account-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.foreground}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "9px 11px"
    width: "100%"
  navigation-active:
    backgroundColor: "{colors.navigation-active}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.navigation}"
    padding: "9px 12px"
  status-healthy:
    textColor: "{colors.success}"
    typography: "{typography.label}"
  service-container:
    backgroundColor: "{colors.background}"
    rounded: "{rounded.control}"
  recovery-notice:
    backgroundColor: "{colors.recovery-background}"
    rounded: "{rounded.control}"
    padding: "18px"
---

# Design System: Forge

## Overview

**Creative North Star: "The Engineering Workbench"**

Forge uses neutral charcoal surfaces, fine gray rules, compact controls, and readable operational detail. The approved dark developer-tool brief is the visual authority. Color communicates state; typography and spacing establish hierarchy.

This document records the implemented foundation, workspace access, GitHub ingestion and Phase 4 pull request analytics in `apps/web`: accounts and social sign-in, organizations and permissions, GitHub App authorization, selected repositories, synchronization, PR and commit history, timing distributions and their evidence. System status and the setup guide remain public. CI, test and production analytics remain future work.

The public landing page at `/` follows one illustrative checkout commit along a centered SVG path. Anime.js draws a 4-unit line between GitHub, Actions, JUnit and Sentry logos and moves a coral code packet with an authored bracket glyph along it. The packet traces delivery, returns to the regression test and related code, then ends at a human review request. Headings and explanations animate into view, stay readable through a reading interval and animate out as the visitor scrolls on. Scrolling back reverses the same sequence. Each chapter retains its realistic code preview. The Anime.js palette remains warm charcoal, off-white, coral controls and warm stone integrations. The application retains its compact neutral foundation. The wordmark remains; a future 3D logo is deferred.

**Key Characteristics:**

- Flat charcoal surfaces with subtle borders.
- Geist interface text with system monospace for commands and versions.
- Restrained controls and explicit, text-supported service states.
- Responsive navigation and locally scrollable technical content.
- Persistent form labels, visible access roles, and divided settings sections.
- Table-based timing distributions with sample counts, exclusions, coverage and direct evidence links.
- A scoped public landing with a continuous delivery track, tool checkpoints and five code examples.

## Colors

The application palette is almost entirely neutral, with muted green, amber, and the form-error tone reserved for meaningful state.

Frontmatter records the implemented colors. The companion `.impeccable/design.json` includes generated tonal ramps for the design panel preview; those ramps are not additional application tokens.

### Primary

- **Primary / primary foreground:** the light solid Button variant and its dark label; account creation, sign-in, form submission, verification, and invitation acceptance use it for the main action.
- **Success:** verified healthy checks, the current phase label, verified email status, and successful form feedback.
- **Warning:** unavailable services, migration requirements, recovery icons, and unverified email status.
- **Form error:** readable inline failures and recovery instructions; no filled error panel or error-specific field border is implemented.

### Neutral

- **Background:** the main application canvas.
- **Surface:** the navigation rail and command blocks.
- **Inset:** notice and repository-header fill.
- **Muted:** interactive hover fill.
- **Foreground / muted foreground:** primary information and supporting descriptions.
- **Border:** one-pixel panel boundaries and dividers.
- **Field border:** the stronger one-pixel boundary shared by text fields and native selects; interactive fields remain distinguishable from the subtle panel rules.
- **Ring:** keyboard focus outlines.
- **Navigation text / hover / active:** distinguish ordinary, hovered, and current destinations.
- **Recovery background / border / text:** the subtle amber-tinted recovery notice.

**The Evidence Rule.** Use state colors with a label and icon. An unverified or loading check must remain visually distinct from a healthy check.

Service-health indicators follow this rule. Compact form feedback, account email status and analytics coverage pair state color with explicit text; these states have no accompanying status icon.

### Landing scope

The `landing-*` frontmatter tokens apply only at `/`. The user-selected Anime.js palette uses warm charcoal, off-white text, warm gray supporting copy and fine rules. Primary actions have coral fill and charcoal labels; hover is lighter coral and focus is coral. The integrations section uses warm stone with charcoal text and darker supporting copy. Local tool logos are white on dark sections and black on stone. The SVG delivery path and code packet use coral, with amber for the review endpoint; source and evidence accents remain scoped to the landing examples. They are not application state colors. The landing also overrides the inherited muted-foreground variable with its own supporting-copy token.

## Typography

Geist Variable is bundled locally through `@fontsource-variable/geist`; the fallback is sans-serif. Commands and version identifiers use the system monospace stack. The application has no separate display face or oversized marketing typography.

- **Headline:** page titles use the frontmatter headline role; mobile titles reduce to 22px.
- **Title:** section headings use the title role. Service titles are 14px at weight 500; guide section headings are 16px at weight 600. Divided account and organization settings use the settings-title role.
- **Body:** the base role is 14px. Page descriptions and service explanations use body-small; supporting overview lists and detail copy use 12px. Settings descriptions use body-small with 1.7 line height; form feedback uses it with 1.6 line height. Field labels and member/session names use the same size at weight 500. Auth descriptions remain 14px with 1.7 line height.
- **Label:** state labels, field hints, role controls, member email addresses, and activity/session dates use 12px. Compact health labels and the build badge use compact-label. Session references use that size in system monospace. Hints use 1.6 line height.
- **Brand:** the wordmark is 22px, weight 650, with -0.6px tracking; mobile reduces it to 20px.
- **Code:** guide commands use the code role and 1.8 line height in scrollable blocks. Check timestamps use tabular numerals.

Repository empty-state copy is limited to 65ch, system notes to 72ch, and the guide column to 76ch. Field hints use a 65ch maximum, onboarding descriptions 60ch. The compact 11px, 13px, and 15px steps are intentional roles in the dense application hierarchy, not a new display scale. Labels use sentence case.

Checkpoint metadata uses 9-11px text; contextual track explanations and code use 10-12px. The adjacent chapter code previews retain 12px selectable text. Logos stay in native HTML, with 44px compact targets. The same metadata stays available through accessible source names.

The landing reuses Geist with the `landing-display` and `landing-chapter` roles. Hero copy is centered, 15px with 1.7 line height; chapter descriptions are 15px with 1.85 line height and a 310px measure. The closing headline scales from 39px to 72px. At 800 to 1100px chapter headings use 32px; below 800px the hero scales from 49px to 68px and chapter headings from 33px to 43px. At 380px and below the hero is 47px. The landing wordmark is 30px, weight 680, with -1.2px tracking and a plain period; the footer wordmark is 26px.

## Layout

The desktop shell is a 240px rail beside a flexible content area. The context bar is 56px tall. Main content is centered with a 1400px maximum width and 32px padding. Section spacing generally uses 24px or 32px; compact metadata uses 6–16px gaps. These are observed values, not an enforced mathematical scale.

At 1100px and below, main padding reduces to 24px and the health strip wraps its checks with labels above values. At 760px and below, the rail becomes a top navigation area, main padding becomes 24px vertically and 20px horizontally, and the context bar, installation label, planned navigation, and sidebar footer are hidden. Page headings and service rows stack. The two-column foundation detail becomes one column with a horizontal divider.

Repository lists use a five-column desktop table with an 820px minimum width inside a local scroller. At intermediate widths a scroll hint explains access to remaining columns. At 760px and below, the same table becomes flat, divided rows: repository identity spans the width, last-push and imported-history values use two columns, and synchronization, actions and expanded history span the width. Column labels remain visible beside their mobile values; table headers remain available to assistive technology. Mobile repository actions are at least 44px tall. Command blocks scroll within their own boundary. Keep the page itself free of horizontal overflow.

Analytics uses the same responsive table grammar. The overview leads with shared filters and a metric table; source coverage, the daily merge trend and the separate current open queue follow in divided sections. Filter fields occupy four columns on desktop, two below 1100px and one below 760px. On mobile, filters start collapsed behind a labeled control with the applied count; opening it exposes the same fields and actions with visible focus and 44px targets. PR and commit details use two-column definition lists that stack on mobile. Review and lifecycle events use divided chronological records. Long titles, SHAs, paths and commit messages wrap without widening the page.

Public identity routes use a single 400px maximum column directly on the application canvas, with 24px by 32px page padding, a 48px Forge home-link row, and 64px above the form column. Its bottom margin is 48px; a second home link sits toward the page bottom. Account forms have a 440px maximum width and 20px vertical gaps, constrained to the public column when used there. Organization onboarding uses a 640px maximum section with 28px gaps. Public identity pages omit the application rail and context bar.

Account and organization settings use a 1040px maximum content region. Each section begins with a one-pixel top rule and 28px vertical padding, then a 230px heading/description column, a 40px gutter, and a flexible content column. Forms remain capped at 440px; member, session, and activity lists fill the content column. At 1100px and below, the heading column becomes 185px, the gutter 28px, and member controls move below the identity.

At 760px and below, identity-page padding becomes 20px by 24px and the form's top margin becomes 44px. Settings sections stack with 20px gaps and 24px vertical padding. The organization selector occupies the mobile navigation width and navigation links wrap. Text fields, form selects, the organization selector, member role selects, and the form, confirmation, member, and session-revoke actions have a 44px minimum height. This is a scoped form/control treatment; the base button primitive keeps its existing sizes. Session controls stack below their details. Member identity and controls share a row again where the wider mobile content column permits; at 430px and below they stack. Account detail labels reduce from a 110px column with a 16px gap to 86px with a 12px gap. Names, emails, slugs, and feedback wrap within their boundaries.

The story uses a flex column to prevent the negative sticky-layer margins from collapsing and displacing the hero. The landing header has a 1600px maximum width, 5% side padding, and an 84px height. The centered hero and sticky core stage use the viewport height minus the header; the hero has a 740px minimum height. The hero begins with a partly drawn SVG path and coral code packet beneath the copy; responsive sizing keeps the line and tool logos in the central reading area. Five chapters alternate copy and tool explanations around the core in a 1440px grid with a 35% center column. Chapters have a 105svh minimum height and 5% side padding. Desktop chapter copy has a 336px maximum width, retaining the intended heading line breaks while character splits are active. At 800 to 1100px the center column reduces to 34% and the core caption is hidden. Story controls occupy a separate sticky layer with a 114px height, a -114px top margin and zero bottom margin, keeping their sticky boundary inside the story. The integration section follows in normal flow, with four initial-tool columns and a wrapping roadmap list.

Below 800px, the landing header is 72px tall with 24px side padding; its secondary navigation is hidden while platform entry remains visible. The hero has a 700px minimum height. The core occupies the upper reading area, with chapter copy beginning at 43svh and using a 440px maximum measure; tool explanations follow the copy. Chapters have a 108svh minimum height and 27px side padding; all five chapter links remain visible with 44px minimum targets. Story controls use a 94px height, a -94px top margin and zero bottom margin. Initial integrations become two columns. At 380px and below chapter side padding becomes 22px. At any width when the viewport is at most 600px high, the core stage and controls return to normal document flow, with a 400px stage and 550px minimum chapter height; code previews remain in document flow beneath their explanations.

## Elevation & Depth

The application implements no shadows, gradients, blur, or floating surfaces. Depth comes from restrained tonal differences and one-pixel borders. Containers sit directly in the document flow. Do not add elevation to ordinary data panels without a new design decision.

The landing illustration is an authored SVG path with rounded turns, a 2.5-unit guide, a 4-unit coral drawn line and an amber review endpoint. A coral code packet measures 32 by 22 SVG units, with 3-unit corners and a charcoal bracket glyph. Four authentic local tool logos sit at their source checkpoints, with labels offset 15px below the path to clear the packet. Native buttons expose the source examples. The SVG line and packet share one viewBox, keeping their coordinates aligned on resize. No WebGL, shaders or external model assets are needed.

## Shapes

Forms are compact rectangles: badges use the badge radius, navigation uses the navigation radius, and buttons, notices, tables, service lists, and code blocks use the control radius. Circular geometry appears in state icons rather than pill-shaped containers. Lucide stroke icons provide navigation and status imagery; the shipping favicon is SVG. The Google sign-in mark is the official current PNG brand asset; other integration marks remain SVG. Provider marks are not redrawn or used as decorative imagery.

Landing actions and checkpoint controls use 3px corners. The SVG delivery line draws through four source checkpoints and finishes at review. Local integration SVGs retain their source geometry and render in white or black to suit the section; provenance is in `public/integrations/SOURCES.md`.

## Components

### Buttons

The shared primitive provides primary, outline, and ghost variants. Default controls are 36px tall with 14px horizontal padding and 8px icon gaps. Small controls are 32px tall with 12px padding; icon controls are 36px square. Icons inside buttons are 16px.

Form submits have a 40px minimum height and align to the start in workspace settings; direct public form submits stretch to the form width. Primary buttons carry submission and acceptance, outline buttons carry retry, session revocation, and confirmations, and ghost buttons carry cancellation or reveal inline member removal. Mobile form/action height overrides are described in Layout.

Outline buttons have a one-pixel border and canvas fill, changing to muted fill on hover. Ghost buttons gain muted fill on hover. Primary buttons reduce their background opacity to 90% on hover. Disabled controls use 50% opacity and suppress pointer events. Color transitions use Tailwind's default 150ms timing. Keyboard focus uses a two-pixel ring offset by four pixels.

### Social sign-in and connections

Login and registration place two equally prominent, full-width provider actions above the email form, with 12px gaps and a quiet ruled "or use your email" separator. Both actions use the provider background, border and text tokens, a 44px minimum height, 12px horizontal padding and 20px official marks. The Google action alone uses self-hosted Google Sans Medium at 14px/20px, as required by its sign-in branding; Geist remains the application typeface. Provider colors and type stay scoped to these controls.

Availability comes from the API. Unconfigured options are disabled with a nearby explanation; loading and errors are announced, with a retry for discovery failures. Starting either email or provider authentication disables conflicting form actions. Fixed callback errors explain recovery without displaying arbitrary provider text.

Account settings place Connected accounts between identity details and sessions. Each divided row pairs the provider mark/name and email or availability with its connection state or Connect action. Connecting requires a verified Forge email. Below 760px the action moves below its provider identity and uses a 44px touch target. This surface authorizes sign-in only and says that it does not connect repositories.

### Navigation and links

Desktop navigation uses 13px labels, 17px icons, and 9px by 12px padding. Hover and current-page fills are separate neutral tones; current links carry `aria-current="page"`. Mobile navigation uses 12px labels and 9px by 10px padding. Planned destinations are static text, not controls. Text links use a small adjacent arrow and underline on hover. A keyboard-visible skip link targets the main content.

Signed-in navigation exposes Overview, Repositories, Pull requests, Commits, Integrations, System status, Setup guide, Organization settings and Account. PR and commit detail routes retain their parent navigation selection. CI, test and production tools remain explicitly planned. The native Organization select sits between the Forge home link and navigation, within the rail's horizontal rules; its label is 12px and its value 13px, with a 38px minimum control height on desktop. It lists accessible organizations and a Create organization option, with a Load more organizations action when needed. The context badge reads "Phase 4 · Pull request analytics". Public status and guide routes retain the shell; public identity routes use their own Forge home and recovery links. Inline form hints and account-switch links are underlined without depending on hover.

### Inputs and form feedback

Text fields and native selects share surface fill, foreground text and caret, the field-border token, and the control radius. Full-width fields have a 42px minimum height with 9px by 11px padding. Persistent labels sit 8px above the field; hints follow beneath and are connected with `aria-describedby`. Placeholder text uses muted foreground. Inputs retain their native email, password, autocomplete, required, length, and pattern behavior. Focus uses the global two-pixel ring with a four-pixel offset; no separate hover fill is applied to fields. Disabled inputs and selects use 65% opacity.

Form errors use the form-error token and `role="alert"`; successful results use success and `role="status"`. Messages sit beside the affected form or row, wrap long content, and explain the next action. Submission sets the form's busy state, disables its fields and submit action, and changes the action label to the work in progress. Settings mutations disable conflicting editable controls. There is no per-field error decoration, loading spinner, or toast system. Password-reset and verification email requests use neutral, conditional confirmation copy rather than revealing whether an account exists.

### Organization settings and access lists

Settings stay in document flow with rules between sections. Organization details pair an editable name with a read-only monospace slug. Viewers and members see the name disabled with an explanation; owners and admins can edit it. Native role selects list Viewer, Member, Admin, and Owner; admins cannot assign Owner or edit an owner's membership. Read-only memberships show their role as text. Member rows pair a 13px name with 12px email, then a 102px-wide role select and Remove action; row dividers and 16px vertical padding organize the list. Role changes save from the select. Removal reveals an inline explanation, Confirm removal, and Cancel, spanning the row; feedback remains attached to that member.

Owners and admins see the invitation form and recorded organization activity. Invitations pair a teammate email with an Invitation role select, defaulting to Member, and report the destination and expiry on success. Activity rows pair readable action text with localized tabular dates, separated by fine rules. Members load 25 at a time and activity 15 at a time, with explicit Load more actions. Loading, retry, and empty activity states use plain text and real controls. Owners see inline organization deactivation with an exact-slug confirmation; the copy states that members lose access and data is retained. No modal is used.

### Account details and sessions

Account settings use a definition list for name, email, and explicit Verified or Not verified status. An unverified account receives a verification request form. Session rows show This browser or Other browser session, localized started/expiry dates with tabular numerals, and an abbreviated monospace session reference. The current row is labeled Current session; other rows offer Revoke session. Revocation changes the button label, disables conflicting actions, refreshes the list, and announces success or failure. Sign out ends the current session. Session lists load 25 at a time and expose loading, retry, and Load more states. Rows use 18px vertical padding and bottom rules.

### Identity and recovery boundaries

Sign-in and registration share the public form frame, with a heading, brief description, one main submit action, and account/recovery links. Registration includes a persistent password-length hint. Reset links expose explicit reading, missing-token, failure, and completed states; changing the password explains that previous sessions end. Verification requires an explicit action and offers another email request after failure. Invitations keep the same frame while the visitor signs in or registers, verifies the invited address, and explicitly accepts; success names the joined organization.

Protected `/app` content waits for the server identity response. An unrecognized session redirects to sign-in while preserving an allowed return destination; a failed identity request exposes a retry and system-status link. Accounts without an organization see creation onboarding, while Account settings remains reachable for verification. Organization switching clears the previous organization's queried content before selecting the next scope. Identity changes between tabs temporarily hide prior account content while the session is checked.

Secure form submission, link-token processing, and protected workspace access require JavaScript. Public identity frames include an explicit enable-JavaScript notice; the protected boundary supplies the same explanation and a sign-in link. These are limited fallbacks, not a functioning no-JavaScript account flow. The public landing's separate static fallback remains as documented below.

### Status indicators

Indicators pair a 14px icon with a 12px label and 6px gap. Healthy is green with a check circle; unavailable and migration-required states are amber with an alert circle; checking and not-verified states are neutral with a dashed circle. State labels do not wrap. The compact strip and detailed list share this vocabulary.

Checks refresh every 30 seconds while mounted. Initial loading displays Checking. During refresh, the action displays Checking… and is disabled while previous check results remain visible. Descriptions explain what each check examines without claiming success. Live regions announce updates; the service list exposes busy state.

### Containers and empty states

Service containers use one-pixel borders and the control radius. Repository lists use horizontal rules and a surface-filled header, with 12px table text, 13px repository names, 11px metadata and 16px desktop cell padding. The empty repository state is left aligned between horizontal rules, with 32px vertical padding, a repository icon, a concise explanation and an Open integrations action. Missing app credentials instead expose an explicit setup message and setup-guide link. Neither state implies a connected or healthy source.

### GitHub integration and synchronization

Integrations extends the divided settings layout: the GitHub source and explanation occupy the description column, while the configuration, authorization and installation controls occupy the working column. GitHub App authorization is separate from account sign-in. Configured apps offer a verified installation link and an Authorize GitHub action. A pending authorization exposes a native installation select, its expiry, a connect action and a refresh action. Owners and admins with verified Forge email may mutate connections; other roles can inspect available data. A callback restores the authorized organization before showing its integration content, including memberships beyond the initial organization page.

Connected installations show account identity and explicit state, catalog refresh progress, an inline disconnect confirmation and a repository checkbox list. Checkbox labels include visibility, branch and archived/access state; labels wrap long repository names. Selection changes stay local until Save repositories, with an unsaved count and Discard changes action. Each save changes at most 100 repositories; catalog pages load 25 at a time. Deselection and disconnection explain that future syncs stop while imported history remains. Switching organizations resets local selection and clears the previous organization's queries.

Repositories read selected repository records from the API. Rows show language, default branch, last push, imported open/total PR and commit counts, sync state and last completed sync. Counts link to the repository's PR and commit history; issues have a separate repository link. Queued, running, retrying, succeeded, partial, failed and canceled states pair text with icons and the established neutral, green or amber colors. Authorized managers can start or retry syncs; active work disables duplicate actions. Generated demo repositories explicitly identify their stored synthetic history and disable live synchronization. Sync details expand a history list with import windows, processed counts, retry timing and a recovery explanation. Active lists poll every four seconds. Loading, unavailable, retry, empty and pagination states remain explicit.

### Pull request analytics and evidence

The overview presents server-calculated cycle time, review wait and approval-to-merge distributions in one table: mean, median, P75, P95, included sample count and excluded count. Each evidence link preserves the exact returned UTC merge window, repository and author. Null durations read “Not available”; a measured zero reads “0 sec”. The source section identifies partial observations, completed imports, review gaps, historical dismissals, the conservative input watermark and formula version. Demo organizations carry an explicit generated-history notice. The current open queue remains separate from the merged cohort.

The daily trend draws only server-returned medians. Missing samples create gaps. Points link to their clipped UTC day cohort; a native disclosure exposes daily values, P95 and sample counts in a table. The metric selector changes the observed series without calculating distributions in the browser. The chart has no entrance animation or invented trend line.

PR and commit lists share repository, exact GitHub author and UTC date-time filters. PR controls add state, activity versus merge cohort, metric and eligibility. Filter submission validates the positive date range of at most 366 days. Empty filters default to the backend's last 90 days. Lists and child evidence use signed cursor pagination; a failed next page retains existing records and provides a retry. Tenant-scoped query keys and keyed content reset loaded history when the organization changes. Refresh data updates the current organization's analytics and child evidence after asynchronous imports, without polling incomplete history indefinitely.

PR details display timing exclusions, review evidence, historical approvals and dismissals, lifecycle transitions, explicit member/merge commits and issue references. Commit details display nullable change totals, paginated changed-file metadata and explicit PR relationships; patches are never presented. Repository issue lists explain missing Issues permission and retain access to PR and commit history. Source links render only for validated GitHub URLs; generated records have no fabricated provider links. Coverage distinguishes pending, complete, partial, failed and unavailable using explicit text with the existing semantic colors.

Service rows use 22px padding and horizontal dividers, reducing to 18px and a stacked layout on mobile. The recovery notice appears after a completed check when any service is not healthy; it pairs an alert icon, explanation, and troubleshooting link. No modal, tooltip, or interactive chip system is implemented.

### Application motion and accessibility

Navigation changes background and text color over 150ms; buttons transition colors. There is no entrance animation or rotating loading icon. Reduced-motion preference removes all animation and transition. Focus remains visible on actionable elements and the lifecycle scroller; the programmatic main-content target suppresses its outline.

### Landing actions and delivery story

The coral solid action with charcoal text uses 12px by 20px padding, a 13px label at weight 500, 3px corners, and a matching border; hover changes its fill to lighter coral. Below 800px it uses 12px by 16px padding and a 12px label. Header entry uses an outlined action. Both open `/app`; build notes and system links reach working routes. Landing actions and chapter links use a coral focus ring. Interactive background, color, and border changes take 200ms.

Four source identities, Code, Build, Tests and Production, stay associated with checkpoints throughout the story. Native chapter anchors expose aria-current=step. Story progress runs from 0 to 5 in 0.01 steps and seeks native scroll; Restart story returns to the opening track. Selecting a checkpoint updates its pressed state, source explanation and the Connect code preview. Controls describe planned capabilities without claiming live provider connections.

Native scroll seeks a paused Anime.js timeline across five 1000ms windows. svg.createDrawable draws the delivery line at 4 SVG units over a 2.5-unit guide; svg.createMotionPath supplies the coordinates of a centered 32 by 22 SVG-unit coral code packet with a native bracket glyph. The packet and path share one SVG viewBox. Checkpoint labels sit 15px below the path to clear the packet. Connect joins four sources. Trace follows the original build, passing tests and release error. Understand returns to the test checkpoint; Investigate returns to the related pull request; Automate follows the evidence into a review request. Reverse scrolling retraces the same path. Frame-rate-independent damping uses 1 - exp(-delta * 12), capped at 0.05 seconds, and stops at rest, outside the story and in hidden tabs. ResizeObserver tracks the scene and story to preserve chapter synchronization when previews change height. Native HTML checkpoint controls remain available throughout.

The same labeled SVG, text, code and native anchors are server-rendered and readable without JavaScript. Reduced motion shows the complete line and updates the story immediately without animated travel or text splitting. WebGL is not required. The follower stays within the SVG coordinate system when resized. Native checkpoint buttons expose source-specific names, pressed states and keyboard focus. Unmount cancels animation frames, reverts timelines and removes observers and listeners. Live preference changes are supported.

### Landing workflow examples and integrations

Anime.js splitText keeps clipped heading characters and explanatory words split throughout the tour. A paused timeline has an entrance, a reading interval and an exit; native scroll geometry continuously seeks its position with frame-rate-independent damping, so both directions animate smoothly. Heading entrances use 540 timeline milliseconds plus at most 180 of stagger; explanatory words begin at 120 and use 400 plus at most 200 of stagger. Heading exits begin at 900 with 320 plus at most 180 of stagger; explanatory exits begin at 950 with 280 plus at most 150 of stagger. Chapter evidence metadata shares the timeline, entering with its explanation and exiting with it. These are timeline positions, not a fixed playback duration: scrolling controls the sequence. Investigate reverses the heading travel direction. The first visible passage, including the hero, animates in on initialization. A reading interval accounts for paragraph height, and focusing a visible passage reveals its text. Resize reflows the persistent word wrappers and recalculates scroll thresholds. Frames stop at rest and in hidden tabs. Reduced motion and unmount revert timelines and splits to the original static text; cleanup also removes frames, observers and listeners. Server-rendered text remains readable before initialization or without JavaScript.

Each chapter includes a selectable, syntax-colored 12px code preview with line numbers, highlighted evidence, a plain-language result and an explicit illustrative-example note. Connect switches among GitHub, Actions, JUnit and Sentry extracts. Trace shows CI YAML; Understand shows a developer-added regression test; Investigate shows a candidate null-guard diff; Automate shows illustrative review-rule logic. PR #184, commit 8f3a2c1, original CI #928 and reproduction run #929 connect the example. Source SHAs are explicitly abbreviated and the rule is not presented as a Forge API. Copy writes the displayed snippet and reports success or failure. Long lines scroll locally; reduced motion and no JavaScript retain all five previews. Evidence highlights settle in 380ms; diff addition/removal colors remain stable.

User-initiated illustrative workflow playback highlights Code, Build, Test and Observe over 2400ms with linear Anime.js timing; investigation reverses the selected sequence. Playback disables its button while running. Reduced motion selects the terminal step immediately. The initial integration section is explicitly labeled "Initial integrations (in development)" and identifies GitHub, GitHub Actions, JUnit reports and Sentry. GitLab, Jira, Linear, Jenkins, SonarQube, Playwright, Selenium and AWS appear under "On the roadmap". These local source logos identify planned tools, not customers or endorsements.

## Do's and Don'ts

### Do:

- **Do** use subtle borders and tonal separation for operational surfaces.
- **Do** pair state color with explicit text and an icon.
- **Do** preserve unknown, checking, unavailable, and healthy as distinct states.
- **Do** keep mobile technical content locally scrollable with a visible cue when needed.
- **Do** use real navigation targets and neutral descriptions of health checks.
- **Do** scope the warm charcoal and coral page palette, source colors, display typography, SVG path drawing and checkpoint transitions to the public marketing surface.
- **Do** keep the static delivery track, chapter content, and native navigation available with reduced motion or JavaScript disabled.

### Don't:

- **Don't** fabricate metrics, customer data, connected sources, or working planned controls.
- **Don't** replace the restrained application foundation with the landing's material gradients, depth, or oversized display text.
- **Don't** treat a healthy installation as evidence that an engineering source is connected.
- **Don't** document future provider connections, metrics, or charts as implemented patterns.
