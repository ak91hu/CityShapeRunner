# AGENTS.md — the AI workflow

This documents the multi-agent system that turns a prompt into a GPX route.
Read this before editing agents, prompts, skills, or the orchestrator.

## Guiding principles
1. **Provider-agnostic.** Any agent that uses an LLM talks to `llm` via
   `try_complete`, never to a vendor SDK directly. Swapping OpenAI ↔ Anthropic
   ↔ Ollama is a config change. Measured geometry optimisation stays
   deterministic.
2. **Graceful degradation.** No API key? Agents must still produce *something*
   via a deterministic fallback so the pipeline is exercisable offline.
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
- **Fast path:** complete known-template/text requests use local keyword, city,
  sport, and distance rules without a network call.
- **LLM:** ambiguous or unsupported requests use JSON extraction with a strict
  schema + worked example. Fallback: the same deterministic rules
  ("heart"→heart, "bike/cycle"→bike, `<n>km`→distance).

### PlanningAgent
- **Input:** `Intent` + city geography (geocoded centre, bbox, coarse
  city-extent heading, natural-language map context).
- **Output:** `Plan` — `shape_strategy` (template/text/llm), `difficulty`,
  optional `rotation_hint_deg` / `scale_hint` / `placement_hints` / `notes`,
  `lat_offset_m` / `lon_offset_m`, and the resolved `center_lat`, `center_lon`,
  and `city_bbox`.
- **Fast path:** known templates, text, and suggestions use curated city
  context deterministically, including a documented street-grid rotation and
  conservative obstacle-avoidance offset. Supported Hungarian cities have
  distinct running and cycling suggestions; the bbox-derived city-extent
  heading is only a coarse fallback.
- **LLM:** unsupported free-form shapes use JSON per `prompts/plan.txt`, with
  the same known geography in the prompt.
- **Consumers:** ShapeAgent (strategy orders the tiers), PlacementAgent
  (resolved city geometry, rotation, scale_hint, and offsets).

### ShapeAgent
- **Input:** `Intent` + `Plan`.
- **Output:** `Shape` — sub-paths of (x, y) in unit space + `closed`.
- **Strategy:** the plan's `shape_strategy` reorders the three tiers
  (template / text / llm). Default (no plan): template → text → llm. The shape
  is normalised (centroid → origin, max side = 1.0). Text supports every A–Z
  letter and 0–9 digit, including short multi-character labels.

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
- **Logic:** deterministically generate up to 180 placements across a 3×3
  city-wide grid, six rotations, and three scales. Subsample each outline to
  up to 18 curvature-preserving guides and send every guide point in one ORS
  snapping request. Rank independent snaps
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
- **Provider:** OpenRouteService directions through the waypoints. No key →
  great-circle connector (`snapped=False`). Simplifies real road geometry by
  `simplify_tolerance` (never the straight-line fallback).

### ValidationAgent
- **Input:** `SnappedRoute` + `RouteDraft` (the placed drawing as reference).
- **Output:** `Validation` (score 0..1, per-metric, issues[]).
- **Metrics:** `shape_fidelity` (shared-frame Fréchet+Hausdorff, drawn vs
  snapped), `distance_fit`, `closure` (closed shapes). Threshold 0.72 gates
  the loop. Below the 0.70 fidelity floor, the score cap remains monotonic to
  preserve candidate ordering. See `skill-validation-metrics.md`.

### RefinementAgent
- **Input:** `Validation` + `RouteDraft`.
- **Output:** mutates `RouteDraft` (scale_factor, rotation_delta, offsets,
  simplify_tolerance).
- **Logic:** deterministic, measurement-driven candidate generation. It first
  consumes the remaining preflight-ranked placements. Once that shortlist is
  exhausted, it tests `target / actual`; because road distance is
  discontinuous, a lower-scoring full correction is followed by a damped
  square-root bracket. Candidate signatures prevent identical
  scale/rotation/offset drafts from being sent twice. It performs no LLM call
  because an LLM must not guess numeric route corrections. See
  `skill-refinement-heuristics.md`.

### ExportAgent
- **Input:** best `SnappedRoute`.
- **Output:** `Export` — in-memory GPX (+ TCX) for the selected candidate.
  Quality and road-matching failures are advisory warnings, not deletion
  conditions; manually review unmatched guides before use.
  Server-side files are written only when `EXPORT_DIR` is explicitly
  configured.

## Loops

### Placement preflight and refinement loop (orchestrator)
```
place → generate city-wide transforms → batch snap → rank → full-route best
snap → validate
while any export quality gate fails and iter < max:
    restore best → next preflight placement (then measured tweak) → snap → validate
    skip already-tested draft signatures
    rank the weakest normalised gate; discard regressions
```
The configured maximum is eight refinement passes after the first full route.
Preflight screens up to 180 placements but sends only seven diverse choices to
full Directions routing. Proxy results live in `state.preflight_candidates`;
every measured street route lives in `state.candidates`, including candidates
that score below the current best. Per-candidate parameters and metrics are
also appended to `state.history`.

### Provider fallback loop (llm factory)
On `LLMError`, rotate to the next provider in `fallback_order`; the chosen
provider is sticky for the rest of the run.

### Shape-generation fallback (ShapeAgent)
Tier order is set by the plan; each tier only runs if the previous yielded
nothing. The ultimate safety net is a star with `source="fallback"` and an
explicit state error; it is never relabelled as the unsupported requested
shape.

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
