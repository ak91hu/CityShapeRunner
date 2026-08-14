# GPS-art algorithm audit — 2026-08

## Scope and conclusion

This audit follows one request from free text to exported route and reviews the
method at every transformation boundary: intent extraction, drawing strategy,
custom contour generation, normalisation, multi-stroke construction, smoothing,
city placement, network preflight, waypoint reduction, street routing,
post-routing simplification, similarity measurement, quality gates, candidate
ranking, and bounded refinement.

The existing architecture already follows the strongest recurring result in
GPS-art research: ordinary shortest-path routing is not a shape optimiser. A
drawing needs several transformed placements, several street-route candidates,
explicit shape-preservation measurements, and an editable result. That pattern
appears in [Waschk and Krüger's automatic GPS-art planning](https://doi.org/10.1007/s41095-019-0146-z)
and in [Powałka's shape-guided artistic route finder](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad).
The audit therefore keeps the multi-candidate pipeline and strengthens the
places where geometry could be damaged before or after the street search.

## Evidence reviewed

- [Waschk and Krüger (2019)](https://doi.org/10.1007/s41095-019-0146-z):
  shape-aware cost and road-graph search for automatic GPS art.
- [Powałka (TU Delft)](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad):
  template placement, multiple route candidates, evaluation, and interactive
  correction.
- [Li and Fu (2026)](https://doi.org/10.3390/ijgi15030098): invariant turning
  angles, adjacent-length relations, topology, approximate segment matching,
  and shape-preserving road-graphic retrieval.
- [Yuksel, Schaefer, and Keyser](https://cemyuksel.com/research/catmullrom_param/):
  centripetal Catmull–Rom is the only parameterisation in its family guaranteed
  not to form cusps or self-intersections inside individual curve segments.
- [Kronenfeld et al.](https://pubs.usgs.gov/publication/70210904): topology and
  self-intersection must be checked explicitly during line simplification.
- [Wang et al. (2026)](https://isprs-annals.copernicus.org/articles/X-4-W8-2025/569/2026/):
  cartographic simplification benefits from visual-fidelity constraints and
  retention of important right-angle structure.
- [DeepSVG](https://proceedings.neurips.cc/paper/2020/hash/bcf9d6bd14a2095866ce8c950b702341-Abstract.html),
  [IconShop](https://arxiv.org/abs/2304.14400), and
  [Chat2SVG](https://openaccess.thecvf.com/content/CVPR2025/html/Wu_Chat2SVG_Vector_Graphics_Generation_with_Large_Language_Models_and_Image_CVPR_2025_paper.html):
  text-guided vector generation works best as a semantic scaffold followed by
  constrained geometric processing, not as unchecked final geometry.
- [openrouteservice endpoint documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/):
  public Directions and Snap APIs provide graph evidence but not a GPS-art
  objective. ORS custom models remain experimental and self-hosted, according
  to the [official custom-model documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/custom-models).

The broader literature map, validity limits, and proposed human-recognition
benchmark remain in [GPS-art research](gps-art-research.md).

## Stage-by-stage audit

| Stage | Method in the application | Audit result |
|---|---|---|
| Intent | Deterministic catalog/text/custom parsing first; structured model inference only for unresolved cases | Retained. It reduces latency and preserves composite free-text modifiers. Hungarian city, activity, distance, and custom-object phrasing have executable regressions. |
| Planning | Local strategy and city constraints; free drawings commit to the custom-vector path | Retained. Another unconstrained model call would add latency without road evidence. |
| Catalog shapes | Hand-authored continuous contours plus full placement-invariant pair audit | Retained. Every registered pair is tested against accidental route duplication. |
| Free-text shapes | One schema-constrained semantic vector scaffold, local checks, one bounded repair, honest fallback | Strengthened. The prompt now assigns contour space to 3–6 identifying cues and forbids stock-symbol substitution. Generated contours are compared with the complete catalog before acceptance. |
| Normalisation | Unit-space centring and bounding-box scale | Improved. Centring now uses route-length-weighted segment centroids, so uneven point density around one detail cannot shift the whole placement. |
| Multiple strokes | Continuous transfer lines between authored strokes | Improved. Custom requests use exact dynamic programming over order and direction to minimise total artificial transfer. Inputs larger than the bounded custom schema keep a deterministic linear-memory heuristic. Designs whose connectors exceed 45% of authored length are repaired. |
| Curve smoothing | Interpolating Catmull–Rom plus whole-line simplicity check | Improved. Uniform parameterisation was replaced by centripetal knots; turns of at least 70° protect adjacent segments, and the global topology guard remains. |
| Placement | Distance-derived scale, rotation/offset search, city barriers, diverse shortlist | Retained. This is consistent with the transform-search evidence; later network measurements remain authoritative. |
| Preflight | Bounded Snap batches over 180 transforms, displacement/connectivity heuristics, diverse finalists | Retained with an explicit limitation: point snapping is coarse evidence, not proof that consecutive points are connected acceptably. Full Directions routing makes that decision. |
| Guide points | Metre-space curvature protection, largest-gap bisection, hard provider budget | Retained and topology-hardened. Simplification now requests topology preservation and refuses a newly crossed line. |
| Street routing | Activity-specific ORS Directions, shortest preference, unsimplified returned geometry, bounded radius retries | Retained. A public black-box Directions call cannot reproduce a paper's custom per-edge shape cost. |
| Routed-line simplification | Refinement-controlled tolerance on successful road geometry only | Improved. Tolerance is now applied in a local metre projection instead of longitude/latitude degrees, and simplification cannot introduce a crossing into a simple route. |
| Similarity | Shared metric frame; arc-length resampling; direction/start variants; discrete Fréchet, Hausdorff, coverage, tangent/turn, multiscale landmark, reversal, extent, and length-ratio terms | Retained. No single proximity metric is allowed to hide lost corners, doubled-back segments, collapse, or wrong proportions. This matches the invariant-relation findings without claiming to implement Li–Fu's graph-retrieval algorithm. |
| Validation | Independent selected-shape, road, overall, fidelity, coverage, landmark, reversal, distance, and closure gates | Retained. A weighted average cannot compensate for failure of an identity-critical condition. |
| Ranking/refinement | Passing routes first; connectivity recovery across the remaining diverse preflight shortlist; measured scale/rotation/offset updates; monotonic best-candidate retention; bounded attempts | Strengthened. A failed first Directions placement no longer promotes its straight-line guide; remaining road-ranked placements are tried before quality refinement. Every numeric update uses observed routed error, never an unbounded model loop. |
| Export/editor | Full connected selected route, explicit acceptance below target, manual waypoint correction | Strengthened. Human correction remains available for quality problems, but graph-connectivity failure is not user-waivable: generated and edited routes fail closed with HTTP 503 and no GPS export. |

## Public street-routing safety boundary

The application keeps `snapped=False` geometry internally so offline pipeline
tests and routing diagnostics remain deterministic. That internal preview is
not a product route. The public boundary enforces four rules:

1. unsnapped candidates are omitted from the route selector;
2. top-level GPX, TCX, and persisted file paths require `snapped=True`;
3. `/generate` returns HTTP 503 after the bounded placement shortlist is
   exhausted without a connected route;
4. `/edit-route` returns HTTP 503 before serialisation if edited control points
   cannot be connected.

This distinction preserves debuggability without turning a visually accurate
overlay across buildings, water, or inaccessible land into a downloadable GPS
track. Explicit acceptance remains available only for a connected route that
misses one or more non-connectivity quality targets.

## Free-text-specific safety and quality contract

A novel description can now succeed without being in the catalog, but it does
not bypass the same route constraints as a template. The accepted model result
must have finite bounded coordinates, enough extent and points, a routable
aspect ratio, simple strokes, manageable stroke transfers, and a contour that
is genuinely distinct from every stock route under translation, scale,
rotation, traversal reversal, and closed-loop start changes.

The schema and one-repair policy bound inference cost. Catalog contour
preparation is cached, successful generated shapes use a 128-entry hashed LRU,
and smoothing/normalisation remain local. Exact multi-stroke optimisation is
safe because the custom schema permits at most eight strokes; it deliberately
falls back to a deterministic heuristic for unexpectedly large text geometry.

These checks prove geometric suitability, not semantic truth. A valid outline
can still be a poor depiction of a rare noun. The application labels a provider
fallback honestly and keeps routed recognition gates and manual editing visible.

## Deliberately deferred methods

1. **A custom shape-aware road-graph solver.** This is the largest likely
   quality gain, but it requires a self-hosted routable graph and per-edge cost,
   legality, turn, and activity handling. The public ORS API does not expose the
   required GPS-art objective.
2. **Vision-language semantic verification.** This should be tested only after
   a labelled multilingual outline/final-route benchmark exists. Asking the
   same generator to approve itself is not independent evidence.
3. **Multiple generated scaffolds by default.** It could improve semantic hit
   rate but multiplies inference and routing cost. It should be enabled only if
   benchmark data shows semantic generation, rather than street distortion, is
   the dominant failure.
4. **User image/sketch tracing.** This needs a separate file-security, privacy,
   foreground extraction, vectorisation, and topology-repair design.

## Regression evidence

The targeted suite now verifies length-centred normalisation, globally optimal
bounded stroke order, finite/simple centripetal smoothing, protected right-angle
features, catalog-collision repair, long-transfer repair, prompt semantic cues,
latitude-invariant metre simplification, endpoint retention, and simple-route
topology. The existing full catalog uniqueness, route similarity, preflight,
routing, validation, refinement, provider, API, and export tests remain the
release gate.
