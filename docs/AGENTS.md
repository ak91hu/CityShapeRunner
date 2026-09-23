# AGENTS.md — the AI workflow

This documents the multi-agent system that turns a prompt into a GPX route.
Read this before editing agents, prompts, skills, or the orchestrator.

## Guiding principles
1. **Provider-agnostic.** Any agent that uses an LLM talks to `llm` via
   `try_complete`, never to a vendor SDK directly. Swapping OpenAI ↔ Anthropic
   ↔ Ollama is a config change. Measured geometry optimisation stays
   deterministic.
2. **Graceful diagnosis, fail-closed export.** No API key? Agents still produce
   a typed deterministic preview so the pipeline is exercisable offline, but
   the public API must never expose a selectable route or GPX/TCX unless
   Directions returned connected street geometry.
3. **Structured data over prose.** Agents exchange typed `dataclass` objects
   through `WorkflowState` (see `state.py`), not free-form strings.
4. **Loops are explicit.** Planning, refinement, and fallback loops live in
   `orchestrator.py` / `llm/factory.py`, not hidden inside agents. Agents are
   stateless between runs and update only their documented `WorkflowState`
   fields.
5. **Docs are loaded, not just read.** `docs/skill-*.md` is injected into each
   agent's system prompt by `skills/loader.py`. Editing a skill changes agent
   behaviour at the next run — no code change needed.

## Skills system
Agent skill Markdown lives in the `docs/` folder. Files named `skill-*.md` are
auto-discovered and parsed (YAML frontmatter + body). Each declares which
agents it `applies_to` (by agent `name`, or `all`). At runtime
`BaseAgent.system_prompt` calls `skills.system_prompt_for(self.name)`, which
appends the relevant skill bodies to `prompts/system.txt`.

| Skill file | Applies to |
|---|---|
| `skill-prompt-engineering.md` | all |
| `skill-planning.md` | planning |
| `skill-shape-design.md` | shape, planning |
| `skill-route-placement.md` | placement, planning |
| `skill-snap-and-roads.md` | snap, refinement, planning |
| `skill-validation-metrics.md` | validation, refinement, planning |
| `skill-refinement-heuristics.md` | refinement |

To add a skill: drop a `docs/skill-*.md` with frontmatter
(`name`, `description`, `applies_to`, `tags`) — it is picked up automatically.

## The agents

### IntentAgent
- **Input:** raw user prompt.
- **Output:** `Intent` (shape, city, sport, distance_km, text, style).
- **Fast path:** complete known-template, text, and named custom requests use
  local shape, city, sport, and distance rules without a network call.
- **LLM:** ambiguous requests use JSON extraction with a strict schema. The
  deterministic parser preserves named custom drawings and composite modifiers,
  so their normal remote call is reserved for ShapeAgent geometry.

### PlanningAgent
- **Input:** `Intent` + city geography (geocoded centre, bbox, coarse
  city-extent heading, natural-language map context).
- **Output:** `Plan` — `shape_strategy` (template/text/llm), `difficulty`,
  optional `rotation_hint_deg` / `scale_hint` / `placement_hints` / `notes`,
  `lat_offset_m` / `lon_offset_m`, and the resolved `center_lat`, `center_lon`,
  and `city_bbox`.
- **Fast path:** known templates, text, and suggestions use curated city
  context deterministically, including a documented street-grid rotation and
  conservative obstacle-avoidance offset. Hungary's KSH top 50 settlements and
  136 regionally balanced European cities have local centres, bounded urban
  search areas, and geography profiles. Suggestions score all 145 templates by
  continuity, turns, directional order, aspect, complexity, city street traits,
  activity, and distance; three diverse continuous candidates proceed to live
  route measurement. The bbox-derived city-extent heading is only a coarse
  fallback.
- **LLM:** planning does not spend a separate model call for a named custom
  drawing; curated geography commits its placement prior deterministically.
- **Consumers:** ShapeAgent (strategy orders the tiers), PlacementAgent
  (resolved city geometry, rotation, scale_hint, and offsets).

### ShapeAgent
- **Input:** `Intent` + `Plan`.
- **Output:** `Shape` — sub-paths of (x, y) in unit space + `closed`.
- **Strategy:** the plan's `shape_strategy` reorders the three tiers
  (template / text / llm). Default (no plan): template → text → llm. The shape
  is selected from 145 deterministic templates or normalised (centroid → origin,
  max side = 1.0). Text supports every A–Z
  letter and 0–9 digit, including short multi-character labels.
