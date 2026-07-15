# AI-Assisted Fast SVG-First GPX Art Shape Matching Algorithm

## Goal

Given a city map and a catalog of SVG shapes, find the shape that best fits the city's street network, place that shape onto the streets, create a legal followable GPS-art route, and export a downloadable GPX file.

The algorithm should return one of:

- a high-confidence SVG-faithful downloadable GPX route,
- a simplified but recognizable approximate route,
- or a clear `not_suitable` result when the city cannot support the shape.

Primary product priority:

```text
1. Find the best matching SVG shape for the selected city's streets.
2. Place the shape on the street graph with the highest routeable confidence.
3. Build the legal route.
4. Export a GPX file that the user can download and follow.
```

The main optimization principle is:

```text
Use the SVG as the source of truth.
Use the city graph as the legal routing surface.
Reject bad placements before expensive routing.
Use AI only to improve weak candidates; deterministic routing and scoring decide the final answer.
```

## Key design decisions

Do not treat the city or the SVG as an image. Treat both as vector geometry and routeable graph data.

```text
City graph:
  nodes = intersections, dead ends, trail junctions
  edges = walkable / bikeable / driveable street segments

SVG shape graph:
  nodes = endpoints, corners, branch points, high-curvature landmarks
  edges = ordered SVG strokes sampled as polylines
```

A valid GPS-art match is not just a visual overlay. It must be routeable on the real street graph and should preserve the most important SVG features: silhouette, stroke order, corners, branches, and distinctive curves.

AI should act as an assistant, not as the authority. It can suggest better shapes, simplifications, anchor choices, neighborhoods, search parameters, and repair strategies, but every accepted route must still pass deterministic geometry, routing, and GPX validation.

## Inputs

```text
city:
  street centerlines from OSM or another map source
  route mode: walking, cycling, driving
  city boundary or search bounding box

shapes:
  SVG catalog containing paths, polygons, letters, icons, or polylines
  optional shape tags such as simple, angular, curvy, dense, symmetric
  optional user-preferred shape

constraints:
  minimum confidence
  minimum confidence before GPX export
  allowed scale range
  allowed route length range
  maximum detour ratio
  maximum geometric error
  maximum runtime or candidate budget
  whether one-way streets matter
  whether simplification is allowed
  whether AI-assisted retry is allowed
  maximum AI retry rounds
```

## Output

```json
{
  "city": "Example City",
  "selected_shape": "heart.svg",
  "status": "matched",
  "confidence": 0.94,
  "route_length_m": 8240,
  "svg_coverage": 0.97,
  "mean_svg_error_m": 5.8,
  "max_svg_error_m": 18.4,
  "detour_ratio": 1.11,
  "detail_level": "medium",
  "transform": {
    "translation": [412300.5, 5260112.8],
    "rotation_degrees": 13.4,
    "scale": 1.02
  },
  "route": [
    "ordered list of street edge IDs or coordinates"
  ],
  "gpx": {
    "status": "ready",
    "filename": "example-city-heart.gpx",
    "download_url": "/downloads/example-city-heart.gpx",
    "track_points": 1532
  }
}
```

## Primary product flow

```text
city + SVG catalog
  -> rank shapes by city compatibility
  -> place the most promising shapes
  -> route the best placement
  -> if confidence is too low, run AI-assisted improvement
  -> validate route and GPX
  -> return downloadable GPX
```

The user-facing result should optimize for a successful GPX download. Internal matching, AI retries, simplification, and rejection logic exist to support that final outcome.

## Fast SVG-first pipeline

### 1. Build reusable city indexes once

Start from street centerlines, preferably OpenStreetMap data.

1. Project latitude/longitude into a local metric coordinate system.
2. Keep only edges allowed for the selected route mode.
3. Split streets at all intersections.
4. Snap near-duplicate nodes within a small tolerance.
5. Remove unusable isolated components unless disconnected routes are allowed.
6. Store each edge geometry, length, bearing, curvature, road type, access rules, and connected component ID.
7. Build spatial and topology indexes:

```text
edge R-tree:
  nearest-street and corridor queries

node feature index:
  degree, outgoing bearing angles, local edge lengths

bearing buckets:
  fast lookup of streets with compatible direction

component index:
  reject transforms that land on disconnected graph parts

route cache:
  shortest paths between frequently used candidate nodes

routing accelerator:
  A* with landmarks, contraction hierarchy, or multi-level Dijkstra
```

For prototypes, NetworkX is acceptable. For speed at city scale, use igraph, graph-tool, contraction hierarchies, or a custom A* with geometric landmarks.

### 2. Parse each SVG into a weighted shape graph

Each SVG must drive its own match. Do not reduce it immediately to a generic outline.

For each SVG path:

1. Flatten curves into polylines with adaptive sampling.
2. Preserve path order and whether the path is open or closed.
3. Detect important points:

```text
endpoints
sharp corners
branch/intersection points
high-curvature points
long nearly-straight strokes
symmetry or repeated motifs when detectable
```

4. Assign importance weights:

```text
high weight:
  endpoints, corners, branch points, distinctive curves

medium weight:
  long silhouette strokes

low weight:
  tiny decorative details that can be simplified
```

5. Build multiple detail levels:

```text
coarse:
  silhouette and main strokes only

medium:
  important corners and curves

fine:
  full sampled SVG geometry
```

Normalize all levels for every SVG in the catalog:

```text
center at origin
scale to unit size
preserve aspect ratio unless non-uniform scaling is explicitly allowed
store stroke order
store edge length ratios
store turn angles
store topology
store weighted SVG sample points
```

### 3. Estimate city suitability before matching

Before expensive matching, quickly decide which SVGs the city is most likely to support.

Useful city features:

```text
intersection density
street orientation entropy
average block size
largest connected component size
grid-like versus organic layout
available route length
dead-end ratio
park / trail density for walking mode
street curvature distribution
```

Compare those features to each SVG:

```text
angular SVG:
  needs compatible intersection angles and enough corners

curvy SVG:
  needs organic streets, trails, parks, or dense route alternatives

detailed SVG:
  needs high intersection density and short block lengths

large simple SVG:
  can work in sparse layouts at a larger scale
```

If the city is clearly unsuitable, reject early. This avoids wasting time trying to force a route that will never resemble the SVG.

For a catalog of shapes, keep a ranked shortlist:

```text
shape_city_fit_score =
  0.25 * street_density_fit +
  0.20 * orientation_fit +
  0.20 * curvature_fit +
  0.15 * route_length_fit +
  0.10 * topology_fit +
  0.10 * mode_fit
```

Only run the expensive placement pipeline for the top-ranked shapes unless the user explicitly selected one shape.

### 4. Generate candidate transforms from SVG anchors

Brute-force sliding the SVG over the city is too slow. Generate transforms from distinctive SVG anchors.

Good SVG anchors:

```text
two connected strokes with a distinctive angle
three-point corner patterns
longest stroke pair
high-curvature points
branch points
closed-shape extrema
```

Find compatible city anchors through the node feature index:

```text
intersection degree is compatible
angle between outgoing streets is similar
nearby edge length ratio is similar
local topology is compatible
bearing bucket is compatible
connected component is large enough
```

Each anchor match gives a candidate transform:

```text
T(point) = scale * rotation * point + translation
```

Use deterministic sampling before random sampling:

```text
1. Try top SVG anchors by importance.
2. Match against top city anchors by compatibility.
3. Generate scale candidates from route-length constraints.
4. Use low-discrepancy or RANSAC sampling only to fill the remaining budget.
```

Keep a strict candidate budget:

```text
coarse transforms:
  500 - 5000 cheap candidates

medium transforms:
  top 50 - 200 after corridor scoring

fine transforms:
  top 5 - 30 after beam-map-matching
```

### 5. Reject bad placements with corridor scoring

