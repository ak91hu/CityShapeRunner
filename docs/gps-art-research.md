# GPS-art route-generation research basis

GPS art is not ordinary waypoint routing. A recognisable result must preserve
the drawing's spatial relationships while every traversed segment remains
connected on a legal activity-specific street graph. The implementation uses a
coarse-to-fine approximation of the methods below.

## Findings that drive the algorithm

Waschk and Krüger's automatic GPS-art route planner shows why simply sending
off-road drawing points to a normal router fails: distant waypoint snapping
creates large detours, and excessive waypoint density can create U-turns. Their
shape-guided shortest-path cost combines progress toward the segment endpoint,
path length, and accumulated edge distance from the intended drawing. The
current hosted ORS API does not expose that custom edge cost, so GPS Art Wizard
approximates it by screening transformations before Directions routing and by
measuring the returned polyline afterward.

Leon Powałka's TU Delft shape-guided route-finding work separates optimal template
placement from graph route search, generates multiple alternatives, and ranks
them by several criteria. It also demonstrates an interactive browser workflow
where users move, rotate, and scale a design and receive route feedback. This
directly motivates both the city-wide automatic search and the built-in manual
route editor.

Arkin et al.'s polygon comparison represents shape through its turning
function. Turning behaviour is invariant to translation and can be normalised
for scale/rotation, making characteristic corners and curves more meaningful
than average point distance alone. GPS Art Wizard therefore combines
shared-frame spatial similarity with characteristic-turn, coverage,
route-length, and extent preservation.

Recent road-network retrieval research models both the target and road network
as graphs and compares invariant spatial relations, including turning angles
and length ratios. The preflight proxy uses those two relations explicitly;
full validation then adds the geographic shared-frame checks needed to detect a
route that has the right abstract shape in the wrong place.

Alternative-route choice-set research identifies path overlap as a first-class
problem: a naïve top-k list may contain several nominally different but almost
identical paths. GPS Art Wizard applies the same principle in transform space.
After the best proxy, each shortlist choice balances road-fit score against
distance in placement, rotation, and scale. This improves geographic coverage
without increasing the seven Directions calls.

Newson and Krumm's HMM map-matching work shows that nearest-point distance
alone is insufficient: transition plausibility through the network matters,
especially for sparse or noisy observations. Pedestrian Fréchet map matching
similarly emphasises sequence and continuity. The hosted ORS API does not expose
those algorithms directly, so manually moved editor points are never exported
as if independent snaps proved connectivity. They are sent back through
activity-specific Directions routing and the entire returned curve is measured
again.

## Production funnel

1. Normalise a deterministic continuous outline and estimate its initial scale
   from the requested activity distance.
2. Project up to 180 variants over the municipality: a 3×3 city-wide placement
   grid, six orientations, and three scale brackets.
3. Subsample every outline to as many as 18 curvature-preserving guide points
   and batch all locations into one ORS snapping request.
4. Score every placement by coverage, collapse resistance, perceptual fidelity,
   turning relations, length relations, and snap distance; retain every proxy.
5. Select seven placements by combined quality and transform diversity and send
   them to full Directions routing.
6. Retain every returned street polyline. Rank them using recognisability,
   distance, closure, and road-routing evidence; thresholds produce warnings,
   not deletion.
7. Apply the same measured funnel to simpler city-aware templates while keeping
   the requested shape available.
8. Let the user choose any route, drag a bounded set of control points, and
   submit the edited guide for fresh Directions routing, validation, and
   GPX/TCX generation.

The snap preflight is deliberately non-authoritative: nearest road edges may
belong to disconnected components. Only Directions plus final validation can
identify a recommended candidate. Lower-scoring and unmatched guides remain
available with explicit review warnings.

## Primary sources

- N. Waschk and A. Krüger, [Automatic Route Planning for GPS
  Art](https://link.springer.com/article/10.1007/s41095-019-0146-z), 2019.
  An [open manuscript](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00072443/Waschk_et_al_Automatic_Route_Planning.pdf)
  is also available.
- L. P. Powałka,
  [Shape-guided artistic route finding](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad),
  2023.
- E. M. Arkin et al.,
  [An Efficiently Computable Metric for Comparing Polygonal
  Shapes](https://www.cs.cornell.edu/~dph/papers/ACHKM-TPAMI-91.pdf), 1991.
- [Invariant Spatial Relation-Based Road Network Graphics Retrieval for GPS
  Art](https://www.mdpi.com/2220-9964/15/3/98), 2026.
- N. Nassir et al.,
  [Choice Set Generation Algorithm Suitable for Measuring Route Choice
  Accessibility](https://journals.sagepub.com/doi/10.3141/2430-18), 2014.
- P. Newson and J. Krumm,
  [Hidden Markov Map Matching Through Noise and
  Sparseness](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/map-matching-ACM-GIS-camera-ready.pdf),
  2009.
- [An Improved Map-Matching Technique Based on the Fréchet Distance Approach
  for Pedestrian Navigation
  Services](https://pmc.ncbi.nlm.nih.gov/articles/PMC5087552/), 2016.
- openrouteservice,
  [Snapping endpoint](https://giscience.github.io/openrouteservice/api-reference/endpoints/snapping/)
  and [Directions request/response
  types](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/requests-and-return-types).
