# Algorithmic background

Paceasso (GPS Art Wizzard) solves a constrained search problem: place a desired drawing in a city, find connected streets that follow it, and return a route whose outline and length remain useful. An ideal contour is a reference, never evidence that a person can travel along it. The connected geometry returned by OpenRouteService Directions is the route authority.

This page explains the implemented search and acceptance rules. The [backend pipeline](implementation/backend-pipeline.md) describes stage ownership, and the [data and quality guide](implementation/data-and-quality.md) describes the state model and metrics.

## 1. Turn an idea into a route-shaped contour

`IntentAgent` extracts a shape or text, city, activity, and optional target length. Recognised templates and text take a deterministic path. Ambiguous or custom ideas can use a configured model provider, but its output is checked before it becomes geometry. `ShapeAgent` chooses a template, a vector-font drawing, or a validated custom shape program. Custom outlines are checked for finite coordinates, usable extent, excessive self-intersection, feature coverage, and unwanted duplication of a catalog shape. A model's stated confidence cannot bypass these checks.

The selected shape consists of one or more ordered paths in unit coordinates. Normalisation removes its translation and scales its longest side to one. Connector ordering joins multiple strokes with a bounded transfer cost. This makes later rotation, scale, and location changes comparable without changing the shape's identity. The code lives in `gps_art_wizzard/agents/shape_agent.py` and `gps_art_wizzard/tools/shape_program.py`.

## 2. Place the contour in geographic space

`PlanningAgent` resolves a city centre and bounded search area. `PlacementAgent` uses an activity-specific estimate of road-network overhead to choose an initial scale for the requested distance. The ideal contour is rotated, scaled, and offset around that centre. Its coordinates are projected locally: northing is proportional to latitude difference, while easting also uses the cosine of the centre latitude. For a small urban search area, this provides metre-scale transformations without treating degrees of longitude as a constant physical distance.

The placed guide is a hypothesis. It can cross a building, water, or an inaccessible path. `RouteDraft` retains the target distance, rotation, scale, offset, and reference waypoints so every routed candidate can be scored against the drawing it actually attempted.

## 3. Search cheaply before requesting full routes

`PreflightAgent` screens a shared budget of up to 180 placements across a coarse city-wide search and two local neighbourhood refinements. Each candidate is reduced to at most 18 guides chosen to preserve important bends. Batched nearest-road snapping measures how much of the guide has nearby road coverage, how far points move, how many distinct points survive, and whether characteristic turns and approximate length survive. A bounded local street-graph proxy can provide additional connectivity and detour evidence.

These scores are **proxies**: independently snapped points need not connect in travel order. The algorithm keeps the proxy evidence, then chooses a diverse shortlist of up to seven placements for full Directions requests. Diversity matters because seven nearly identical translations would offer little chance of escaping a poor street pattern. With no routing credentials, the initial deterministic placement remains available for internal diagnosis, but it cannot become a downloadable route.

## 4. Route and repair on real streets

`SnapAgent` sends guide points to OpenRouteService Directions. Optional local OSM graph search can propose better guide sequences, while Directions still supplies the final connected polyline and length. The adapter rejects invalid, zero-length, skipped-segment, or disconnected provider results and preserves every returned route vertex. It distinguishes `snapped=True` street routes from internal `snapped=False` straight-line diagnostics.

The orchestrator first tries the top placement. If it is unroutable, it tries remaining shortlisted placements before refinement. Subsequent passes use measured distance and recognition errors to select untried transforms. For an overlong or short route, a correction can use the ratio `target_length / actual_length`; a damped square-root step follows when a full correction overshoots. Candidate signatures prevent repeating the same scale, rotation, and offset. Local contour, turn, and detour repairs have separate bounded candidate budgets and retain the original reference drawing. Every proposed repair must be routed and validated again; a local graph path or straight chord alone cannot replace a measured route.

## 5. Compare the routed line with the drawing

`ValidationAgent` expresses the ideal and routed coordinates in a shared metre frame, samples curves by path length, and calls `shape_similarity.similarity_diagnostics_between_routes`. The diagnostics combine ordered spatial matching (including Fréchet and Hausdorff evidence), outline coverage, tangent or turning sequence, salient corners and tips, route length and extent, and unintended reversal events. Closed contours are checked in both travel directions and a bounded number of cyclic phases; this changes the comparison's starting point, not the route geometry or stroke order. Authored semantic features can be checked separately when the shape includes them.

For a target distance `T` and actual distance `A`, the implemented distance fit is `exp(-3 × |A − T| / max(T, 1 km))`. Thus a 20% error at targets of at least 1 km corresponds to `exp(-0.6) ≈ 0.549`. A closed contour's endpoint gap `G` metres has closure score `exp(-G / 200)`. Open contours have no closure penalty. The aggregate score is `0.5 × fidelity + 0.3 × distance_fit + 0.2 × closure` for closed contours, or `0.6 × fidelity + 0.4 × distance_fit` for open contours. A route without street evidence is capped at 0.4, and a route below the fidelity floor receives a monotonic score cap. These formulas are in `gps_art_wizzard/agents/validation_agent.py`.

## 6. Apply independent gates and rank candidates

An aggregate score alone can hide a missing distinctive corner or a major detour. `gps_art_wizzard/quality.py` therefore checks connected street geometry, overall score, combined fidelity, ordered curve match, coverage, characteristic turns, landmarks, reversals, length, extent, distance fit, and closure independently where applicable. The configured overall threshold is 0.72 and the default shape-fidelity floor is 0.70. A closed route also needs closure score at least 0.60. The report includes pass/fail status and an explanation per gate.

Complete gate passes rank ahead of partial routes. Among partial routes, a recognisable drawing within distance tolerance ranks ahead of an over-tolerance one; fidelity and the weakest gate then guide comparison. All fully routed candidates remain available for comparison even if a quality target fails. Such a candidate requires user review in the interface before download. No `snapped=False` diagnostic is selectable or exportable. The API and export path independently recheck this boundary, including edited routes.

## Reproducibility and limits

The shape templates, coordinate transformations, geometry checks, scoring, and refinement rules are deterministic for fixed inputs. Geocoding, street data, Directions routing, weather, and optional model generation depend on external services and can change. Preflight scores predict promising placements; they do not certify traversability. Quality gates assess geometry and route-readiness signals, while live access, closures, traffic, and personal suitability still need a human check.

For the full request and response contract, see the [API reference](api-reference.md). For bounded-search tuning and benchmark commands, see [generation development](generation-development.md).
