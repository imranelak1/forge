---
name: Forge
description: A dark engineering workbench with a scoped monochrome WebGL cable landing page.
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
  inset: "#191919"
  navigation-hover: "#242424"
  navigation-active: "#2a2a2a"
  navigation-text: "#b7b7b7"
  recovery-background: "#211d17"
  recovery-border: "#504330"
  recovery-text: "#c9bda9"
  landing-background: "#fafafa"
  landing-text: "#111111"
  landing-muted: "#666666"
  landing-line: "#dedede"
  landing-button: "#171717"
  landing-button-text: "#ffffff"
  landing-button-hover: "#383838"
typography:
  landing-display:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "clamp(64px, 7.1vw, 102px)"
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
  label:
    fontFamily: '"Geist Variable", sans-serif'
    fontSize: "12px"
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
  "32": "32px"
components:
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

This document records the implemented Phase 1 foundation in `apps/web`: the overview at `/app`, system status, and setup guide. Authentication, integrations, metrics, charts, and form fields are not implemented and have no established application component conventions here.

The public landing page at `/` adds a scoped monochrome material illustration: a centered graphite cable on a white canvas, large black Geist type, and smooth scroll-driven deformation. Its display scale, shader reflections, and narrative motion belong to this marketing surface. The application retains the compact, flat, neutral conventions below. The simple wordmark remains in use; a new 3D logo is deferred.

**Key Characteristics:**

- Flat charcoal surfaces with subtle borders.
- Geist interface text with system monospace for commands and versions.
- Restrained controls and explicit, text-supported service states.
- Responsive navigation and locally scrollable technical content.
- A scoped public landing with a procedural five-strand WebGL cable and five connected capability chapters.

## Colors

The application palette is almost entirely neutral, with muted green and amber reserved for meaningful state.

Frontmatter records the implemented colors. The companion `.impeccable/design.json` includes generated tonal ramps for the design panel preview; those ramps are not additional application tokens.

### Primary

- **Primary / primary foreground:** the light solid Button variant and its dark label; this variant exists in the primitive, while current page actions use outline buttons.
- **Success:** verified healthy checks and the current phase label.
- **Warning:** unavailable services, migration requirements, and recovery icons.

### Neutral

- **Background:** the main application canvas.
- **Surface:** the navigation rail and command blocks.
- **Inset:** notice and repository-header fill.
- **Muted:** interactive hover fill.
- **Foreground / muted foreground:** primary information and supporting descriptions.
- **Border:** one-pixel panel boundaries and dividers.
- **Ring:** keyboard focus outlines.
- **Navigation text / hover / active:** distinguish ordinary, hovered, and current destinations.
- **Recovery background / border / text:** the subtle amber-tinted recovery notice.

**The Evidence Rule.** Use state colors with a label and icon. An unverified or loading check must remain visually distinct from a healthy check.

### Landing scope

The `landing-*` frontmatter tokens apply only at `/`. White background, black text, gray supporting copy, and fine gray rules frame the cable. Primary actions have a near-black fill and white labels; hover and keyboard focus remain monochrome. The cable uses grayscale reflections, surface detail, and a light signal. This landing palette does not change application service-state semantics.

## Typography

Geist Variable is bundled locally through `@fontsource-variable/geist`; the fallback is sans-serif. Commands and version identifiers use the system monospace stack. The application has no separate display face or oversized marketing typography.

- **Headline:** page titles use the frontmatter headline role; mobile titles reduce to 22px.
- **Title:** section headings use the title role. Service titles are 14px at weight 500; guide section headings are 16px at weight 600.
- **Body:** the base role is 14px. Page descriptions and service explanations use 13px; supporting overview lists and detail copy use 12px.
- **Label:** state labels and most metadata use 12px. Compact health labels and the build badge use 11px.
- **Brand:** the wordmark is 22px, weight 650, with -0.6px tracking; mobile reduces it to 20px.
- **Code:** guide commands use the code role and 1.8 line height in scrollable blocks. Check timestamps use tabular numerals.

Repository empty-state copy is limited to 47ch, system notes to 72ch, and the guide column to 76ch. Labels use sentence case.