- **Custom geometry:** a strict `ShapeSpec` contains an explicit 3–6 feature
  brief, followed by one to four route-native candidates as allowed by the
  configured cap. The zero-cost production profile requests one model candidate
  and adds a deterministic semantic scaffold locally. Compound requests use the
  earliest related catalog subject as a compact structure/proportion anchor.
  Output is checked for finite coordinates, usable extent,
  aspect ratio, self-intersection, excessive multi-stroke transfer, and
  placement-invariant catalog duplication. Valid candidates are ranked by cue
  coverage, rendered evidence when enabled, and local geometry rather than by
  the model's preferred index alone.
  A cubic-control loop receives one deterministic endpoint-linearisation check.
  A still-crossed single closed linear outline receives a bounded 2-opt edge
  untangling that retains its endpoints and complete feature-id set. Every
  corrected contour must pass the normal geometry, ShapeSpec and uniqueness
  checks; unsupported or still-crossed paths are rejected.
  Every valid candidate is rendered and reviewed cue by cue. A different
  provider is tried first; if none is available, one bounded temperature-zero
  call to the generator acts as a disclosed visual self-review. Its score may
  rank valid candidates and target the single repair, but metadata keeps
  `independent=false`. If no visual call succeeds, local geometry evidence is
  used without inventing a semantic score.
  Route-length-centred normalisation is insensitive to uneven control density;
  bounded multi-stroke requests receive globally minimal connector ordering.
  Centripetal, corner-protecting smoothing cannot introduce a crossing. Only
  successful model geometry is stored in the 128-entry versioned cache; callers
  receive fresh path lists.

### PlacementAgent
- **Input:** `Intent` + `Shape` + `Plan`.
- **Output:** `RouteDraft` — real [lat, lon] waypoints + scale/rotation/offset.
- **Logic:** reuse the city centre and bbox resolved by PlanningAgent; geocode
  only as a defensive fallback for an incomplete plan. Scale the stitched
  shape using sport- and shape-specific road-network overhead estimates; use
  8 km for a run or 20 km for a ride when the prompt omits distance. Use the plan's
  `rotation_hint_deg` or, as a coarse fallback, the bbox long axis; apply the
  plan's `scale_hint`; equirectangular-project. Offsets accumulate for
  refinement. No global geocoder cache is retained between pipelines.

### PreflightAgent
- **Input:** `Intent` + `Shape` + the initial `RouteDraft` + city bbox.
- **Output:** the highest-ranked `RouteDraft` and
  `WorkflowState.placement_candidates`, a bounded full-routing shortlist.
- **Logic:** share a 180-placement budget between a diverse city-wide coarse
  search and two measured neighbourhood refinements. Subsample each outline to
  up to 18 curvature-preserving guides, with at most three ORS Snap batches.
  A bounded local graph proxy can add directed connectivity and detour evidence.
  Rank independent snaps
  using coverage, snapped distance, distinct-point ratio, perceptual fidelity,
  characteristic-turn preservation, and route-length preservation. Retain
  every proxy result, then greedily balance quality and transform diversity
  when choosing the seven full-routing candidates.
- **Boundary:** nearest-edge snapping is only a cheap road-fit proxy; it does
  not establish connectivity or produce an exportable route. SnapAgent and
  ValidationAgent remain authoritative. With no public ORS key, preflight
  degrades to the deterministic initial placement.

### SnapAgent
- **Input:** `RouteDraft`.
- **Output:** `SnappedRoute` — road-following polyline + distance + `snapped`.
- **Provider:** optional bounded shape-aware OSM graph search proposes better
  guides; OpenRouteService Directions remains the final route authority. Failed
  graph proposals fall back to the original guide. Successful proposals expose
  one pending original-guide challenger, measured by the orchestrator; both
  street routes are validated and retained. Graph proposals can retain up to
  50 Directions guides; original drawing challengers retain the 24-guide
  default. Street-based detour repairs also use 50 guides. Pending budgets
  are consumed with their guides and cleared in independent candidate shells.
  Guide budgets have separate cache entries. No key →
  internal great-circle diagnostic (`snapped=False`). It is useful for tests
  and issue reporting only and is not an exportable route. Every Directions
  vertex is preserved: `simplify_tolerance` remains a legacy draft field but
  cannot alter street geometry. Non-LineString, zero-length and skipped-segment
  provider responses are rejected.
  Graph guide selection can use a common weakly connected component within
  the existing 150 m radius when nearby isolated paths crowd out alternatives.
  Directed edges and turn restrictions remain authoritative. The cheap
  preflight connectivity proxy keeps its closest-street selection.
  At a turn-restricted intermediate guide, search retains up to two arrivals
  with different legal exits. A cheap arrival leading only into a dead end
  therefore does not automatically eliminate another viable approach.
  Unrestricted guides retain their single-arrival behavior and search budgets
  remain unchanged.

