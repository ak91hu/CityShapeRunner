# Paceasso: cartographic studio

## Planner examples and waiting games

Quick examples draw six choices from a shuffled catalogue. **Show different
ideas** advances to unseen choices before cycling through the catalogue; it
keeps the user's sentence and keyboard focus intact. Choosing an example is
still an explicit replacement of the full request. The waiting sketch challenge
also shuffles each twelve-sketch round without repeating a sketch within it.

Result cards explain their starting-point distance from the recommended route
(straight-line distance, not travel distance), distinguish likeness from passing
all checks, and announce the selected option. The highest-ranked measured route
remains first; variety never overrides the final quality ranking.

Document-level scrolling is immediate so keyboard focus followed by a pointer
click cannot race an unfinished scroll and miss a disclosure. The idea-refresh
checks exercise keyboard activation as well as pointer clicks; they do not
assume that every browser focuses an unfocused button when clicked.

Each page load selects a complete random request from the catalog. Session
storage excludes the previous example in that tab; blocked storage falls back
to random selection. Only the initial catalog example is saved. User edits and
view changes preserve the current sentence, and campaign links keep their preset.

The waiting screen offers twelve guessing sketches and an optional Shape Sprint
runner using the same twelve outlines. Players jump over three obstacle types
with touch, Space or Arrow Up, choose a runner, pause and restart. Animation
starts only on request and pauses on disclosure close or backgrounding the tab.
Finishing or cancelling generation removes the game.
Mobile Cancel stays outside the scrollable game content. Late tool responses
cannot reopen dialogs while the result view is inactive.

## October 19 update: usability review across mobile and desktop

The main review action now follows the idea field before optional examples.
Examples explain that they replace a complete request, then return focus to the
editable sentence. Phone results use vertically stacked route choices and a
single grid column, removing the measured 28px overflow at 320px.

Route choices retain native button semantics, state-specific headings and text
contrast have been corrected, and compact waiting dialogs manage background
inertness, keyboard focus and orientation changes. Initial prompt focus is
applied once per DOM node, avoiding repeated focus in WebKit with StrictMode.
Stage transitions finish scrolling immediately before controls can be used.
The default Vite proxy now covers all client API resources, including templates.

The expert review, primary research sources, measurements, test methodology and
limitations are recorded in the [usability report](../reports/2026-10-19-usability.md). The portable report
retains before/after screenshots, initial failing runs and targeted reruns;
its final audit is tied to source SHA-256 hashes. This is an expert and browser
evaluation, with a separate live API smoke check, not a participant study or
GPS accuracy benchmark.

## October 18 update: faster measurements with repair time preserved

Snap and Directions now reuse one bounded HTTP pool per workflow. Request
counters update before the provider responds, including retries. Batched Fréchet
phase/direction comparisons preserve the original metric values and resolution.
The 35-second exploration budget no longer truncates recognition/distance repairs
or connectivity retries; these retain the 175-second workflow budget.

The waiting challenge now has eight sketches, a running score, and one answer
per question. Its illustration remains distinct from the actual provider-routed
preview. The elapsed timer measures wall time even after background-tab throttling.
Seed zero now uses the same city-sector sampling as other explicit seeds.

Verification: 864 backend tests passed (eight temporary-directory setup failures
were rerun successfully in a fresh workspace directory), 142 desktop/mobile
Chromium checks and six Firefox/WebKit generation checks passed, alongside 13
frontend unit tests, the production build, Ruff and application type checking.
Waiting/game screenshots at 1440, 390 and 320px showed no horizontal overflow;
the mobile Cancel action remained visible. Local synthetic measurements kept
the same result: scheduling 0.452s → 0.153s, and four-variant Fréchet calculation
10.845ms → 5.007ms at 64 samples and 68.878ms → 50.871ms at 256 samples.
These are isolated measurements, not production end-to-end timings.

## October 16 update: creative search and an interactive wait