Before running shortest paths, score each transform using only spatial queries.

For a transformed SVG:

1. Build a narrow corridor around the SVG polyline.
2. Query the edge R-tree for streets inside the corridor.
3. Measure how much weighted SVG length has nearby street support.
4. Compare street bearings to SVG stroke bearings.
5. Check whether supported streets are in the same connected component.

Fast corridor score:

```text
corridor_score =
  0.40 * weighted_svg_coverage +
  0.25 * bearing_compatibility +
  0.15 * important_point_support +
  0.10 * component_consistency +
  0.10 * scale_feasibility
```

Reject immediately when:

```text
weighted_svg_coverage < coarse_min_coverage
important corners have no nearby intersections
supported edges belong to too many disconnected components
estimated route length is outside constraints
street bearings conflict with major SVG strokes
```

This step is the main speed win: most bad placements are discarded with R-tree queries instead of expensive routing.

### 6. Snap the SVG to streets with beam map matching

For the remaining candidates, use HMM-style map matching with a small beam.

For each weighted SVG sample point:

1. Query only nearby street edges from the R-tree.
2. Keep the top `k` candidates by distance and bearing.
3. Use dynamic programming to choose a continuous street sequence.
4. Prune to the best `beam_width` partial paths at each step.

Emission score:

```text
how close the street candidate is to the SVG point
how compatible the street bearing is with the SVG tangent
how important the SVG point is
```

Transition score:

```text
legal route distance between consecutive candidates
detour compared with SVG segment length
whether the route stays inside the SVG corridor
whether the route crosses unsupported connector streets
```

Use cached and accelerated routing for transitions:

```text
same edge or adjacent edge:
  constant-time transition

nearby nodes:
  A* with Euclidean heuristic

repeated node pairs:
  route cache lookup

far or obviously bad pairs:
  reject by lower-bound distance before routing
```

Recommended defaults:

```text
samples per SVG level:
  coarse 100 - 250
  medium 250 - 800
  fine 800 - 2500

candidates per sample:
  3 - 8

beam width:
  20 - 100
```

### 7. Construct the GPS-art route with shape-aware routing

After snapping, build one legal route that follows the SVG as closely as possible.

For each consecutive matched position:

```text
find shortest legal path on the city graph
respect one-way rules if route mode requires it
respect access restrictions
prefer streets inside the SVG corridor
penalize streets that move away from the SVG
```

Use a route cost that rewards SVG fidelity:

```text
edge_cost =
  physical_length
  + off_svg_corridor_penalty
  + bearing_mismatch_penalty
  + connector_penalty
  - svg_support_reward
```

Route ordering:

```text
single SVG path:
  follow SVG path order

closed SVG path:
  choose best start point and direction

multiple SVG paths:
  follow SVG document order by default
  optionally reorder independent strokes to minimize invisible connectors
```

For complex multi-stroke shapes, use a rural postman / prize-collecting route formulation:

```text
required edges:
  streets that strongly support high-weight SVG strokes

optional edges:
  streets that support low-weight details

connector edges:
  legal paths between required strokes, heavily penalized
```

### 8. Refine only the best candidates

Optimization is expensive, so refine after strong pruning.

Optimize:

```text
translation
rotation
scale
optional non-uniform scale if explicitly allowed
optional detail level
```

Use cheap-to-expensive refinement:

```text
1. Coordinate search over translation, rotation, scale.
2. Re-score with corridor scoring.
3. Re-run beam map matching only for promising moves.
4. Reconstruct the route only for final candidates.
```

Good methods:

```text
ICP-like weighted alignment for geometry
bounded Nelder-Mead or Powell search
CMA-ES only when candidate quality is high but alignment is unstable
```

Avoid optimizing against the simplified shape only. Always re-score the final route against the original SVG samples so the result stays based on the input SVG.

### 9. Score SVG fidelity and routeability separately

Use separate scores so the route does not win only because it is easy to follow.