The landing reuses Geist with the `landing-display` and `landing-chapter` roles. Hero copy is centered, 15px with 1.7 line height; chapter descriptions are 15px with 1.85 line height and a 310px measure. The closing headline scales from 39px to 72px. At 800 to 1100px chapter headings use 32px; below 800px the hero scales from 61px to 82px and chapter headings from 33px to 43px. At 380px and below the hero is 56px. The landing wordmark is 30px, weight 680, with -1.2px tracking and a plain period; the footer wordmark is 26px.

## Layout

The desktop shell is a 240px rail beside a flexible content area. The context bar is 56px tall. Main content is centered with a 1400px maximum width and 32px padding. Section spacing generally uses 24px or 32px; compact metadata uses 6–16px gaps. These are observed values, not an enforced mathematical scale.

At 1100px and below, main padding reduces to 24px and the health strip wraps its checks with labels above values. At 760px and below, the rail becomes a top navigation area, main padding becomes 24px vertically and 20px horizontally, and the context bar, installation label, planned navigation, and sidebar footer are hidden. Page headings and service rows stack. The two-column foundation detail becomes one column with a horizontal divider.

The lifecycle has seven equal desktop columns. On mobile, stages keep a 94px width within a keyboard-focusable horizontal scroller, followed by an explicit scroll hint. Repository headers reduce from four columns to two. Command blocks scroll within their own boundary. Keep the page itself free of horizontal overflow.

The landing header has a 1600px maximum width, 5% side padding, and an 84px height. The centered hero and sticky cable stage use the viewport height minus the header; the hero has a 740px minimum height. The cable remains centered while five chapters alternate their copy between the outer columns of a 1250px grid with a 36% center column. Chapters have a 105svh minimum height and 5% side padding. At 800 to 1100px the center column reduces to 34% and the cable caption is hidden.

Below 800px, the landing header is 72px tall with 24px side padding; its secondary navigation is hidden while platform entry remains visible. The hero has a 700px minimum height. The cable occupies the upper reading area, with chapter copy beginning at 43svh and using a 440px maximum measure. Chapters have a 108svh minimum height and 27px side padding; all five chapter links remain visible with 44px minimum targets. At 380px and below chapter side padding becomes 22px. At any width when the viewport is at most 600px high, the cable stage returns to normal document flow at 400px high, followed by chapters with a 550px minimum height.

## Elevation & Depth

The application implements no shadows, gradients, blur, or floating surfaces. Depth comes from restrained tonal differences and one-pixel borders. Containers sit directly in the document flow. Do not add elevation to ordinary data panels without a new design decision.

The landing cable uses real WebGL geometry with custom vertex and fragment shaders. Grayscale studio reflections, subtle woven surface detail, and background grain establish material depth. An orthographic camera keeps the composition centered; a small mouse response turns the object. This treatment is confined to the illustration; landing copy and controls retain flat surfaces and fine rules.

## Shapes

Forms are compact rectangles: badges use the badge radius, navigation uses the navigation radius, and buttons, notices, tables, service lists, and code blocks use the control radius. Circular geometry appears in state icons rather than pill-shaped containers. Lucide stroke icons provide navigation and status imagery; the shipping favicon is SVG. There are no shipping raster assets.

Landing actions use 3px corners. The cable is a procedural five-strand mesh that moves between separated, braided, opened, and closed-loop forms. Its fallback is a static SVG of five curved strokes. It is an illustration, not a replacement logo or a reusable application panel style.

## Components

### Buttons

The shared primitive provides primary, outline, and ghost variants. Default controls are 36px tall with 14px horizontal padding and 8px icon gaps. Small controls are 32px tall with 12px padding; icon controls are 36px square. Icons inside buttons are 16px.

Outline buttons have a one-pixel border and canvas fill, changing to muted fill on hover. Ghost buttons gain muted fill on hover. Primary buttons reduce their background opacity to 90% on hover. Disabled controls use 50% opacity and suppress pointer events. Color transitions use Tailwind's default 150ms timing. Keyboard focus uses a two-pixel ring offset by four pixels.

### Navigation and links

