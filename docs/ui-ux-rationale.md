# UI and mobile UX rationale

This document records the research behind the GPS Art Wizard interface refresh
and turns general design guidance into product-specific decisions. The goal is
not to imitate a fashionable landing page. It is to help a first-time user move
from an idea to a route they understand and can safely export.

## What the interface must help users do

The core journey has three tasks:

1. Describe a drawing, place, activity, and approximate distance.
2. Compare the returned street route with the intended drawing.
3. Adjust the route if necessary, review warnings, and download it.

Everything else—candidate diagnostics, placement parameters, earlier attempts,
and gallery publishing—is supporting information. The visual hierarchy should
reflect that difference.

The prompt goes directly to the generation pipeline; internal interpretation is
not exposed as another form for the user to review. The result page shows route
alternatives side by side with likeness, distance, climb, and readiness instead
of hiding those trade-offs in a select. Readiness findings are buttons: choosing
one highlights and fits its mapped segment, while a visible reset returns to the
full route. Start-point, first-direction, and routing preferences stay together
in one optional disclosure before the primary action.

The optional result lab keeps pre-route tools focused on improving the route.
Inkproof asks for expected GPS accuracy, returns a small score summary, and uses
a single map toggle for the exact fragile sections.

## Anti-slop content and visual standard

The Cambridge Dictionary defines AI slop as low-quality digital content made
with artificial intelligence. For this product, the useful test is not whether
AI touched the work; it is whether the interface is generic, repetitive,
decorative, or vague enough to get in the user's way.

The interface therefore follows these rules:

- Headings name the task or state: “Create GPS art on real streets”, “Checks passed”,
  “Review before download”, and “Street route unavailable”. They do not make
  lifestyle claims.
- Labels name the requested information, and buttons state the action and
  object: “Drawing and location”, “Find routes”, and “Publish map”.
- Safety and privacy information is specific. It identifies access, crossings,
  traffic, surfaces, location, visible street names, and unpublished data.
- The same explanation appears once. Generic step narration, slogans,
  congratulatory copy, and “magic” or surprise language are excluded.
- A bordered surface groups a real unit of work, such as the planner form or
  map. Metrics use compact definition rows instead of a dashboard of identical
  cards. Gradients, glass effects, ornamental pills, and decorative badges are
  not part of the visual language.

W3C recommends familiar words, short sentences, descriptive headings and
labels, and content that is as simple as the subject allows. GOV.UK similarly
recommends mobile-first single-column reading, short direct labels, restrained
lead text, and removing unnecessary decoration rather than using images to make
a page look more interesting. Those standards make the anti-slop decisions
testable as content and service-design choices instead of matters of taste.