```text
svg_geometry_score:
  directed distance from SVG samples to the route

reverse_geometry_score:
  directed distance from route samples back to the SVG

weighted_coverage_score:
  percentage of high-weight SVG length supported by streets

corner_score:
  important SVG corners align with real intersections or route turns

topology_score:
  endpoints, branches, closed loops, and stroke order are preserved

routeability_score:
  route can be legally and continuously followed

detour_score:
  route does not require excessive connector travel

simplicity_score:
  route is not full of tiny zigzags that were not in the SVG

uniqueness_score:
  best match is clearly better than alternatives
```

Recommended confidence formula:

```text
confidence =
  0.25 * svg_geometry_score +
  0.15 * reverse_geometry_score +
  0.20 * weighted_coverage_score +
  0.10 * corner_score +
  0.10 * topology_score +
  0.10 * routeability_score +
  0.05 * detour_score +
  0.05 * uniqueness_score
```

Example score definitions:

```text
svg_geometry_score = exp(-weighted_mean_svg_to_route_error_m / tolerance_m)

reverse_geometry_score = exp(-mean_route_to_svg_error_m / tolerance_m)

weighted_coverage_score = matched_weighted_svg_length / total_weighted_svg_length

corner_score = matched_important_svg_points / total_important_svg_points

routeability_score = legal_connected_route_length / required_route_length

detour_score = max(0, 1 - (detour_ratio - 1) / max_allowed_detour)

uniqueness_score = clamp(1 - second_best_confidence / best_confidence, 0, 1)
```

Suggested confidence bands:

```text
0.95 - 1.00:
  excellent, SVG should be recognizable

0.85 - 0.95:
  good, minor distortion

0.70 - 0.85:
  approximate, recognizable for simple or iconic SVGs

below 0.70:
  reject unless rough results are explicitly allowed
```

### 10. Use AI-assisted improvement when confidence is too low

If the best deterministic match is below the required confidence, use AI to search for a better match instead of immediately rejecting. AI is used to propose smarter next attempts; the geometry engine still verifies every result.

Trigger AI assistance when:

```text
best_confidence < constraints.min_confidence
or weighted_coverage_score is low
or high-weight SVG corners are unmatched
or connector_length / total_length is too high
or many candidate transforms fail for the same reason
```

AI receives only structured, non-secret matching diagnostics:

```json
{
  "city_features": {
    "intersection_density": "medium",
    "orientation_entropy": "high",
    "dominant_bearings": [0, 45, 90],
    "curvature": "organic",
    "largest_component_length_m": 185000
  },
  "shape_failures": [
    {
      "shape": "dragon.svg",
      "confidence": 0.58,
      "failure_reason": "too_many_unmatched_corners",
      "missing_features": ["tail spikes", "small wing corners"]
    }
  ],
  "candidate_metrics": {
    "best_neighborhoods": ["northwest", "river_trail_area"],
    "best_scales": [0.8, 1.1, 1.4],
    "bad_scales": [0.3, 2.5],
    "route_mode": "walking"
  }
}
```

AI can suggest:

```text
try a different SVG from the catalog that better matches city topology
prefer a specific neighborhood or connected component
increase or decrease scale within constraints
try a different rotation prior
simplify low-weight SVG details
decompose a complex SVG into routeable strokes
change the stroke order for independent paths
relax non-critical tolerances but keep hard routing gates
switch route mode if the user allowed it
```

AI must not:

```text
invent streets
ignore access restrictions
force a visually good but unroutable overlay
remove high-weight SVG features without reporting it
produce the final confidence score
produce the GPX without deterministic route validation
```

Recommended AI loop:

```text
1. Run deterministic matching for the top shape shortlist.
2. If confidence is high enough, export GPX immediately.
3. If confidence is too low, summarize failures into structured diagnostics.
4. Ask AI for a bounded set of retry actions.
5. Convert AI suggestions into concrete deterministic search parameters.
6. Re-run placement, snapping, routing, and scoring.
7. Repeat only up to max_ai_retry_rounds.
8. Export GPX only if hard gates pass; otherwise return not_suitable with AI-derived suggestions.
```