The generation view now adds live counts of measured search areas and unique
street-connected candidates to its existing placement and Directions counters.
Counters retain their maximum when parallel workers deliver events out of order.
Stages advance from server events; no estimated percentage or invented remaining
time is shown. After 12 seconds without an update, a stable message explains the
quiet period while the elapsed timer continues.

An optional three-sketch guessing game provides original SVG outlines, verbal
clues, labelled answer buttons and GPS-art tips. It runs locally, independently
of generation, and supports keyboard use and reduced motion. It starts collapsed
on mobile. Opening or answering scrolls the game into view within the progress
panel, while Cancel remains outside that scroll area and visible at the bottom.
The provisional provider-routed map and guarded final download flow remain.

The backend samples fresh city sectors per request, evaluates up to three
shortlisted placements concurrently and stops optional search work at the
configured advisory budget. See the README for configuration, seed semantics
and the distinction between a search budget and a response-time guarantee.

Verification: the full backend run passed 849 tests; final scheduling/route and
budget/benchmark follow-ups passed 406 and 97 tests respectively. Type checking
passed for all 71 application modules and Ruff passed. Frontend validation passed
13 unit tests, 38 desktop/mobile generation-and-workflow checks, and six focused
checks each on Chromium desktop/mobile and Firefox/WebKit after the game scroll
refinement. The production build passed. Waiting, game-answer and early-map
screenshots were reviewed at 1440, 390 and 320px; Cancel stayed inside the mobile
viewport and no horizontal overflow was found.

The scheduling microbenchmark (five pairs, 150ms synthetic latency per route,
zero network calls) measured median 0.452s sequential versus 0.152s with three
workers, about 2.96×. The selected candidate and validation were unchanged. This
isolates scheduling and is not an observed production end-to-end improvement.

## October 16 update: easier planning and returning to a route

The planner now comes before the gallery example in the document and on compact
screens. Desktop grid areas retain the introduction and gallery alongside the
form. This keeps the functional form reachable on mobile while preserving the
real gallery example, its empty/error states and its attribution.

Three labelled shortcuts open the existing structured, map-placement and image
forms directly. They expand both disclosure levels, move keyboard focus to the
chosen form's summary and keep the written idea intact. They do not generate a
route. All original entry points and optional route settings remain available.

The shape catalog combines its existing text search with a category picker,
announces the matching count and offers a clear-filters action, including when
there are no matches. Clearing filters preserves the selected route idea.

The new **Your route** navigation item returns to the latest result within the
current page session. The result remains mounted in a hidden container while
visiting the gallery or changing the request, preserving candidate selection,
accepted-route decisions and unfinished map edits. Starting a new generation
still clears the previous result. Browser Back also restores the result view
when returning to its fragment. Returning to the result cancels any pending
request interpretation, so its eventual response cannot switch views again.
Leaving the result closes its poster, reel and worksheet dialogs, releasing
their focus trap and scroll lock even when navigation uses browser Back.

Review focuses the new step's heading; returning to a result focuses the result
region. Generation errors offer an **Edit route idea** action alongside retry.
On compact screens, text-entry controls use a 16px font and shortcut targets
are at least 44px tall.

The street-routing API contract, quality gates, explicit approval of routes
requiring review, editor download blocking, GPX/TCX content and publishing consent
are unchanged. Browser tests use mocked routing and gallery responses; these
checks do not establish availability of external routing services.

Verification for this update:

- Production build and all 13 unit tests passed.
- The full desktop/mobile Chromium regression run passed all 268 cases.
- After the final dialog cleanup, the complete 11-case usability suite passed
  on desktop Chromium, mobile Chromium, Firefox and WebKit: 44 checks. This
  includes browser Back with a dialog open, preserved pending edits, guarded
  downloads and keyboard focus after clearing filters.
- Planner screenshots were inspected at 1440, 390 and 320px, with no horizontal
  overflow. The filtered catalog, request review and mobile result were also
  captured and inspected.

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
in `docs/research/budapest-heart-route.md`. The entire map, including attribution,
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