### ValidationAgent
- **Input:** `SnappedRoute` + `RouteDraft` (the placed drawing as reference).
- **Output:** `Validation` (score 0..1, per-metric, issues[]).
- **Metrics:** `shape_fidelity` (shared-frame Fréchet/Hausdorff, coverage,
  tangent sequence, multiscale salient-curvature landmarks, unintended
  reversal events, length, and extent;
  drawn vs snapped), `distance_fit`, `closure` (closed shapes). Threshold 0.72
  gates the loop. Below the 0.70 fidelity floor, the score cap remains
  monotonic to preserve candidate ordering. See `skill-validation-metrics.md`.
- **Closed-loop alignment:** compare both travel directions and up to two
  cyclic phases per direction. Whole-contour phase matching disambiguates
  repeated visits to a crossing; it never reorders strokes or edits geometry.
- **Semantic cues:** authored feature geometry shares the drawing's transforms.
  Coverage and metre deviation are measured per feature; important cues have
  independent gates. Up to two refinement slots target lost cues. Final street
  image review is advisory and cached, never road-connectivity evidence.

### RefinementAgent
- **Input:** `Validation` + `RouteDraft`.
- **Output:** mutates `RouteDraft` (scale_factor, rotation_delta, offsets,
  simplify_tolerance).
- **Logic:** deterministic, measurement-driven candidate generation. It first
  consumes the remaining preflight-ranked placements, but reserves the last two
  configured iteration slots for measured correction while distance exceeds
  the 20% target tolerance.
  Untested placements remain queued; the total iteration budget does not grow.
  Once the shortlist is exhausted or distance correction is due, it tests
  `target / actual`; because road distance is
  discontinuous, a lower-scoring full correction is followed by a damped
  square-root bracket. Candidate signatures prevent identical
  scale/rotation/offset drafts from being sent twice. It performs no LLM call
  because an LLM must not guess numeric route corrections. See
  `skill-refinement-heuristics.md`.

### ExportAgent
- **Input:** best `SnappedRoute`.
- **Output:** `Export` — in-memory GPX (+ TCX) for the selected candidate.
  Unrouted diagnostics are blocked before serialisation, including offline
  runs. The API also filters every `snapped=False` candidate and removes its
  GPX/TCX/file paths. Passing all gates enables an immediate automatic-check
  download; below-target **road-routed** results require explicit user
  acceptance in the UI. Persistent server-side files are written only for
  road-routed routes that pass every gate and only when `EXPORT_DIR` is
  configured. `/edit-route` also fails before serialisation when Directions
  cannot connect the edited guide.

## Loops