Use AI mainly for search strategy, not low-level routing. Good AI-backed components are:

```text
shape recommender:
  ranks SVGs that should fit the city's graph style

failure classifier:
  explains why the current best candidate failed

retry planner:
  proposes the next bounded parameter changes

SVG simplifier:
  marks low-importance details that may be dropped

neighborhood recommender:
  suggests city components or areas with better topology
```

### 11. Export a validated downloadable GPX

The final deliverable is a GPX file, not just a route preview.

After selecting the best match:

1. Convert the final ordered route geometry back to latitude/longitude.
2. Densify long street segments enough for smooth GPS following.
3. Remove duplicate consecutive points.
4. Preserve route order exactly as the user should travel it.
5. Add GPX metadata with city, selected SVG, confidence, route mode, and timestamp.
6. Validate the GPX XML schema and coordinate bounds.
7. Store the GPX and return a download URL.

GPX export format:

```xml
<gpx version="1.1" creator="gps-art-shape-matcher">
  <metadata>
    <name>Example City - heart.svg</name>
    <desc>Confidence 0.94, walking route, SVG-faithful GPS art</desc>
  </metadata>
  <trk>
    <name>heart.svg GPS art</name>
    <trkseg>
      <trkpt lat="47.497900" lon="19.040200" />
    </trkseg>
  </trk>
</gpx>
```

GPX acceptance gates:

```text
GPX has at least 2 valid track points
all coordinates are valid WGS84 latitude/longitude
track order matches the final legal route
track length matches scored route length within tolerance
no NaN, duplicate-only, or out-of-city coordinate sequences
download file is created only after route hard gates pass
```

### 12. Simplify only when needed

If the fine SVG cannot be matched, simplify gradually rather than abandoning the shape.

Allowed simplifications:

```text
remove tiny low-weight decorative strokes
smooth noisy path samples
merge very short consecutive segments
drop details below the street-block resolution
increase route scale within constraints
```

Forbidden simplifications unless explicitly allowed:

```text
changing the SVG aspect ratio
removing high-weight corners
breaking closed loops
reordering dependent strokes
matching only a visually similar but different silhouette
```

Return the selected detail level and which SVG features were dropped.

### 13. Fail honestly

Common failure reasons:

```text
city street graph too sparse
SVG too detailed for available streets
important SVG corners have no compatible intersections
route disconnected
one-way restrictions break the route
required scale exceeds allowed route length
too many connector paths
match works only by visual proximity, not routeability
```

Structured failure:

```json
{
  "best_candidate_shape": "dragon.svg",
  "status": "not_suitable",
  "confidence": 0.42,
  "reason": "City street graph is too sparse for the high-weight SVG corners",
  "suggestions": [
    "increase scale",
    "allow medium detail instead of fine detail",
    "try walking mode",
    "try a denser city area"
  ]
}
```

## Pseudocode