Desktop navigation uses 13px labels, 17px icons, and 9px by 12px padding. Hover and current-page fills are separate neutral tones; current links carry `aria-current="page"`. Mobile navigation uses 12px labels and 9px by 10px padding. Planned destinations are static text, not controls. Text links use a small adjacent arrow and underline on hover. A keyboard-visible skip link targets the main content.

### Status indicators

Indicators pair a 14px icon with a 12px label and 6px gap. Healthy is green with a check circle; unavailable and migration-required states are amber with an alert circle; checking and not-verified states are neutral with a dashed circle. State labels do not wrap. The compact strip and detailed list share this vocabulary.

Checks refresh every 30 seconds while mounted. Initial loading displays Checking. During refresh, the action displays Checking… and is disabled while previous check results remain visible. Descriptions explain what each check examines without claiming success. Live regions announce updates; the service list exposes busy state.

### Containers and empty states

Repository and service containers use one-pixel borders, the control radius, and clipped corners. Repository headers have inset fill and 11px by 20px padding. The empty state has centered content, 32px by 24px padding, an outlined repository icon, a concise explanation, and a real setup-guide link. It displays no synthetic activity or metrics.

Service rows use 22px padding and horizontal dividers, reducing to 18px and a stacked layout on mobile. The recovery notice appears after a completed check when any service is not healthy; it pairs an alert icon, explanation, and troubleshooting link. No modal, input, tooltip, or interactive chip system exists yet.

### Application motion and accessibility

Navigation changes background and text color over 150ms; buttons transition colors. There is no entrance animation or rotating loading icon. Reduced-motion preference removes all animation and transition. Focus remains visible on actionable elements and the lifecycle scroller; the programmatic main-content target suppresses its outline.

### Landing actions and cable

The near-black solid action uses 12px by 20px padding, a 13px label at weight 500, 3px corners, and a matching border; hover changes its fill to gray. Below 800px it uses 12px by 16px padding and a 12px label. Header entry uses an outlined action. Both open `/app`; build notes and system links reach working routes. Landing actions and chapter links use a black focus ring. Interactive background, color, and border changes take 200ms.

The cable represents Connect, Trace, Understand, Investigate, and Automate. Native anchor links navigate to chapters, while the active chapter receives `aria-current="step"`. Hover or keyboard focus emphasizes an individual strand. The accompanying descriptions and in-development disclosures make clear that the capability tour illustrates planned work.

Native scroll position drives shader progress from 0 to 5. Frame-rate-independent exponential damping smooths progress and the small mouse response. Five strands join, carry a signal, open for inspection, reverse the signal during investigation, and close a loop for automation. Reverse scrolling reverses the deformation. Rendering stops when motion settles, when the story leaves view, and when the tab is hidden. There is no autoplay loop or scroll hijacking. Pixel ratio is capped at 1.75 on desktop and 1.25 below 800px.

Server-rendered text, native links, and the static SVG cable remain available without JavaScript. Reduced motion skips WebGL initialization and uses the static cable; unavailable WebGL, shader failure, and context loss also retain the fallback. Context restoration resumes rendering. Live preference changes dispose or initialize the renderer; cleanup disposes geometry, materials, observers, listeners, and the WebGL context. The decorative renderer is hidden from assistive technology. The page also has a keyboard-visible skip link to main content.

## Do's and Don'ts

### Do:

- **Do** use subtle borders and tonal separation for operational surfaces.
- **Do** pair state color with explicit text and an icon.
- **Do** preserve unknown, checking, unavailable, and healthy as distinct states.
- **Do** keep mobile technical content locally scrollable with a visible cue when needed.
- **Do** use real navigation targets and neutral descriptions of health checks.
- **Do** scope the monochrome landing palette, display typography, shader materials, and cable motion to the public marketing surface.
- **Do** keep the static cable, chapter content, and native navigation available with reduced motion, JavaScript disabled, or unavailable WebGL.

### Don't:

- **Don't** fabricate metrics, customer data, connected sources, or working planned controls.
- **Don't** replace the restrained application foundation with the landing's material gradients, depth, or oversized display text.
- **Don't** treat a healthy installation as evidence that an engineering source is connected.
- **Don't** document future forms, charts, or authentication screens as implemented patterns.