### Placement preflight and refinement loop (orchestrator)
```
place → generate city-wide transforms → batch snap → rank → full-route best
snap → validate
if route is not connected:
    try each remaining preflight-ranked placement → snap → validate
    stop at the first connected street route; otherwise fail closed at the API
while any export quality gate fails and iter < max:
    restore best → next preflight placement (then measured tweak) → snap → validate
    skip already-tested draft signatures
    prefer recognizable in-tolerance drawings, then give fidelity twice the weakest-gate weight
screen up to 16 local transforms around the best routed placement
measure at most four shortlisted local candidates; retain the best
if a measured loser improves a failed shape cue: graph-screen eight nearby placements and measure one challenger
if excess reversals remain: measure one graph alternative penalizing reused edges
reroute at most two local guide omissions to improve weak contour sections
reroute at most two alternatives guided by the original contour section
if characteristic turns still fail: route at most three high-proxy, reference-guided local turn repairs directly through Directions
if turning or detour length still fails: graph-screen reconnect windows (and high-error turning windows when needed); measure bounded sequential challengers
if turn or graph repair changed the incumbent geometry: rerun one omission and one reference-guided reconnect candidate
```
Complete quality-gate passes always rank ahead of partial results. Requested
distance may differ by up to 20% (`distance_fit >= exp(-0.6)`); closed-loop
closure still uses `0.60`. The same
selection rule is used in the API. Displayed metrics and gates are unchanged.
Local polishing is controlled by `SHAPE_POLISH_CANDIDATES` (0–4), respects the
deadline, and adds at most one Snap batch beyond initial preflight. The normal
16-placement/four-route search is preserved. If one of those fully routed
losers improves a still-failing spatial, coverage, turning, landmark, length,
extent or reversal cue by at least 0.02, eight nearby rotation, translation and
scale transforms are screened locally and at most one extra challenger receives
Directions validation. Scale moves by 10%, 20% or 25% in the direction suggested
by that candidate's measured distance relative to the target. This
second screen makes no additional Snap request, requires usable distance and
closure, keeps the original drawing reference, and cannot displace the normal
four measurements. Each
successful graph route may receive one additional original-guide measurement.
After detour repair, contour reconnection screens bounded local guide omissions,
then sends at most two proposals through Directions with a 50-guide budget.
The omitted section's straight chord is only an optimistic search proxy; it
never supplies road evidence or export geometry. The original drawing stays
unchanged, every returned candidate is retained, and regressions roll back.
A second bounded pass can insert one or two original-contour guides in a weak
section. It respects forward/reverse traversal, avoids spending both proposals
on heavily overlapping windows, and adds at most two Directions measurements.
Both passes keep the incumbent's endpoints and use the same final quality gates.
If turning still fails after both passes, up to three high-proxy local turning
windows are sent directly to Directions with the original drawing unchanged.
This search bypasses the local graph because a graph proposal can return to the
same incumbent streets despite a better reference guide. Every result must be
connected and outrank the incumbent; a worse route rolls back. Fixed start
constraints and the shared deadline skip the attempt.
If turning or detour length still fails, the graph search screens reconnection
windows; when turning fails it additionally screens at most 18 local candidates
around six separated, equal-arc turning-error phases. Each phase candidate
keeps the incumbent outside one window and uses
three points from the unchanged reference contour as speculative graph guides.
Physical 300/335 m windows avoid dependence on provider vertex density. Their
reference points use nearest-coordinate matching where it gives valid forward
progress, then fall back to the selected direction and whole-contour cyclic
phase so nearby arms and crossings do not silently jump to a different stroke.
The incumbent street endpoints and all geometry outside the chosen window remain
fixed. One graph winner per round receives a 50-guide Directions measurement;
accepted repairs can trigger at most two recomputed follow-ups while turning or
detour length still fails. Each proposal must improve the weakest recognition
component while retaining at least 98% of fidelity, coverage, landmarks, extent,
and reversal quality. Rejection, success, or the shared deadline stops the
stage, and fixed start constraints skip it. The graph path is never export
evidence, and a worse routed result rolls back.
Because direct-turn and graph repairs can expose a new local detour after the
initial reconnect screens, a changed incumbent receives one last omission and
one last reference-guided reconnect candidate. If neither late repair changed
the contour inputs, these redundant Directions measurements are skipped. Both
use the same 50-guide Directions authority and quality ranking; no broad
window set is reopened.
Before the local repair passes, a failed reversal gate can trigger one additional graph
proposal with a cost for edges already used in earlier contour layers. Its
50-guide Directions route is measured against the same drawing and competes
under the existing quality ranking; a worse route is retained for comparison
but cannot replace the incumbent. This attempt respects graph enablement and
the deadline, and is skipped for an explicit start anchor or fixed start bearing.
The default graph cost remains unchanged for all ordinary candidates.
The configured maximum is eight main refinement passes after the first full route.
Preflight screens up to 180 placements but sends only seven diverse choices to
full Directions routing. Proxy results live in `state.preflight_candidates`;
every measured street route lives in `state.candidates`, including candidates
that score below the current best. Per-candidate parameters and metrics are
also appended to `state.history`. The road-recovery pass runs before suggestion
evaluation and quality refinement because geometry tweaks cannot make an
unrouted straight-line diagnostic safe.

### Provider fallback loop (llm factory)
On `LLMError`, rotate to the next provider in `fallback_order`; the chosen
provider is sticky for the rest of the run.

### Shape-generation fallback (ShapeAgent)
Tier order is set by the plan; each tier only runs if the previous yielded
nothing. The ultimate safety net is a vector rendering of the complete
ASCII-normalised requested phrase with `source="fallback"` and an explicit state
error. It must never reduce a described subject to its initial. If no usable
ASCII word can be derived, the star remains the final emergency geometry;
neither fallback is relabelled as the unsupported requested shape.

## State
`WorkflowState` (dataclass) is the single shared object threaded through the
graph. Every agent reads what it needs and writes its own slot. The
orchestrator owns the instance; agents are stateless.

## Extending
- **New agent:** `agents/foo_agent.py` subclassing `BaseAgent`, register in
  `graph.py`, add a prompt to `prompts/`, add a `docs/skill-*.md` if it has
  domain knowledge.
- **New provider:** implement `llm/base.py:LLMProvider`, add to the factory.
- **New shape template:** append to `tools/shape_library.py:SHAPES`.
- **New skill:** drop a `docs/skill-*.md` with frontmatter — auto-loaded.