```python
def create_best_gps_art_gpx(city_data, svg_catalog, constraints, ai_assistant=None):
    city_graph = build_routeable_city_graph(city_data, constraints.route_mode)
    indexes = build_city_indexes(city_graph)
    router = build_accelerated_router(city_graph, constraints)

    parsed_shapes = [
        parse_svg_multilevel(svg)
        for svg in svg_catalog
    ]

    ranked_shapes = rank_shapes_for_city(
        city_graph=city_graph,
        indexes=indexes,
        parsed_shapes=parsed_shapes,
        constraints=constraints,
    )

    if not ranked_shapes:
        return reject_all("no SVG shape is suitable for this city")

    best_matches = []

    for attempt in range(constraints.max_ai_retry_rounds + 1):
        for parsed_shape in select_shapes_for_attempt(ranked_shapes, attempt, constraints):
            for svg_graph in parsed_shape.levels:  # coarse -> medium -> fine
                anchors = extract_weighted_svg_anchors(svg_graph)
                transforms = generate_anchor_transforms(
                    svg_graph=svg_graph,
                    svg_anchors=anchors,
                    city_indexes=indexes,
                    constraints=constraints,
                )

                coarse_candidates = []
                for transform in transforms:
                    corridor_score = score_svg_corridor_support(
                        svg_graph=svg_graph,
                        transform=transform,
                        indexes=indexes,
                        constraints=constraints,
                    )
                    if corridor_score >= constraints.min_corridor_score:
                        coarse_candidates.append((transform, corridor_score))

                medium_candidates = select_top_k(
                    coarse_candidates,
                    k=constraints.medium_candidate_limit,
                )

                snapped_candidates = []
                for transform, _ in medium_candidates:
                    snapped = beam_match_svg_to_streets(
                        svg_graph=svg_graph,
                        transform=transform,
                        city_graph=city_graph,
                        indexes=indexes,
                        router=router,
                        constraints=constraints,
                    )
                    if snapped.weighted_coverage >= constraints.min_weighted_coverage:
                        snapped_candidates.append((transform, snapped))

                final_candidates = select_top_k(
                    snapped_candidates,
                    k=constraints.final_candidate_limit,
                )

                for transform, snapped in final_candidates:
                    optimized = refine_transform_with_cached_scores(
                        svg_graph=svg_graph,
                        initial_transform=transform,
                        snapped=snapped,
                        city_graph=city_graph,
                        indexes=indexes,
                        router=router,
                        constraints=constraints,
                    )

                    route = construct_shape_aware_route(
                        svg_graph=svg_graph,
                        transform=optimized.transform,
                        snapped=optimized.snapped,
                        city_graph=city_graph,
                        router=router,
                        constraints=constraints,
                    )

                    if not route.is_connected:
                        continue

                    score = score_svg_route_match(
                        original_svg=parsed_shape.original_svg,
                        svg_graph=svg_graph,
                        transform=optimized.transform,
                        route=route,
                        constraints=constraints,
                    )

                    best_matches.append({
                        "shape": parsed_shape.original_svg.name,
                        "detail_level": svg_graph.detail_level,
                        "confidence": score.confidence,
                        "transform": optimized.transform,
                        "route": route,
                        "metrics": score.metrics,
                        "score": score,
                    })

                if good_enough_match_found(best_matches, constraints):
                    best = select_best_match(best_matches)
                    if passes_hard_gates(best["score"], best["route"], constraints):
                        gpx = export_validated_gpx(best, city_graph, constraints)
                        return build_download_result(best, gpx)

        best_so_far = select_best_match(best_matches) if best_matches else None
        if should_stop_without_ai(best_so_far, attempt, constraints):
            break

        if not constraints.ai_retry_enabled or ai_assistant is None:
            break

        diagnostics = build_matching_diagnostics(
            city_graph=city_graph,
            indexes=indexes,
            ranked_shapes=ranked_shapes,
            best_matches=best_matches,
            constraints=constraints,
        )

        ai_plan = ai_assistant.propose_retry_plan(
            diagnostics=diagnostics,
            allowed_actions=[
                "rerank_shapes",
                "change_neighborhood",
                "change_scale",
                "change_rotation_prior",
                "simplify_low_weight_svg_details",
                "decompose_independent_strokes",
                "adjust_candidate_budget",
            ],
        )

        ranked_shapes, constraints = apply_ai_retry_plan_safely(
            ai_plan=ai_plan,
            ranked_shapes=ranked_shapes,
            constraints=constraints,
        )

    if not best_matches:
        return build_rejection_result(
            reason="No routeable SVG shape could be placed on this city graph",
        )

    best = select_best_match(best_matches)
    if passes_hard_gates(best["score"], best["route"], constraints):
        gpx = export_validated_gpx(best, city_graph, constraints)
        return build_download_result(best, gpx)

    return build_rejection_result(
        reason="Best match stayed below confidence threshold after deterministic and AI-assisted retries",
        best_candidate=best,
        suggestions=build_user_suggestions(best, ranked_shapes),
    )
```

