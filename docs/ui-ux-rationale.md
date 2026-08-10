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

## Anti-slop content and visual standard

The Cambridge Dictionary defines AI slop as low-quality digital content made
with artificial intelligence. For this product, the useful test is not whether
AI touched the work; it is whether the interface is generic, repetitive,
decorative, or vague enough to get in the user's way.

The interface therefore follows these rules:

- Headings name the task or state: “Plan a GPS art route”, “Checks passed”,
  and “Review before download”. They do not make lifestyle claims.
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

### Keep the primary task obvious

Apple's iOS guidance recommends limiting onscreen controls so people can focus
on the primary task, while keeping secondary actions discoverable. The planner
now opens with a task-specific heading and one short explanation beside a
clearly bounded input area. The generic three-step story, decorative gradient,
ornamental labels, and competing card treatments were removed in favour of a
neutral canvas, consistent borders, and one primary action.

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

Sources: [WCAG 2.2 target-size guidance](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum) and [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

### Match the control to the question

The GOV.UK Design System advises using selects sparingly. The 80-city list
remains a native select, which stays compact and uses the platform's familiar
mobile picker. Hungary's KSH top 50 and the 30-city European coverage set are
separate labelled option groups, so users do not have to scan one undifferentiated
list. A two-item running/cycling choice is faster to scan as visible radio
options, so activity uses two large radio targets while distance remains a
labelled number input.

Source: [GOV.UK Design System — Select](https://design-system.service.gov.uk/components/select/).

### Keep a large shape catalog findable

Exposing 86 choices as one uninterrupted field of chips would make scanning
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
non-Latin text remains valid. The structured suggestion form can be stricter:
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