Sources: [Cambridge Dictionary — AI slop](https://dictionary.cambridge.org/us/dictionary/english/ai-slop),
[W3C — Clear and understandable content](https://www.w3.org/WAI/WCAG2/supplemental/objectives/o3-clear-content/),
[W3C — Writing for web accessibility](https://www.w3.org/WAI/tips/writing/),
[W3C technique G153](https://www.w3.org/WAI/WCAG22/Techniques/general/G153),
[GOV.UK layout](https://design-system.service.gov.uk/styles/layout/),
[GOV.UK text input](https://design-system.service.gov.uk/components/text-input/),
and [GOV.UK images](https://design-system.service.gov.uk/styles/images/).

## Research findings and design decisions

### 2026-08 service-design audit

This refresh treats route creation as one end-to-end service rather than a set
of product features. GOV.UK's Service Standard says that users should succeed
first time with minimum help and receive a consistent experience across the
devices they use. Its service-design introduction adds that a good service
minimises steps, makes its purpose and starting action clear, uses familiar
conventions, and never leaves the user at a dead end. The Design Council's
Double Diamond reinforces separating evidence gathering and problem definition
from solution development.

The audit mapped each visible touchpoint to the user's next decision:

| Touchpoint | Friction found | Implemented response |
|---|---|---|
| Arrival | “Planner” and “lab” describe the product's machinery rather than the user's outcome. | The navigation now says “Create route”, the heading promises GPS art on real streets, and the decorative “Live route lab” label was removed. |
| Route request | Three valid starting methods were present without a clear relationship. | Free text remains the single primary path. Separate fields and image input are grouped under “Other ways to start”; the simpler structured path appears before the specialist image path. |
| Form completion | Optional shape choices could be mistaken for a required step. | The common-shape legend now marks the choices as optional, while labels remain visible above every input. |
| Waiting | Users need reassurance without fabricated server progress. | The real elapsed time, cancel action, plain-language messages, reduced-motion handling, and illustrative-stage disclosure remain; internal “lab” terminology does not. |
| Review and export | A plausible picture can still be an unusable route. | The existing route checks, explicit review state, editing path, and fail-closed export remain the visible decision sequence. |
| Return visit | The former CSS-drawn mark and favicon did not share one clear identity. | A scalable route-shaped mark with visible start and finish points now unifies the header and favicon. Rounded geometry keeps it friendly; restrained colour and a simple silhouette keep it legible at small sizes. |

This is an evidence-based heuristic audit of the implemented service, not a
substitute for observing target users. The next research round should watch
first-time runners and cyclists complete the full idea → wait → review → export
journey, then measure first-attempt completion, correction rate, time to the
primary action, and whether users understand why an export can be unavailable.

Sources: [GOV.UK — Make the service simple to use](https://www.gov.uk/service-manual/service-standard/point-4-make-the-service-simple-to-use),
[GOV.UK — Designing good government services](https://www.gov.uk/service-manual/design/introduction-designing-government-services),
[GOV.UK — Map and understand a user's whole problem](https://www.gov.uk/service-manual/design/map-a-users-whole-problem),
[GOV.UK — Structuring forms](https://www.gov.uk/service-manual/design/form-structure),
[Design Council — Double Diamond](https://www.designcouncil.org.uk/resources/the-double-diamond/),
[Nielsen Norman Group — usability heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/),
[Baymard — form design research](https://baymard.com/learn/form-design), and
[Parhi, Karlson, and Bederson — one-handed target-size study](https://www.microsoft.com/en-us/research/wp-content/uploads/2006/01/parhi-mobileHCI06.pdf).

### Keep the primary task obvious

Apple's iOS guidance recommends limiting onscreen controls so people can focus
on the primary task, while keeping secondary actions discoverable. The planner
now opens with an outcome-specific heading and one short explanation beside a
clearly bounded input area. One free-text request and one primary action stay
visible; separate-field and image starts are labelled, collapsed alternatives.
The generic three-step story, ornamental labels, and competing card treatments
remain excluded in favour of a neutral canvas and consistent borders.

Source: [Apple Human Interface Guidelines — Designing for iOS](https://developer.apple.com/design/human-interface-guidelines/designing-for-ios/).

### Reveal technical detail only when it helps

The GOV.UK Design System recommends a details disclosure for information that
only some users need, and warns against hiding information most users require.
The route map, headline quality, distance, shape match, route choices, and
download state remain visible. Individual quality gates, route parameters,
history, and audit tables stay in labelled disclosures.

Source: [GOV.UK Design System — Details](https://design-system.service.gov.uk/components/details/).

### Use large, well-spaced controls

WCAG 2.2 requires pointer targets to be at least 24 by 24 CSS pixels unless a
spacing exception applies, and its enhanced target is 44 by 44. This refresh
uses a 44-pixel practical floor and generally renders primary form controls at
48 pixels. Map edit handles increased from 28 to 44 pixels; primary buttons,
idea choices, radios, selects, and map zoom controls are larger as well.

Parhi, Karlson, and Bederson's controlled one-handed touchscreen study found
that discrete targets around 9.2 mm were sufficient without degrading
performance or preference. The interface therefore keeps the standard's
44-pixel practical floor and uses 48-pixel mobile targets for idea choices and
collapsed alternative-start controls instead of treating 24 pixels as a design
target.

Sources: [WCAG 2.2 target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum),
[WCAG 2.2](https://www.w3.org/TR/WCAG22/), and
[the one-handed target-size study](https://www.microsoft.com/en-us/research/wp-content/uploads/2006/01/parhi-mobileHCI06.pdf).

### Match the control to the question

The GOV.UK Design System advises using selects sparingly. The 230-destination list
remains a native select, which stays compact and uses the platform's familiar
mobile picker. Hungary's KSH top 50, 44 additional Lake Balaton shore
municipalities, and the 136-city European coverage set are separate labelled
option groups. Siófok stays in the Hungary group instead of appearing twice.
This keeps the long list structured and its option values unique. A two-item
running/cycling choice is faster to scan as visible radio
options, so activity uses two large radio targets while distance remains a
labelled number input.

Source: [GOV.UK Design System — Select](https://design-system.service.gov.uk/components/select/).

### Keep a large shape catalog findable

Exposing 158 choices as one uninterrupted field of chips would make scanning
slow and bury familiar options. Six common shapes stay beside the prompt. The
full catalog is grouped by plain-language category and has a labelled search
that filters both names and categories, reports the remaining count, and gives
an explicit empty result. This follows the W3C preference for familiar,
unambiguous symbols while retaining text labels instead of relying on glyphs.

Source: [W3C COGA — Use Clear and Familiar Icons and Symbols](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o1p07-icons-used/).

### Keep labels and instructions concise but explicit

WCAG requires labels or instructions when content needs user input and notes
that too much instruction can be as harmful as too little. Each planner field
has a visible label; the route prompt has one short hint and an always-visible
character count. The introduction explains what the planner produces; controls
do not repeat the workflow.

Source: [WCAG 2.2 labels or instructions](https://www.w3.org/WAI/WCAG22/Understanding/labels-or-instructions.html).

### Make errors recoverable

GOV.UK validation guidance says to explain what went wrong, retain the user's
entered values, and focus the error summary. The application already preserves
the route prompt, focuses its error card, shows the backend's actionable detail,
and offers an immediate retry. Edit errors remain beside the editor and do not
close it or discard control points.

Sources: [GOV.UK validation pattern](https://design-system.service.gov.uk/patterns/validation/) and [error-message guidance](https://design-system.service.gov.uk/components/error-message/).

### Make a long search understandable without inventing progress

Route generation is synchronous and can spend time comparing placements and
running Directions requests. A generic spinner makes that wait feel stalled,
but a fabricated percentage would imply server progress the API does not send.
The generation view therefore combines:

- a real elapsed-seconds counter;
- a GPS-art route animation and moving route marker;
- rotating, task-specific status messages and short educational facts;
- four stages whose timing is explicitly labelled illustrative;
- a visible cancel action that aborts the browser request.

The container uses `aria-busy=true`; the rotating message is a polite live
status, and the indeterminate track is labelled as route generation in
progress. Animation does not carry unique information: with
`prefers-reduced-motion: reduce`, the route, marker, signal, and progress
animations stop while the same text, elapsed time, stages, and cancel action
remain available.

Sources: [WAI-ARIA status role](https://www.w3.org/WAI/ARIA/apg/patterns/status/) and
[WCAG animation from interactions](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).

### Fail closed when there is no street route

An accurate drawing overlaid on a map is not a usable GPS route when it crosses
buildings, water, or disconnected land. The result and editor therefore keep a
hard distinction between a road-routed candidate and an internal straight-line
diagnostic. `snapped=false` never enables approval, GPX/TCX download, or gallery
publication. Generation and edited-route requests return an actionable HTTP 503
instead, preserve the user's idea or control points, and offer retry rather than
asking the user to waive a graph-connectivity failure.

### Validate fields without hiding the way forward

WCAG requires detected errors to identify the affected field in text and, when
the fix is known, explain how to correct it. Native browser messages vary and
usually expose one problem at a time, so the planner keeps HTML constraints but
adds persistent inline messages. Invalid controls use `aria-invalid` and
`aria-errormessage`; submission focuses the first field that needs attention,
and corrections clear the message without erasing the user's input.

The free-text idea is deliberately not restricted to ASCII or a narrow English
pattern. It is Unicode-normalised, whitespace is collapsed, invisible control
characters are rejected, and a letter or number is required while accented and
non-Latin text remains valid. Its copy explicitly welcomes drawings outside the
catalog, while generated results identify that their outline was made from the
description and ask the user to compare it with the street route. The structured
suggestion form can be stricter:
city and activity use allowlists, while distance must be a whole number within
the activity-specific range. A running-to-cycling switch that raises the
minimum distance announces that change instead of silently replacing the
value.

The same prompt length, normalisation, and malformed-character rules run in the
FastAPI request model. Client checks provide fast feedback, but server checks
remain the security boundary because browser validation can be bypassed.

Sources: [WCAG error identification](https://www.w3.org/WAI/WCAG22/Understanding/error-identification), [MDN client-side form validation](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation), [MDN `aria-errormessage`](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Attributes/aria-errormessage), and [OWASP input validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html).

### Preserve familiar map behaviour

Apple recommends keeping maps interactive, avoiding persistent overlays that
obscure them, maintaining contrast for custom controls, and keeping attribution
visible. Route selection stays above the map, editing controls stay below it,
and the map retains standard pan and zoom interactions. The route and intended
drawing remain distinct, with start, finish, and important points explained in
the caption.

Source: [Apple Human Interface Guidelines — Maps](https://developer.apple.com/design/human-interface-guidelines/maps/).

### Support more than dragging

WCAG 2.2 calls out dragging as an interaction that needs an alternative unless
dragging is essential. Numbered edit markers can still be dragged on a touch
screen, but they are also keyboard focusable and move with the arrow keys;
holding Shift makes a larger adjustment. Start-over and discard actions remain
available outside the map.

Source: [WCAG 2.2, criterion 2.5.7](https://www.w3.org/TR/WCAG22/#dragging-movements).

## Responsive behaviour

- Desktop uses a two-column planning view: a short explanation first and the
  route form second.
- Tablet and mobile stack the explanation above the form without inserting an
  extra step list between the user and the first field.
- Mobile uses two-column idea buttons, stacks all suggestion fields, and keeps
  the planner and gallery links visible. The structured suggestion action sits
  in a separate row below every field: right-aligned on wider screens and full
  width on phones. Field help or validation text can no longer move it into an
  ambiguous column beside the inputs.
- Route results become a single column before the layout can squeeze the map or
  sidebar. Metrics become labelled rows on phones and every primary control
  keeps at least a 44-pixel target.
- Tables become labelled rows rather than forcing horizontal scrolling.
- Reduced-motion preferences disable nonessential transitions and animation.

Playwright verifies desktop and Pixel 7-sized mobile Chromium, checks initial
and result screens for horizontal overflow, confirms key control heights, and
exercises keyboard route-point movement in addition to the touch-oriented
layout.