## Hard acceptance gates

Before accepting a route, enforce hard gates:

```text
weighted SVG coverage >= 0.90 for simple shapes
weighted SVG coverage >= 0.95 for detailed shapes
all high-weight endpoints are matched
at least 90% of high-weight corners are matched
mean SVG-to-route error <= 5-15 m depending on city density
max SVG-to-route error <= 25-50 m depending on target route size
route-to-SVG error must not indicate large unwanted loops
detour_ratio <= 1.25 unless rough art is allowed
route must be connected
route must obey selected travel mode
connector_length / total_length <= 0.10
GPX export must validate before a download URL is returned
```

These gates prevent false positives where a route is legal but no longer resembles the SVG.

## Performance rules

Use these rules to keep the algorithm fast:

```text
Never run shortest-path routing during broad candidate generation.
Use R-tree corridor scoring before HMM / beam matching.
Limit candidates per SVG sample to a small k.
Use beam search instead of full dynamic programming over all street candidates.
Cache shortest paths between candidate nodes.
Reject transitions by Euclidean lower bound before routing.
Route only the final candidate set.
Stop after the first detail level that meets high confidence.
Re-score final output against the original SVG, not only simplified geometry.
Call AI only after deterministic matching produces low confidence.
Limit AI to bounded retry actions and validate all AI suggestions deterministically.
Export GPX only for the final accepted route.
```

Expected complexity improvement:

```text
slow approach:
  every transform * every SVG sample * many street candidates * many routes

fast approach:
  anchor transforms
  -> R-tree corridor pruning
  -> beam map matching with small k
  -> cached routing only for survivors
  -> final route construction for top candidates
```

## Recommended implementation stack

```text
Map data:
  OpenStreetMap via OSMnx, Overpass, pyrosm, or planet extracts

SVG parsing:
  svgpathtools, shapely, custom adaptive curve flattening

Geometry:
  Shapely / GEOS

Graph routing:
  NetworkX for prototype
  igraph, graph-tool, or custom contraction hierarchy for speed

Spatial index:
  STRtree or R-tree

Optimization:
  scipy.optimize, bounded coordinate search, CMA-ES only for hard cases

Map matching:
  HMM-style candidate scoring with beam search and cached shortest paths

AI assistance:
  LLM or multimodal model for shape ranking, failure diagnosis, SVG simplification proposals, and bounded retry planning

GPX export:
  gpxpy, lxml, or a small schema-validated GPX writer
```

## Practical notes for GPS art

1. Walking mode usually gives the best results because it can use paths, parks, alleys, and pedestrian streets.
2. Driving mode needs one-way and turn restrictions, so it should be scored more strictly.
3. Closed SVG paths should allow any start point and either clockwise or counter-clockwise direction.
4. The route preview should show connector paths differently from shape-matching paths.
5. Confidence should be based on the final routed path against the original SVG.
6. If simplification was used, the UI should show which SVG details were dropped.
7. If multiple SVGs are available, the app should default to the best city-compatible shape, not the user's first listed shape.
8. AI-assisted retries should be invisible to the user unless the final result needs an explanation or a lower-detail SVG was chosen.
9. The primary user action after success should be downloading the GPX file.

## Final recommendation

The fastest reliable algorithm is:

```text
routeable city graph + reusable indexes
  -> weighted multi-level SVG catalog
  -> city/SVG suitability ranking
  -> SVG-anchor candidate transforms
  -> fast corridor support scoring
  -> beam map matching with cached routing
  -> shape-aware legal route construction
  -> SVG-fidelity and routeability scoring
  -> AI-assisted retry when confidence is too low
  -> validated GPX export
  -> honest rejection when no downloadable route is good enough
```

This is faster than exhaustive graph matching and more SVG-faithful than generic nearest-street snapping because the SVG controls candidate generation, scoring, simplification, AI retry planning, final acceptance, and GPX export.
