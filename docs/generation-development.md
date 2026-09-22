# GPS art generation development

> Historical development record: the distance-fit `0.60` references below
> describe the earlier policy. The current target-distance gate permits a
> 20% relative deviation (`distance_fit >= exp(-0.6) ≈ 0.549`) and weights
> shape fidelity more heavily when ranking incomplete routes.

This work implements the five directions requested after the September 2026
research review. Completion requires working pipeline integration and evidence,
not just standalone algorithms.

## Requirements and current evidence

| Requirement | Implementation / verification status |
| --- | --- |
| Adaptive placement within a bounded total budget | PreflightAgent; tests cover measured improvement, provider degradation, coarse diversity and user constraints. |
| Early network connectivity and detour evidence | Top proxy candidates receive bounded directed graph transition checks; unavailable evidence stays unknown. |
| Shape-aware street graph search | Ordered contour layers, displacement/direction/reversal costs, distance objective, activity/access and turn restrictions; bounded search and ORS fallback. Tests show selection of a longer street path closer to the contour. |
| Semantic feature spans through projection and final route | Feature segments share normalization and anchor transforms, then receive geometric measurements and targeted repair. Critical cues have separate quality gates. |
| Final routed image review using economical AI | One provider attempt for up to three finalists, cached by exact inputs, within the atomic shared AI budget. Results appear in route details. |
| End-to-end benchmark and comparisons | 200 cases, four ablation variants, incremental JSON reports, exact-route human labels, failure attribution, latency and actual API/AI attempt counts. |

## Research basis

