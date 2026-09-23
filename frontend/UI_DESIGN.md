# Paceasso: cartographic studio

## September 23 update: live gallery example

The homepage now features a real public gallery thumbnail, changing it on each
page load when at least two images are available. The caption stays generic
because the gallery does not store city or shape names. Empty/unavailable
galleries show text rather than a made-up map, and the historical bundled
Budapest WebP is no longer preloaded. Final-polish progress names the enclosing
check even while its nested street-routing call is running.

## September 11 correction: actual cartography and a mischievous identity

This revision superseded the invented street-grid illustration and W-pin logo
described in the historical notes below. At the time, the homepage bundled a WebP-encoded
Budapest heart preview from the project's public gallery. Its unchanged PNG source is documented
in `public/budapest-heart-route.source.md`. The entire map, including attribution,
stays visible at its original aspect ratio and can be opened at full resolution.
Labels distinguish the planned street route, reference drawing and review sections;
no recorded activity, guaranteed access or field verification is claimed.

The original SVG identity now traces an angular fox face with a route-start marker,
one open eye and a wink. It brings playfulness through the mark and the “few detours”
caption, without inventing geography. Header, favicon and empty-gallery mark share
the geometry. Both compact and desktop layouts retained the actual map example.

Verification for this revision: production build and 10 unit tests passed;
56 planner checks passed across desktop/mobile Chromium; eight focused
Firefox/WebKit checks passed. Screenshots were inspected at 1440, 390 and 320px.
The screenshot harness waits for the bundled map to decode before capture.
The source and bundled image SHA-256 both equal
`554880271d6bb7a0ffd23dfa8e2b9b331b48d1c995c3d6784b4b5e14957f816e`.

The interface uses warm paper surfaces, forest-green ink and terracotta route
lines. A restrained serif headline and an original street-grid illustration
give the planner a recognizable identity without adding another interaction.
The illustration is explicitly labelled as illustrative and hidden from
assistive technology; it is not a generated route or a real map.

## Research applied

Research reviewed on 10 September 2026:

- [Nielsen Norman Group: Visual Hierarchy in UX](https://www.nngroup.com/articles/visual-hierarchy-ux-definition/): emphasize the title, current step and primary action; use spacing to group related controls.
- [Nielsen Norman Group: The Characteristics of Minimalism in Web Design](https://www.nngroup.com/articles/characteristics-minimalism/): use typography and intentional negative space for character, with a restrained palette.
- [W3C: Contrast (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum): use dark foregrounds on light surfaces and avoid faded progress labels.
- [W3C: What's New in WCAG 2.2](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/): preserve visible focus and comfortably sized targets. Primary controls retain a minimum 44 CSS-pixel height.

## Scope and maintenance

`src/studio.css` is the visual layer, loaded after the existing feature styles.
It styles the planner, shared controls, result cards and gallery. The existing
breakpoints and interaction order are preserved. On compact screens, the
decorative illustration is omitted and the progress indicator uses three columns.
The header mark and favicon share the same colors and geometry. No remote
fonts, image services or new dependencies are needed.

No event handlers, API payloads, route generation, downloads or application
state were changed. The additional JSX is presentation only.

## Local visual review

With Vite running at `http://127.0.0.1:4173`, run from `frontend`:

```sh
node scripts/studio-preview.mjs
```

This uses the existing mocked API fixtures to capture desktop, mobile and
320-pixel planner screenshots, plus result and gallery screenshots, under
`.tmp/studio-*.png`. It checks horizontal overflow on the planner and waits for
the result map to render. Map tiles and generated routes are test fixtures.

The existing Playwright suites cover navigation, keyboard access, responsive
layout, request review, generation, route editing, exports and gallery flows.
These checks are regression evidence, not a complete WCAG conformance audit.

## First-pass verification (10 September 2026)

- Production build: passed.
- Unit tests: 10 passed.
- Desktop/mobile Chromium: 227 passed in the full 228-case run. The one
  spacing failure was corrected (48px maximum column gap, 44px vertical
  padding), and that desktop test passed on a targeted rerun.
- WebKit: all 51 planner and result tests passed.
- Firefox: unable to create a test page; Playwright raised
  `browserContext.newPage: Cannot read properties of undefined (reading '_page')`
  before the application loaded. Firefox verification remains unavailable in
  this environment.
- The Windows test servers did not exit automatically after their workers
  finished. Stopping the identified Vite processes released the final reports;
  WebKit and the corrected Chromium case both exited successfully.
- Planner screenshots reviewed at 1440, 390 and 320px; result and gallery
  screenshots also captured. No planner horizontal overflow at these widths.
- Measured palette contrast: white on primary green 7.41:1; muted text on
  the paper surface 5.11:1. These are palette checks, not a full-page audit.
- `git diff --check`: passed. No commit or push performed.

## Extended visual audit and refinement (11 September 2026)

This is a source-informed expert review of the implemented UI, not a user
study. The goal is a memorable GPS-art identity with a clear route-planning
task. User preference or brand recognition has not been empirically measured.

| Area reviewed | Finding | Implemented response |
| --- | --- | --- |
| Identity | The earlier heart-wave badge did not explicitly communicate location or the Wizard name. | Original map-pin outline with a W-shaped route and two endpoints, matching across the header, favicon and empty gallery. |
| Action hierarchy | Solid navigation styling competed with the primary form action. | A pale selected navigation tab with an underline; the main action retains the solid green treatment. |
| Shape recognition | Character-based shapes varied in weight and proportions across platforms. | Six original SVG outlines on a shared 24-unit grid, retaining every visible text label. |
| Mobile density | The desktop-scale heading delayed access to the form. | A smaller mobile heading and tighter intro spacing without hiding instructions or controls. |
| Map hierarchy | The illustration needs to distinguish the route from street context. | Quiet grid and streets, terracotta route, clearly marked endpoint, and an explicit illustrative caption. |
| Result selection | The selected route needed to remain distinct from the surrounding cards. | Green-tinted surface, dark border and inset left edge; existing semantic selected state retained. |
| Empty states | The empty gallery was informative but visually anonymous. | The new brand mark, a paper card and a more expressive heading; existing state-specific explanations remain intact. |
| Accessibility | Aesthetic changes must preserve labelled controls, contrast and focus. | Decorative SVGs are hidden from assistive technology; 44px primary targets and visible focus remain. Thumbnail focus is inset to avoid clipping. |
| Delivery | The browser chrome and tab icon did not fully match the app. | Theme color now matches the canvas; vector assets need no remote font or image dependency. |

### Additional research and how it informed the changes

- [NN/g: The Aesthetic-Usability Effect](https://www.nngroup.com/articles/aesthetic-usability-effect/): attractive presentation can improve perceived usability, but does not establish actual usability. This is why functional and visual verification accompany the redesign.
- [GOV.UK: Button](https://design-system.service.gov.uk/components/button/): competing primary actions weaken the hierarchy. The navigation is now visually quieter than the route-review button.
- [NN/g: Icon Usability](https://www.nngroup.com/articles/icon-usability/): icons can be ambiguous, so the shape names remain alongside the new symbols.
- [IBM Design Language: Pictogram design](https://www.ibm.com/design/language/iconography/pictograms/design/): consistent grids, proportions and stroke treatment support a coherent family. The app uses original geometry; no IBM artwork is reused.
- [Mapbox: Guide to map design](https://www.mapbox.com/insights/map-design-process): contrast, hierarchy, density and legibility inform the quiet context and prominent route in the illustration. The actual routing and map data are unchanged.
- [NN/g: Designing Empty States](https://www.nngroup.com/articles/empty-state-interface-design/): empty panels should explain what happened and what users can do. Existing loading, unavailable, error and empty messages remain separate.
- [W3C: Reflow](https://www.w3.org/WAI/WCAG21/Understanding/reflow): narrow-width checks include 320 CSS pixels. The decorative illustration disappears on compact screens while the functional content remains available.

The logo is original artwork designed for this project. Its distinctiveness
is a design intention, not a trademark-clearance or user-recognition claim.
The W is a route motif, the enclosing pin supplies location context, and the
two endpoints connect the mark to GPS-track drawing. SVG keeps it crisp at
header and favicon sizes.

### Final refinement verification

- `npm run build`: passed.
- `npm run test:unit`: 10 passed.
- Planner, results and gallery-resilience Playwright suites: 126 passed across
  desktop and mobile Chromium (5 minutes).
- Targeted Firefox/WebKit checks of the logo/favicon, compact layout,
  activation targets and shape selection: 8 passed. The earlier Firefox
  startup issue did not recur in this run.
- Final planner screenshots reviewed at 1440, 390 and 320px; the empty gallery
  and selected-result styling were also visually inspected using API fixtures.
- `git diff --check`: passed. Event handlers, request payloads and route
  processing were reviewed and remain unchanged.