- [Waschk and Krüger, 2019](https://link.springer.com/content/pdf/10.1007/s41095-019-0146-z.pdf): drawing-dependent graph costs.
- [Powałka, 2023](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad): placement, custom routing costs, candidate evaluation and interactive adjustment.
- [Li and Fu, 2026](https://www.mdpi.com/2220-9964/15/3/98): turning angles and length relations for graphic retrieval.
- [ORS custom models](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/custom-models): experimental, self-hosted support; not exposed on the public service.

## Adaptive search

`PREFLIGHT_ADAPTIVE=true` allocates approximately 55% of the existing placement
limit to a spatially and geometrically diverse coarse search, and divides the
remaining allowance between two measured neighbourhood refinements. Up to four
diverse seeds receive round-robin translation, rotation and scale perturbations.
Round two uses smaller steps. Every measured result remains in diagnostics and
the final shortlist keeps the best coarse result if fine search does not improve
it. A failed fine Snap batch retains earlier evidence without retrying the batch.
Manual search radius, fixed start bearing, anchored start and city bounds are
preserved. This uses at most three Snap batches instead of one, with the same
overall placement limit. `PREFLIGHT_ADAPTIVE=false` supports baseline comparisons.

## Shape-aware graph search

### Component-guided placement polishing (2026-09-17)

The four established full-route polishing measurements remain unchanged. When
a measured losing placement improves one of the incumbent's failed recognition
components by at least 0.02 while retaining usable distance and closure, the
pipeline explores eight nearby rotation/translation/scale combinations. Scale
moves by 10%, 20% or 25% in the direction suggested by the seed's measured
distance relative to the target. The frozen
street graph screens those placements; at most one graph winner is then sent
through Directions as a fifth local challenger. No second Snap batch is used.
The original drawing remains the reference, every Directions result is retained,
the existing quality rank decides acceptance, and failed or worse challengers
roll back. Graph unavailability or the shared deadline skips the extra attempt.

On the frozen Szeged 5 km circle, a complete paired run improved fidelity from
0.77185 to 0.81698, turning similarity from 0.58780 to 0.66560, and length
similarity from 0.61353 to 0.77108. Spatial similarity rose from 0.72410 to
0.77458 and the route-length ratio fell from 1.30824 to 1.15370. Distance was
4.5061 km (distance fit 0.74353). Only the turning gate still fails. The search
used 204 placement screens and 28 routed candidates versus 196 and 26 before;
it added no extra Snap batch and completed without recorded provider failures.
Artifact: `.tmp/current-circle-component-polish-v3.json`.

Preservation was checked on the frozen Szeged heart. An intermediate design
that halved the incumbent-centred placement budget regressed and was rejected.
Keeping all 16 established placements plus the separate component challenger
reproduced the previous winner exactly: fidelity 0.81405, turning 0.67810,
length 0.71323 and 4.4942 km. Artifact:
`.tmp/current-heart-component-polish-v3.json`. Opposite traversal, seven cyclic
start phases, individually turning-ranked repairs, and combined repair windows
did not beat this heart and were not integrated.

Four turning-focused reconnection candidates were also routed from the improved
circle. The strongest reached 0.8162 fidelity and 0.6652 turning versus the
0.8170/0.6656 incumbent, so none was integrated. Artifact:
`.tmp/circle-turning-targeted.json`. The implementation passed all 730 backend
tests, Ruff, and mypy over 67 modules. Tests verify usable component seed
selection, the unchanged four incumbent measurements, the single separate
challenger, the 16-placement Snap batch, rollback, and the shared deadline.

The same production check preserved the Szeged star result exactly at 0.75772
fidelity, 0.58027 turning and 0.67176 length. Its component challenger fell to
0.65477 and was rolled back. Routing the graph alternatives with the best
spatial, turning and length proxies reached at most 0.7156 fidelity, so the
single graph-fidelity choice was not hiding a better final route. Artifact:
`.tmp/current-star-component-polish.json` and
`.tmp/star-component-alternatives.json`.

With scale included inside the same eight-placement bound, the frozen circle's
graph selected a +25% placement. Directions returned a complete 5.701 km route
that passes every unchanged gate: fidelity 0.86567, spatial 0.81171, coverage
0.88117, turning 0.74714, length 0.76748, extent 0.96622, landmark and reversal
1.0, closure 1.0, and distance fit 0.65665. The completed run used 204 placement
screens and 24 routed candidates, recorded no provider failure, and needed no
later contour repair. Artifact: `.tmp/current-circle-component-polish-v4.json`.

Fresh post-scale runs reproduced the heart exactly at 0.81405 fidelity and the
star exactly at 0.75772; their scaled challengers lost and rolled back.
Artifacts: `.tmp/current-heart-component-polish-v4.json` and
`.tmp/current-star-component-polish-v2.json`. The exploratory scale and
sequential-repair measurements remain in
`.tmp/circle-component-scale-probe-large.json` and
`.tmp/circle-scale-sequential-repair.json`; they are not portable fixtures.

### Restricted guide arrival alternatives (2026-09-17)

A synthetic bicycle case demonstrated a remaining guide-boundary failure:
the cheapest arrival had a legal outgoing edge, but it entered a one-way dead
end; another incoming way allowed the next contour segment. The previous
single-arrival search returned no proposal. Restricted intermediate guides
now retain up to two arrivals with distinct sets of legal outgoing edges.
The search still uses its existing four-state beam, time and expansion limits,
and all turn restrictions remain enforced. This bounded search is not a
guarantee of finding every feasible alternative.

Applying two-arrival selection to every guide was rejected after paired
Directions measurements: the Szeged star regressed from 0.7269 to 0.7018,
the heart from 0.8014 to 0.8007, and the circle was unchanged. The integrated
version applies only where a turn restriction distinguishes legal exits;
on the saved star, heart and circle it produces exactly the same graph
coordinates as before. These checks establish a routing correctness fix and
preservation of those proposals, not a new final shape-score improvement.
Artifacts: `.tmp/arrival-diversity-probe.json` and
`.tmp/arrival-restricted-regression.json`.
Verification: the new regression failed before the fix; all 712 backend tests
passed afterward, as did Ruff and mypy (67 modules).

### Connected endpoint regression check (2026-09-16)

A saved Szeged star placement had two guides whose three nearest nodes all
belonged to isolated paths. Connected alternatives were available at 41 m and
115 m. The common-component filter restores a proposal within the original
search budget (7,790 expansions); Directions confirmed connected street
geometry, but its fidelity was only 0.49770. It therefore cannot replace the
better incumbent merely because graph search succeeded.

Paired full runs on the same frozen Szeged OSM snapshot exposed a separate
regression when the filter also changed preflight connectivity ranking:
fidelity fell from 0.72690 to 0.66030. That proxy change was reverted. Applying
the filter only to full graph search reproduced the original winner exactly:
0.72690 fidelity, 0.53868 turning, 0.44933 reversal, 0.61140 length and 4.889 km.
The endpoint bug is fixed; this case does not demonstrate a final shape gain,
and three quality gates still fail. Local experiment artifacts are
`.tmp/star-snapshot-before.json`, `.tmp/star-snapshot-after.json` (rejected
proxy variant), `.tmp/star-snapshot-route-only.json` and
`.tmp/star-isolated-proof.json`; they are not portable benchmark fixtures.

The full backend suite passed 699 tests before reverting the proxy variant;
the 38 graph, preflight and generation integration tests passed afterward.
Ruff and mypy passed. Regression tests cover isolated alternatives, unchanged
radius, one-way restrictions and empty guide input.

### Bounded reversal repair (2026-09-17)

The final pipeline can measure one extra graph challenger when the routed
winner fails the reversal gate. Traversing an undirected edge already used in
an earlier contour layer adds three times that edge's length to its search
cost. Default graph searches retain their existing costs. Directions remains
the authority, using up to 50 guides, and the unchanged quality ranking decides
whether the challenger replaces the incumbent. Both candidates remain in the
record. Explicit start anchors/bearings and expired deadlines skip this pass.

On the frozen Szeged star comparison, the full pipeline reproduced fidelity
0.72690 → 0.74589 and reversal similarity 0.44933 → 1.0. Turning stayed near
0.5388 and length similarity rose slightly to 0.61628; distance was 4.8669 km.
This is a tradeoff, not full compliance: spatial similarity fell from 0.72533
to 0.66915 and now fails its gate. All thresholds and the original drawing
were preserved. Artifact: `.tmp/star-snapshot-reversal-repair.json`.

Paired fixed-placement graph probes also covered the Szeged heart and circle.
The unconditional cost regressed the heart (0.8014 → 0.7966) and left the circle
unchanged (0.7831). Both had reversal similarity 1.0, so the integrated pass
does not run for them. Local star-tip shifts and release of neighbouring
street anchors did not yield an acceptable contour-preserving improvement;
those experiments were not integrated. Increasing contour costs alongside
reuse costs also did not improve the measured result.

Verification: 711 backend tests passed, Ruff passed and mypy checked 67 modules.
Tests cover the alternative graph path, unchanged reference, provider routing,
retention of losing candidates, rollback for failed/worse routes, deadline
checks, start constraints and skipping already-passing reversal scores.

The reversal attempt now runs immediately after placement polishing, before
detour and contour repair. With the identical star reference and 27 measured
candidates in both runs, this ordering lets the existing contour pass improve
the reversal-repaired geometry: fidelity 0.74589 → 0.75772, turning
0.53885 → 0.58027, length 0.61628 → 0.67176 and spatial
0.66915 → 0.67801. Reversal similarity remains 1.0. Distance falls from
4.8669 to 4.6465 km, but distance fit still passes (0.80888). Landmark similarity
also falls from 0.93390 to 0.89358. The three spatial/turning/length gates still
fail. The number and limits of repair attempts did not increase. Artifact:
`.tmp/star-reversal-first.json`; the initial direct routing attempt had a
transport error, but the selected drawing and preceding reversal-repair
incumbent match the comparison exactly.

The ordering change passed 85 targeted pipeline, repair, integration and
benchmark tests, plus Ruff and mypy. A three-case live extension on the same
OSM snapshot found Szeged's 10 km star at 0.80872 fidelity (turning 0.64568,
length 0.64030 still fail), and its 5 km triangle at 0.80710 (only turning,
0.63096, fails). These are current outcomes, not paired improvement claims.
The subsequent square run hit HTTP 429 rate limiting and is incomplete;
its selected route must not be treated as a fully evaluated search.
Artifact: `.tmp/shape-regression-sample.json`. A concurrent circle guide-density
probe also received HTTP 429 for every request; its unrouted fallback metrics
in `.tmp/circle-guide-density.json` are not street-quality evidence.

After the rate limit cleared, both circle density experiments completed with
connected Directions geometry: 4/6/8/12 evenly spaced contour controls, each
with two cyclic phases. Allowing the standard intermediate-point insertion
peaked at 0.7636 fidelity; strict 5/7/9/13 coordinate budgets peaked at 0.7559.
Neither beat the saved 0.78217 circle incumbent. These guide-density changes
were therefore not integrated. The unchanged original circle remained the
reference throughout. Valid artifacts: `.tmp/circle-guide-density-retry.json`
and `.tmp/circle-guide-density-tight.json`.

`SHAPE_GRAPH_ENABLED=true` enables a local graph proposal before Directions.
Guide endpoints are selected from a shared weakly connected component when
one is available inside the existing 150 m radius. This prevents several
nearby nodes on an isolated path from hiding a usable connected alternative.
The full search still checks directed edges and turn restrictions. This
filter does not change the cheap preflight proxy's closest-street ranking.
Each search layer advances to the next contour guide. Dijkstra states retain
incoming way and previous node across guide boundaries. Edge costs combine
distance, contour displacement, direction and unwanted reversal. A small beam
retains endpoint/length alternatives, then penalizes target-distance error.
Default limits are two seconds and 30,000 expanded states per proposal. An
unfinished search never returns an exportable partial path.

Online graphs use a quantized region no larger than 25 km diagonally. Large
cities use the drawing neighbourhood. The process cache retains at most six
entries and 100,000 nodes, with one-hour reuse and a 60-second failure cooldown.
`SHAPE_GRAPH_SNAPSHOT` can point to a trusted operator-supplied Overpass JSON
file containing an `elements` array. Its SHA-256 identifies the graph revision.

Node ids preserve bridge/tunnel topology. Explicit activity access, bicycle
one-way overrides, barriers, no/only turns and same-way U-turn restrictions are
handled. Conditional and via-way restrictions conservatively exclude affected
ways; ferry routes are not imported. These rules can omit usable roads. Final
activity access and jurisdiction-specific rules remain the Directions provider's
responsibility. The graph never sets `snapped=True`: Directions must return the
actual connected geometry. If it rejects graph guides, the original guides are
tried through the existing bounded client. Validation uses the original outline.

## Measured shape refinement (September 15)

Successful graph proposals now receive one original-guide challenger through
Directions. The orchestrator validates both against the unchanged drawing and
retains both measured candidates. Graph routing can no longer silently replace
a better direct route solely because its provider request succeeded.

Search and API ranking share `route_quality_rank`: complete gate passes win.
For incomplete routes, the primary rank combines the weakest normalised
required gate with fidelity constrained continuously by distance-fit/0.6 and
closure/0.6. This lets a targeted repair advance a blocking characteristic turn
without allowing a marginal bottleneck gain to erase a large amount of overall
silhouette quality. Once all gates pass, higher constrained fidelity takes
priority. This changes selection, not displayed metrics or thresholds.

`SHAPE_POLISH_CANDIDATES=4` adds a bounded final neighbourhood search around the
best fully routed placement. One Snap batch screens up to 16 small transforms;
at most four are routed, with incumbent rollback on regressions. It honors the
workflow deadline and existing anchor, bearing, manual radius and city bounds.
Zero disables it; it also stays disabled without adaptive preflight. This is
an additional budget beyond the 180 initial placement samples. Graph challengers
can add another Directions invocation for each successful graph proposal;
provider retries remain separately bounded by the existing client.

Live smoke results using unchanged fidelity metrics:

| 5 km running case | Before fidelity | Refined fidelity | Refined distance |
| --- | ---: | ---: | ---: |
| Budapest heart | 0.6787 | 0.7573 | 4.9904 km |
| Szeged heart | 0.7344 | 0.7848 | 4.8053 km |

Evidence: `.tmp/fidelity-before.json`, `.tmp/fidelity-polished.json` and a final
repeat with the final selection rule, `.tmp/fidelity-final-szeged.json` (0.7848,
4.8053 km, graph disabled). Live graph availability/revisions varied, so these
are smoke results, not a controlled benchmark. Both still fail turning and
length-similarity gates and need user review. Star and the attempted paired
comparison hit HTTP 429; those runs do not establish a before/after improvement.
The full 200-case benchmark and human recognition study remain outstanding.

### Targeted detour repair

After placement polishing, up to two new Directions measurements can test
removing short closed excursions. Only exact repeated coordinates delimit
excursions, bounded to 10–400 m and eight detected loops. Single removals and
cumulative removals are screened against the original drawing; significant
loss of coverage, landmarks or extent rejects the proposal. The edited polyline
is only a guide proposal: the router must supply all final street vertices.
The orchestrator keeps the incumbent on failure/regression and retains every
measured candidate. The workflow deadline also bounds this stage.

The Szeged heart smoke test improved from 0.7846 fidelity / 0.6289 length
similarity to approximately 0.7907 / 0.7057 after rerouting. Distance changed
from 4.8053 to 4.4771 km, within the unchanged distance-fit gate. The length
gate passed; tangent-direction similarity remained below target (about 0.597).
Single-guide removal and larger-scale/rotated probes did not resolve that
remaining defect. A full-circle replacement of the coarse candidate pool
regressed this case and was not retained. This work is not yet a complete
resolution of the shape-quality defects.

A subsequent repeat exhausted the provider quota (HTTP 403, `Quota exceeded`).
`.tmp/fidelity-detour-proof.json` is that incomplete repeat, not evidence for
the preceding 0.7907 result. Do not compare its selected incumbent as a complete
search. Further live probes are paused until routing quota is available.

Correction after checking the user's dashboard: the local `.env` still selected
the deprecated `api.openrouteservice.org` host. The same key returned HTTP 403
there but HTTP 200 at `api.heigit.org/openrouteservice`, with 1999 requests
remaining. The local override was migrated and a fresh application-client
request succeeded. The earlier quota blocker applied to the legacy host, not
the key's current HeiGIT allowance. The outstanding shape defect still requires
further measurements; these connectivity checks do not resolve it.

Offline graph regression checks also exposed a guide-boundary dead end: the
cheapest arrival at a waypoint could forbid every outgoing turn, yet it closed
the search layer and discarded a more expensive legal arrival. Such arrivals
are now skipped while other incoming-way states continue searching. Beam
deduplication also retains the previous node, which affects U-turn legality.
A synthetic one-way network reproduces the old failure and verifies the legal
alternative without weakening restrictions or changing score thresholds.
This does not establish that the live heart's remaining tangent defect is fixed.

An experiment with 250 m guide spacing was rolled back: on the live heart case
it reduced fidelity to 0.733 and introduced a length-gate failure. The current
400 m spacing remains because protected corners and the measured local search
performed better. The experiment is recorded to prevent repeating the same
regression.

### Street geometry is preserved end to end

Directions vertices now remain intact through SnapAgent, validation, generated
and edited API map responses, GPX and TCX. RouteMap disables Leaflet's display
simplification; the old 500-point street preview limit is removed. Large routes
therefore transfer more coordinates, in exchange for showing the actual routed
corners. Sampling remains limited to drawing guides and other non-route previews.

ExportAgent refuses unrouted diagnostics even for internal/offline callers.
The provider boundary rejects non-LineString and zero-length geometry, skipped
segments in returned query metadata, and warning code 3, defined as skipped
segments in the [ORS source](https://github.com/GIScience/openrouteservice/blob/main/ors-engine/src/main/java/org/heigit/ors/routing/RouteWarning.java).
Missing optional extras (warning 4) do not invalidate an otherwise routed line.

The initial live Szeged street-preservation check measured 0.7846
fidelity and 4.8053 km with all 145 provider vertices intact. The primary and all
candidate map lines exactly matched captured Directions geometries; GPX had
the same vertices with zero measured coordinate error. This slightly changes
the earlier 0.7848 result because validation now uses the full street polyline.
Desktop/mobile browser tests also preserve all 620 supplied map vertices.

## Semantic feature preservation

The shape compiler retains the geometry assigned to each `feature_id`.
Features share the whole shape's normalization, rotation, scale, translation
and anchor shift; multi-stroke connectors do not become semantic features.
Validation reports coverage, mean/worst metre deviation and a preservation
score. Importance-4/5 features have separate gates at 0.65. This remains an
engineering threshold, not a human-recognition probability.

Up to two existing refinement slots pin a lost feature's endpoints and most
deviated tip, with a small outward tip perturbation on the second attempt.
The reference outline stays unchanged. Final validation rejects regressions.
Shapes without authored semantic spans keep the existing geometric landmark
checks; no semantic labels are fabricated for catalog contours.

## AI costs

`AI_ROUTE_VERIFIER_ENABLED=true` reviews at most
`AI_ROUTE_VERIFIER_CANDIDATES=3` already-routed finalists in one provider attempt,
using 256-pixel monochrome images and at most 1,200 output tokens. It reuses the
provider adapters and `OPENCODE_API_KEY`. The configured OpenCode structured
model defaults to `gpt-5.4-mini`; availability is documented by
[OpenCode Zen](https://opencode.ai/docs/zen/).

Successful reviews have a 24-hour, 512-entry process cache; failures have a
60-second cooldown. Keys include exact geometry, subject, features, configured
models and prompt version. Concurrent identical reviews do not duplicate paid
calls. A finite shared `WORKFLOW_MAX_LLM_CALLS` limit reserves calls atomically
across workers; `-1` removes that quota for the free-model profile. Token usage
and actual endpoint attempts, including retries, are recorded without
credentials. Prices are not guessed from token counts.

AI reviews are advisory and uncalibrated. Same-provider reviews are marked
non-independent. A model opinion cannot override road evidence or geometry
gates. The UI shows visible resemblance and missing details for the selected
geometry. Editing a route creates fresh validation, without a stale review.
Review images undo the placement rotation to show the authored orientation;
the actual route coordinates remain unchanged.

Free-text outline review now follows the same honest provenance rule. It first
tries one provider other than the geometry generator. If none answers, a single
temperature-zero call to the generator reviews the rendered pixels as a critic.
That result can rank already geometry-valid candidates and target the bounded
repair, but is stored as `rendered-image-self-review` with
`independent=false`. If the call also fails, selection falls back to local
geometry without fabricating a semantic score. Deterministic tests cover both
independent and same-provider paths. A September 21 one-case live retry hit the
provider's `max_output_tokens` termination during structured generation and
degraded to the labelled text fallback; it is failure-containment evidence,
not a successful semantic-quality measurement.

The fallback also covers a reachable independent critic that returns malformed
or incomplete schema output. In that case the generator critic receives the
same rendered candidates once; only a successfully parsed different-provider
result is marked independent.

The September 21 diagnostic then exposed a sparse-index review bug: geometry
validation retained two candidates with original indices 0 and 2, while the
generic image-order text implied indices 0 and 1. The valid self-review was
rejected as referencing an unknown candidate. Review prompts now list every
exact image-position/candidate-index pair, with deterministic coverage for a
filtered middle candidate.

A subsequent live repair returned a second `move` inside one stroke. The
repair prompt now repeats the program's single-leading-`move` rule explicitly;
the deterministic compiler remains strict instead of guessing how a malformed
subpath should connect or close.

The next captured response isolated the remaining failure: one closed stroke
used valid commands and useful labelled endpoints, but ordered its perimeter
edges across one another. Once a candidate is reduced to a single closed
linear endpoint outline, the compiler can apply a bounded 2-opt untangling and
then reruns all geometry, ShapeSpec and catalog-uniqueness checks. It preserves the complete
authored cue-id set and never accepts a contour that remains non-simple. A live
September 21 benchmark subsequently produced three valid robot candidates,
zero fallback, and a `0.72` rendered semantic score. The single-provider critic
was correctly recorded as `rendered-image-self-review` and supplied concrete
walking-stance and arm-separation repair diagnostics.

That live failure also exposed an undersized structured-output budget. The
free-text stages no longer inherit the general 2K ceiling: spec, geometry,
repair and rendered review now have 6K/8K/6K/4K maxima respectively, while the
geometry prompt asks for only 12–36 meaningful commands per candidate. This
matches the largest four-candidate schema without encouraging street-invisible
detail. Tests assert each call receives the intended bound.
Only the 6K/8K geometry and repair calls receive a 45-second OpenCode transport
timeout; spec and review remain at 30 seconds. This addresses a measured
large-schema timeout without allowing every model stage to consume the longer
window.

The same live response showed that all three initial robot programs could have
looping cubic controls. Candidate parsing now retries only that failure mode by
replacing each cubic with a line to its existing endpoint, retaining command
order and `feature_id`. The corrected program is recompiled and passes the full
simple-path, aspect, stroke-transfer, uniqueness and ShapeSpec validation; if
its endpoint polygon still crosses, it is rejected normally. Repair prompts now
also receive the exact locally corrected program rather than stale pre-fix JSON.

The final semantic-quality pass adds bounded ShapeSpec scaffolds for the
benchmark's difficult object, animal, fantasy and compound families. Primary
silhouettes close independently while semantic secondary strokes stay open
unless explicitly closed. Ranking is cue-complete-first, visual review covers
every surviving candidate exactly once, and questioned typed scaffolds may be
rechecked alone to remove contact-sheet attribution errors. OpenCode structured
responses retry one timeout at 45 seconds and one token-limit truncation at up
to 16K without marking a reachable provider unavailable.

The September 22 release measurement reviewed all four previously unstable
cases and produced route-valid geometry with no fallback for all four. Coffee,
the Hungarian crowned dragon, and the phoenix passed the semantic gate; the
platypus retained all authored geometry cues but the same-provider visual score
varied below the gate in that run. This is recorded as reviewer variance rather
than hidden as a pass: deterministic geometry and feature tests remain the
release authority, while same-provider visual scores stay advisory.

## Benchmark

```powershell
.venv/Scripts/python.exe -m gps_art_wizzard.generation_benchmark --list --output .tmp/cases.json
.venv/Scripts/python.exe -m gps_art_wizzard.generation_benchmark --run baseline --limit 4 --output .tmp/baseline.json
.venv/Scripts/python.exe -m gps_art_wizzard.generation_benchmark --run full --limit 4 --output .tmp/full.json
.venv/Scripts/python.exe -m gps_art_wizzard.generation_benchmark --compare .tmp/baseline.json .tmp/full.json --output .tmp/comparison.json
```

`--run` uses configured live APIs; omitting `--limit` runs all 200 cases.
`--case-id` selects stable ids. Variants: `baseline` (fixed placement), `adaptive`
(adaptive placement), `graph` (also local graph), and `full` (also final AI
review). Existing shape generation, feature checks and export safeguards remain
in every variant: this is a search/review ablation, not a historical binary.

Reports retain exact route/reference geometry, selected shape, all validation
metrics, failure stage, runtime and endpoint usage. A substituted shape is not
counted as success for the requested shape. Directions cache is cold per case;
graph and AI process caches may be shared. Freeze both graph and ORS map data
for strict reproducibility. `--network-revision` is an operator assertion, not
proof that a live external router used that revision. Comparisons reject
different supplied revisions or different case parameters.

Run-scoped `workflow.routing_failures` records fixed endpoint/category counters
for HTTP service/request failures, transport errors and malformed responses.
It excludes provider bodies, URLs and credentials. Ordinary Directions
connectivity and nearby-road failures (the codes handled by bounded routing
retries) remain valid negative candidate measurements. A later successful
candidate does not erase an earlier missed measurement.

Each new record includes `search_complete` and `search_incomplete_reasons`.
Operational failures, absent telemetry, an unmeasured offline route, and an
execution exception mark a search incomplete. Route geometry and measured
scores remain available, and summaries separately count incomplete searches
and older records whose completeness is unknown. Their raw observed averages
are diagnostic outcomes, not evidence of a completed search. `--compare`
rejects incomplete or legacy-unverified records; rerun affected cases with
current telemetry before claiming paired quality improvements. This detects
interrupted measurements; it does not certify optimality or freeze live maps.

A fresh Szeged 5 km square run completed without recorded provider failures
after the earlier HTTP 429 interruption. It passed every quality gate:
fidelity 0.86065, turning 0.70489, length 0.85392 and reversal 1.0, at 4.3849 km
(distance fit 0.69138). The previous partial square search cannot support a
paired algorithm-gain claim. Artifact: `.tmp/square-complete-measurement.json`.
Verification: 728 backend tests passed, along with Ruff and mypy (67 modules).
HTTP limits/outages, transport errors, malformed responses, valid disconnected
candidates, credential-free telemetry, run isolation and comparison rejection
are covered by deterministic provider-boundary tests.

Human labels are a separate JSON array, applied with `--labels`:

```json
[{"case_id":"c0-heart-run-5","route_hash":"hash from report","recognized":true,"manual_edit_count":2}]
```

Labels apply only to that exact route hash. Unlabelled recognition and edit
counts remain null. Model scores never fill human labels. Calibration requires
blinded human recognition on held-out routes/cities before changing thresholds.

## Verification

### Measured distance correction cannot be starved by the shortlist

When a connected incumbent still has `distance_fit < 0.6`, the final two
configured refinement slots now test measured scale corrections even if
preflight placements remain queued. The existing full-ratio/damped-ratio logic
and iteration limit are unchanged. Earlier iterations and already usable
distances still use shortlist priority. This fixes the six-iteration/seven-item
configuration in which the distance heuristic could never run.

In the Szeged 5 km circle case, `.tmp/circle-reserved-distance-slots.json`
reached 5.1324 km (distance fit 0.92363) and fidelity 0.78217, compared with
3.6841 km (distance fit 0.45407) and fidelity 0.71002 in
`.tmp/shape-quality-diverse-check.json`. Turning improved from 0.56138 to
0.60504; length similarity decreased from 0.63566 to 0.61630. Those two shape
gates remain failed. Both runs measured 17 candidates; this is live, unfrozen
map evidence, not a claim that all drawing-quality requirements now pass.

The same broader check also found a Budapest 5 km heart that passed every
gate (fidelity 0.79261, turning 0.71522, length 0.70327), while the Szeged star
remained poor (fidelity 0.58291). Current improvements therefore have evidence
beyond the original heart placement, but do not establish general success.

### Local contour reconnection

After placement polishing and loop repair, the workflow can release one local
section of the incumbent's guide for fresh street routing. It samples at most
50 arc-length anchors, screens bounded 150–1200 m windows (scaled to route
length), fully scores only the best 16 proxies, and requests at most two diverse
Directions alternatives. Endpoint positions and the original reference are
preserved. Proxy chords are never treated as streets: only the provider's full
returned geometry is validated, retained as a candidate, and eligible for export.
Worse or disconnected results restore the incumbent. The workflow deadline is
checked before screening and before each provider measurement.

The Szeged 5 km heart live run in `.tmp/heart-local-reconnect.json` reached
0.80520 fidelity, 0.65516 turning, and 0.70743 length similarity on a 4.4985 km
street route, leaving only the turning gate below threshold. The preceding
run had 0.80355 fidelity, 0.64369 turning, and 0.69022 length similarity.
This is a physical route change, unlike the separate phase-scoring correction.
An additional omission-only pass did not consistently improve turning, so it
was not added to the production request budget. Wider-city gains remain unproven.

A subsequent reference-guided pass adds one or two original-contour points in
each proposed local window. It retains the rest of the street guide and chooses
at most two alternatives, excluding windows with at least 50% intersection over
union so both requests do not merely repeat the same repair. Reference matching
handles both traversal directions and open/closed drawings, and uses at most
513 reference samples. The existing omission pass still has its own two-request
limit. Both passes validate against the unchanged original drawing, keep every
returned candidate and reject failed or worse results. Their separate histories
are included in benchmark reports.

The full run `.tmp/heart-reference-reconnect-final.json` reached 0.81405
fidelity, 0.67810 turning similarity and 0.71323 length similarity on a
4.4942 km Directions route. Only the turning gate remains below threshold.
The selected reference-guided repair improved the geometry; no scoring weights
or gate thresholds changed. This single live case does not establish general
recognition quality or completion of the remaining turning-quality work.

A later frozen 10 km Szeged star showed why reconnect timing matters. Running
the existing omission operator once more after direct-turn and graph repair
raised fidelity from 0.81448 to 0.81600, turning from 0.68566 to 0.69680 and
length similarity from 0.65806 to 0.66323 on a connected 8.7667 km Directions
route (`.tmp/star10-final-reconnections.json`). The workflow therefore permits
one final omission and one final reference-guided candidate on the repaired
incumbent. This is a bounded 1+1 authoritative measurement, not a repeated
broad search; regressions still roll back and the unchanged turning/length
gates remain just below target in this case.

### Local graph repair after contour reconnection

When both direct reconnection passes leave the turning gate below target, the
pipeline reuses their bounded weak windows and adds phase-targeted windows for
local shape-aware street search. Equal-arc tangent errors are grouped into six
separated phases; three nearby windows per phase preserve their street endpoints
and use three unchanged original-contour points as speculative graph guides.
This contributes at most 18 candidates and no provider call by itself. The graph
may replace only one selected window; every guide outside it remains fixed.
Candidates must gain at least 0.00025 in the balanced sum of proxy fidelity
and the weakest recognition component while retaining at least 98% of
aggregate fidelity, coverage, landmark, extent, and reversal quality. When the
weakest component is already within 95% of its gate, selection switches from
the balanced sum to bottleneck-first ordering so a small fidelity gain cannot
divert a nearly passing route into a local dead end.
At most one winner per round is sent through Directions with the 50-guide
budget. An accepted repair may trigger up to two recomputed follow-ups while
the turning gate still fails; rejection, success, a stalled proxy, or the shared
deadline stops the search, so the stage uses at most three provider measurements. The pass is skipped
when the graph is disabled, the deadline has expired, the route
already passes turning, or the user fixed the start point/bearing. A disconnected
or lower-ranked routed candidate is retained for comparison and rolled back.

On the frozen Szeged 5 km heart, the current HeiGIT Directions run is complete
and uses three accepted local repairs. Compared with the two-repair incumbent,
fidelity rises from 0.81498 to 0.81695, turning from 0.68702 to 0.69040, spatial
similarity from 0.75711 to 0.75733, and length similarity from 0.70699 to
0.70787. The connected 4.5193 km route scores 0.83331 overall. A fourth offline
screen improves turning by only 0.00008, below the minimum progress rule, so it
does not spend another provider request. The unchanged 0.70 turning gate still
fails; this is measured physical-route progress, not a full pass. Artifact:
`.tmp/current-heart-contour-graph.json`.

The same bounded search produces a much larger improvement on the frozen
Szeged 5 km star. The complete live run raises overall score from 0.82067 to
0.86362, fidelity from 0.70576 to 0.74780, spatial similarity from 0.58792 to
0.67060, and turning similarity from 0.60089 to 0.61304. Distance fit improves
from 0.89316 to 0.96575 and the connected route is 4.9419 km. Length similarity
falls from 0.62850 to 0.60466, so spatial, turning, and length still remain below
the unchanged 0.70 gates. All three local graph winners were rerouted by
Directions and accepted by the same authoritative partial-route rank; none is
treated as street evidence from the graph proxy alone. Artifact:
`.tmp/current-star-contour-graph.json`.

The stopping probes are also recorded. Re-running the local operator on the
three-repair star yields no further proxy progress. Cyclically moving the heart
start produces no physical gain after restoring the original start before
measurement. Scaling the improved star contour to 1.30× yields promising
spatial/turning/length proxies (0.784/0.632/0.689), but requires repeated-edge
backtracking with reversal similarity 0.202; reuse penalties through 10 do not
remove it, so that branch is not sent to Directions. One heart run with a Snap
transport timeout is marked incomplete and excluded; the clean repeat above is
the comparison evidence.

Current verification after the adaptive proxy ordering and third bounded
repair: all 745 backend tests pass, Ruff reports no findings, mypy checks all
67 source modules, and the strict MkDocs build succeeds.

### Closed-loop scoring correction

Metric revision `closed-phase-v2` fixes ambiguous start alignment at crossings.
Previously an identical two-loop path with its start moved to the other visit
to the shared node scored only 0.63145 fidelity and 0.18879 turning similarity.
The corrected alignment gives 0.98989 and 0.98036; the small remaining gap is
arc-length sampling error. A control with three genuinely reordered loops
still scores only 0.56831 fidelity and 0.14900 turning similarity despite
identical outline coverage. Both directions retain their nearest-start option
and one whole-contour phase option; at most four full comparisons are needed.
Weights, thresholds, original reference and street geometry are unchanged.

On the unchanged saved Szeged heart, this scoring correction changes fidelity
from 0.80238 to 0.80355 and turning from 0.63908 to 0.64369. This is a scoring
correction, **not** an improvement of that route's physical shape. Length stays
0.69022; both failed gates remain. A full live run is saved separately in
`.tmp/heart-closed-phase-v2.json`. Benchmark reports include the metric revision
and reject comparisons against differently versioned scoring, including older
unversioned reports. GPS-drift simulation snapshots were updated to the new
metric values without changing tolerances or fragile/durable classifications.

### Preserving graph proposals through Directions

Graph proposals now use up to 50 request guides, while ideal drawings retain
the default 24. This preserves more of the road choices already found by the
graph. The requested budget participates in Directions caching; retries remain
bounded and returned street vertices are never simplified.

Detour repairs also retain this 50-guide budget. Previously they fell back to
24 despite being derived from an already routed street line. The pending budget
is consumed once and cannot leak into original-drawing challengers or independent
candidate clones. Rerouting the saved incumbent's repair with 50 guides produced
0.80238 fidelity, 0.63908 turning similarity and 0.69022 length similarity
(`.tmp/detour-50-probe.json`); the original reference stayed unchanged.
The production orchestrator reproduced these values on that saved incumbent
(`.tmp/repair-budget-production-proof.json`), retaining both measured candidates.
A full pipeline repeat reached the same 0.80238 fidelity
(`.tmp/heart-repair-guide-budget-retry.json`). The first full run suffered a
Snap preflight timeout and is not a paired comparison. Turning and length still
fail; the repair does not claim full quality compliance. The 342 routing,
integration and detour tests passed, as did Ruff and the CI mypy command.

A paired live Szeged heart probe on the same saved graph proposal improved
fidelity from 0.7802 (24 guides) to 0.8001 (50), and turning similarity from
0.5917 to 0.6365. The full pipeline also reached approximately 0.800 fidelity
(`.tmp/heart-graph-guides-50.json`). Turning and length gates still failed:
this is a measured partial improvement, not completion of shape-quality work.
These live measurements do not establish gains across other cities or shapes.

Further probes around the same saved placement did not justify production
search changes. Increasing nearest-node choices from 3 to 24 failed to improve
the graph proposal. Reducing their endpoint penalty improved length at the
expense of fidelity. Six additional relative rotations (120–270 degrees) were
measured through Directions; none exceeded the retained result and none passed
both turning and length gates. Raw evidence is in `.tmp/graph-neighbours-probe.json`,
`.tmp/graph-endpoint-probe.json`, and `.tmp/opposite-rotation-probe.json`. These
temporary local artifacts are exploratory evidence, not portable test fixtures.

Backend unit/integration tests cover measured adaptive gains, graph routing and
fallback boundaries, feature transforms/loss/repair, review validation/cache,
atomic AI budgets, and benchmark evidence handling. Frontend production build
and unit tests are also run. Live service and latest suite results are recorded
in the completion report; synthetic tests do not establish city-wide quality
improvements or human recognition rates.

### September 15 live smoke evidence

After network access became available, the OpenCode structured-image smoke test
succeeded using `gpt-5.4-mini`: 211 input tokens and 88 output tokens. A separate
review of an actual generated street route returned a valid low-recognition
judgement. The initial three-finalist batch hit the provider's 30-second timeout
and safely used fallback without a second provider attempt.

One paired live case (heart, Szeged, 5 km running) produced connected routes in
both variants. Distance error fell from 11.70% to 2.37%, while shape fidelity
fell from approximately 77.7% to 73.4%. Neither route passed every geometric
gate. Baseline runtime was 5.1 s; adaptive plus graph was 11.9 s; the run including
the timed-out AI request was 47.0 s. Graph diagnostics confirmed five successful
proposals among seven route attempts. This demonstrates integration and a
distance/shape tradeoff, not a general quality improvement. Live maps were not
frozen and there were no human labels.

A custom robot-with-umbrella request exercised the shared four-call AI budget:
three calls succeeded, one failed, and the run returned the labelled fallback
instead of inventing custom semantics. Recorded successful usage was 5,637 input
and 1,657 output tokens. This does not verify live custom-shape recognition;
feature compilation, transforms, detection and repair are covered by the
deterministic tests. Full 200-case live experiments and human calibration should
be run with an explicit operational API budget.

Verification: the full backend suite passed 634 tests, followed by passing
focused tests for subsequent review-orientation and benchmark diagnostics changes.
Ruff, mypy (66 modules), frontend production build, ten frontend unit tests and
strict MkDocs build passed. The repository's Playwright regression passed on
desktop and mobile, including clearing stale review/feature evidence on candidate
switch. The resulting mobile screenshot was visually inspected. The in-app
Browser was unavailable; no claim of testing through that browser is made.
