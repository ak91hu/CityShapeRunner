# GPS-art theory and scientific basis

Research cutoff: **2026-08-10**.

This is a structured synthesis of the directly relevant, publicly discoverable
literature, not a claim that every page ever written about GPS art has been
enumerated. GPS art is a small research niche, so a defensible foundation has
to join its few domain-specific publications with established work in graph
routing, curve matching, shape perception, map matching, geodesy, GNSS error,
geographic-data quality, and human-centred evaluation.

### Review method and strength of evidence

The search used combinations of `GPS art`, `GPS drawing`, `artistic route`,
`road graphic retrieval`, `shape-guided route`, `curve-to-graph`, `Fréchet map
matching`, `sketch map matching`, `curvature shape recognition`, `GNSS urban
canyon`, and `route choice`. Backward citation searching was applied to the
direct GPS-art papers and forward searching to the foundational algorithms.
Priority was given to original papers, university repositories, standards,
and official service documentation. Product pages and informal examples can
show that a workflow exists, but they are not used as scientific validation.

Four evidence labels should be kept distinct throughout this document:

1. **Mathematical result:** a definition, theorem, complexity result, or proven
   guarantee under stated assumptions.
2. **Empirical result:** an observation supported by a described experiment or
   dataset; its generality is limited by the sample and protocol.
3. **Design inference:** a reasoned consequence of results from adjacent fields
   for GPS-art software.
4. **Engineering hypothesis:** a plausible choice that still requires GPS-art-
   specific calibration, ablation, or user testing.

The direct literature is too small and heterogeneous for a meaningful
meta-analysis. The review is therefore a critical narrative synthesis, not a
PRISMA-style claim of exhaustive systematic coverage. Where only an abstract
is public, the document says so and does not infer unreported methods or
results.

## 1. What GPS art is

GPS art (GPS drawing) is a physical traversal whose recorded geographic trace
is intended to be perceived as a drawing. It has three simultaneous realities:

1. **Graphic:** a target contour or collection of strokes with semantic
   identity, such as an arrow, heart, word, or animal.
2. **Geographic:** a walk on an activity-specific, directed road/path graph,
   including connectivity, access, barriers, bridges, and turn restrictions.
3. **Measured:** a noisy, sampled GNSS trajectory produced by a person and a
   receiver, not the exact mathematical route that was planned.

The artistic literature also treats the trace as a performed, embodied map,
not merely a static polyline. That distinction matters to product design: a
geometrically attractive route that is unsafe, inaccessible, or impossible to
follow is not successful GPS art.

## 2. Formal problem statement

Let the desired drawing be an ordered planar curve or stroke set

\[
S = (S_1, \ldots, S_k), \qquad S_i:[0,1]\rightarrow\mathbb{R}^2.
\]

Let an activity-specific road network be an embedded directed multigraph

\[
G_a=(V,E_a),
\]

where the available edges and their costs depend on activity `a` (walking,
road cycling, mountain biking, and so on). A placement is a similarity
transform

\[
T_\theta(x)=sR_\phi x+t
\]

with scale `s`, rotation `phi`, and translation `t`. The output is a connected
walk `P` in `G_a`. In the general case the system must search over both
placement and graph path:

\[
\min_{\theta,\;P\subseteq G_a}
\left(
d_F(T_\theta S,P),
d_H(T_\theta S,P),
d_L(T_\theta S,P),
e_D(P),
e_C(P),
c_a(P)
\right).
\]

The terms represent ordered curve error (Fréchet), outline coverage
(Hausdorff/robust bidirectional deviation), salient-landmark error, requested
distance error, closure error, and activity/safety cost. This is a
**multi-objective constrained optimisation problem**. A scalar weighted score
is useful for ranking, but it is not proof that all constraints pass. A weak
recognition dimension must therefore remain visible as its own gate.

For multi-stroke art, transfers between strokes are part of the physical walk
unless the recording is intentionally paused. They must be modelled explicitly;
silently joining strokes with a straight segment changes the drawing.

### 2.1 A road is geometry plus state, not just a line

Each directed edge `e` needs an embedding

\[
\gamma_e:[0,\ell_e]\rightarrow\mathbb{R}^2
\]

and an attribute/state vector `x_e`: activity permission, direction, surface,
grade, crossing type, traffic exposure, construction/closure state, and data
provenance. Feasibility can depend on departure time `tau`, user capability
`u`, and uncertain map state `omega`:

\[
A_e(a,\tau,u,\omega)\in\{0,1,\text{unknown}\}.
\]

The geometric trace of a graph walk `P=(e_1,...,e_m)` is the concatenation
`Gamma(P)=gamma_e1 oplus ... oplus gamma_em`; adjacency and direction are hard
constraints. Two visually identical polylines can therefore have different
feasibility or effort, and two geometrically intersecting roads may be
topologically disconnected because one is a bridge or tunnel.

### 2.2 Planned, executed, recorded, and displayed curves

GPS art has at least four non-equivalent curves:

- `T_theta S`: the placed ideal drawing;
- `Gamma(P)`: the route on the map graph;
- `Y=(Y_1,...,Y_n)`: the receiver observations during execution; and
- `M(Y)`: a platform's filtered or map-matched display.

A useful observation model is

\[
Y_i=\Gamma(P)(q_i)+b(z_i,\tau_i,d_i)+\varepsilon_i,
\]

where `q_i` is progress along the walk, `b` is an environment-, time-, and
device-dependent bias (notably NLOS bias), and `epsilon_i` is residual noise.
Neither term should automatically be assumed independent, identically
distributed, isotropic, or Gaussian. The scientifically relevant planning
objective is consequently not only `D(T_theta S,Gamma(P))`, but robustness of
the *recorded* result:

\[
\min_{\theta,P}\left(
\mathbb E[D(T_\theta S,Y)],
Q_{0.95}[D(T_\theta S,Y)],
e_D,e_C,c_a
\right),
\]

where the expectation and upper quantile are over plausible execution and
measurement conditions. This is a proposed robust formulation, not something
the current repository already solves.

### 2.3 Hard constraints and soft objectives

The following should normally be hard gates, not terms that a high aesthetic
score can cancel:

- every traversed edge is connected and permitted for the activity;
- mandatory start/finish, maximum distance/time, and closure requirements;
- no inaccessible transfer between strokes;
- any explicitly forbidden road, crossing, or area; and
- numeric validity of coordinates and route geometry.

Shape error, distance deviation, elevation/effort, number of turns, route
complexity, and preference attributes can be soft objectives. Safety should be
soft only where the input is genuinely a preference; a known prohibited or
physically impossible edge remains infeasible.

## 3. Direct GPS-art research

### 3.1 Balduz (2017): raster placement search

[Walk line drawing](https://www.cg.tuwien.ac.at/research/publications/2017/Balduz_01/)
rasterises both the target and street map and searches positions for a low
image-distance match. Its main contribution is recognising placement as a
separate search problem. Its limitation is equally important: pixel proximity
does not establish a connected, legal route on a graph.

### 3.2 Baloian, Biella, and Luther (2020): digital-geometry constructions

[GPS Drawing on Street Networks: Extracting Routes from Polygonal
Coverings](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00075701/Hajian_et_al_2020_Collaborative_Technologies.pdf)
connects GPS drawing to digital geometry and topology. It describes two
constructive families: approximate a rectifiable Jordan arc with paths selected
from the boundaries of a polygonal street covering, or encode a target polyline
with a grid chain code and transfer that directional sequence to street-network
crossing points. The contribution is theoretically useful because it makes the
“street network as drawing canvas” explicit and considers grid orientation,
regularity, and mesh size. The constructions assume suitable network/cell
structure and are not a comparative human-recognition or real-execution
benchmark.

### 3.3 Waschk and Krüger (2019): shape-guided graph cost

[Automatic route planning for GPS art generation](https://doi.org/10.1007/s41095-019-0146-z)
is the central route-generation paper. Its key observations are:

- ordinary fastest/shortest routers optimise the wrong objective;
- forcing too many off-network waypoints produces U-turns and detours;
- reaching every control point is less important than preserving the whole
  drawing;
- placement, scale, and rotation matter; and
- sparse rural graphs and fine detail impose unavoidable limits.

For each target segment from `S` to `E`, it uses a Dijkstra-like search with an
edge cost

\[
C(P,N,S,E)=\alpha C_1(N,E)+\beta C_2(P,N)+\gamma C_3(P,N,S,E),
\]

where `C1` rewards progress toward the segment endpoint, `C2` controls path
length, and `C3` is a Riemann-sum-style distance between a candidate road edge
and the intended segment. Reusing the previous segment's end node guarantees
continuity. The [open manuscript](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00072443/Waschk_et_al_Automatic_Route_Planning.pdf)
contains the formulas and failure illustrations.

### 3.4 Powałka (2023): placement, candidates, and interaction

[Shape-guided artistic route finding](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)
casts placement as image/template matching and route generation as graph search
with a target-aware cost. It separates:

- automatic initial placement;
- generation and multi-criterion evaluation of alternatives; and
- an interactive workflow where the user moves, rotates, and scales the design
  and receives rapid route feedback.

This supports a coarse-to-fine search and a human correction loop. It does not
justify treating nearest-edge snaps as connected routes.

### 3.5 Zhang et al. (2025): local-feature road-graphic retrieval

[Research on a road-graphic retrieval method for GPS art](https://dxkj.cbpt.cnki.net/portal/journal/portal/client/paper/a80384ddba058c588b4b7ad6ea9e233d)
describes a directly relevant retrieval pipeline: constrain a road-network
search with local shape features, build a candidate set, rank it with explicit
similarity measures, and return the best road graphic. The journal page makes
the bilingual abstract and references public, while directing readers to CNKI
for the full text; conclusions beyond that public abstract should therefore
not be inferred. It is an important bridge between template matching and the
more explicit invariant/topological formulation below.

### 3.6 Li and Fu (2026): invariant relations and graph retrieval

[Invariant Spatial Relation-Based Road Network Graphics Retrieval for GPS Art](https://doi.org/10.3390/ijgi15030098)
is the newest directly relevant paper found. It represents the input and road
network as graphs and matches:

- relative turning angles between adjacent directed segments;
- adjacent-segment length ratios, which are scale invariant;
- topological adjacency; and
- one-to-one or one-to-many input-segment/road-polyline correspondences.

It dynamically grows candidate road graphs and uses backtracking for individual
graphics, then a greedy combination stage for separated subgraphics. The
result is an enumeration/retrieval method rather than the same optimisation
problem as Waschk and Krüger. Its main implication here is that total route
length and average direction are insufficient: **local invariant relations and
topology must survive**.

More precisely, a target line segment may correspond to a single road edge or
to a road polyline that approximates that segment. This one-to-many mechanism
increases the retrievable scale and number of candidates. The paper reports
experiments on simulated and five real road networks, individual figures up to
approximately 8 km, and combined forms such as `520`, `1314`, `I♥y`, and
`LOVE`. Runtime depends strongly on the number and ordering of subgraphic
candidates: reported combined examples range from seconds to roughly 29
minutes. Its evaluation ranks turning- and length-relation consistency, but it
does not establish pedestrian/cycling feasibility, GNSS execution robustness,
or human semantic-recognition calibration. It also notes that a fixed input
geometry cannot retrieve every alternative drawing with the same meaning. The
authors link their [data and implementation](https://github.com/liganggis/run_drawing),
which enables direct reproduction and comparison rather than reconstruction
from prose alone.

### 3.7 What the direct evidence does—and does not—establish

| Work | Evidence supplied | Strongest warranted conclusion | Missing evidence |
|---|---|---|---|
| Balduz (2017) | Bachelor thesis and prototype | Raster/template placement is a useful search stage | Connected legal route guarantee and broad quantitative evaluation |
| Rosner et al. (2015) | CHI deployment with 16 people for about one week | Sketch-generated walking can be delightful, disorienting, and socially meaningful | Shape-fidelity algorithm validation and safety guarantee |
| Baloian–Biella–Luther (2020) | Open book chapter with digital-geometry constructions and examples | Polygonal coverings and chain codes are principled ways to transfer a curve's ordered directions to structured streets | Comparative benchmark, arbitrary irregular-network guarantee, human recognition, and physical execution |
| Waschk–Krüger (2019) | Algorithm, cost derivation, and qualitative examples | A target-dependent graph cost avoids characteristic waypoint-router failures | Published human study, calibrated weights, and benchmark statistics; the paper lists user evaluation as future work |
| Powałka (2023) | Geomatics master's thesis and interactive prototype | Placement, graph routing, candidate ranking, and user adjustment form a coherent end-to-end process | Peer-reviewed comparative benchmark and execution study |
| Zhang et al. (2025) | Public bilingual abstract | Local feature constraints plus candidate ranking are directly relevant | Public full method/results needed before stronger claims |
| Li–Fu (2026) | Open algorithm paper, simulated and five-region experiments | Turning angles, adjacent-length ratios, topology, and one-to-many segment matches materially expand road-graphic retrieval | Human recognition, route legality/safety, GNSS traversal, and comparison on a shared GPS-art benchmark |

This table exposes the central research gap: **no located publication provides
one benchmark joining semantic recognisability, connected activity-specific
routing, real traversal, receiver noise, and human evaluation**. Any production
quality percentage is therefore an operational score, not a scientifically
established probability that people will recognise the drawing.

## 4. Why ordinary waypoint routing fails

A conventional router solves an origin-to-destination problem. GPS art asks for
a graph walk that remains near an entire curve. These objectives diverge in
several predictable ways:

- **Independent snapping:** nearest road points may lie on disconnected graph
  components.
- **Off-grid anchors:** a router may accept a far-away road or make a large
  detour to visit an impossible point.
- **Waypoint overload:** dense anchors force repeated approaches and U-turns.
- **Waypoint under-sampling:** long unconstrained gaps allow the shortest path
  to erase lobes, corners, letters, or an arrowhead.
- **Grid ambiguity:** many Manhattan-shortest paths have the same length but
  very different visual shapes.
- **Barrier topology:** rivers, railways, motorways, private areas, and missing
  crossings turn a small Euclidean gap into a large network detour.

The correct abstraction is close to **curve-to-graph map matching in reverse**:
instead of inferring the graph path that produced noisy observations, find a
graph path that will produce a desired curve.

## 5. Curve and shape similarity

No single metric represents human recognisability. The production score should
combine complementary measurements in a shared coordinate frame.

### 5.1 Arc-length resampling

Road responses are often much denser than templates. Both curves must be
resampled by cumulative arc length before pointwise or order-aware comparison;
otherwise vertex density, not geometry, determines the score. Resampling must
retain closed-loop phase invariance and travel-direction invariance.

### 5.2 Fréchet distance: order and continuity

Fréchet distance minimises the maximum separation under monotone
reparameterisations of two curves. Unlike a point-set metric, it respects point
order and continuity. [Alt and Godau (1995)](https://doi.org/10.1142/S0218195995000064)
gave the classic continuous algorithm; [Eiter and Mannila (1994)](https://www.kr.tuwien.ac.at/staff/eiter/et-archive/files/cdtr9464.pdf)
defined the discrete dynamic-programming approximation used here.

Strength: detects reordered or backtracking paths. Limitation: a worst local
deviation can dominate, and the discrete computation is quadratic in sample
counts.

### 5.3 Hausdorff and bidirectional coverage

Symmetric Hausdorff distance asks whether every point set lies near the other.
It detects an omitted lobe or extra excursion but ignores traversal order and
is sensitive to a single outlier. A bidirectional RMS/trimmed deviation is a
useful robust companion. Neither can reject a scribble that repeatedly covers
the correct area.

### 5.4 Turning functions and invariant relations

[Arkin et al. (1991)](https://www.cs.cornell.edu/~dph/papers/ACHKM-TPAMI-91.pdf)
represent a polygon by cumulative tangent angle over normalised perimeter.
Translation disappears, scale is normalised by perimeter, and rotation becomes
an angular shift. Li and Fu's turning-angle and length-ratio constraints are a
graph-local version of the same principle.

For GPS art, retain both:

- tangent/turn sequence, to reject backtracking and wrong orientation changes;
- total and local length relations, to reject compressed shafts, stretched
  lobes, or detour-dominated segments.

### 5.5 Salient curvature landmarks

Uniform point weights are perceptually wrong. [Richards, Dawson, and Whittington
(1986)](https://doi.org/10.1364/JOSAA.3.001483) show that curvature extrema
carry significant contour-shape information. [Mokhtarian and Mackworth
(1992)](https://www.cs.ubc.ca/~mack/Publications/IEEE-PAMI92.pdf) develop a
multiscale curvature representation robust to noise and scale.
[Feldman and Singh (2005)](https://doi.org/10.1037/0033-295X.112.1.243)
formally connect contour information to curvature and report an asymmetry in
which concave boundary regions can be especially informative.

That is not a universal law that every concavity deserves a fixed bonus.
[De Winter and Wagemans (2008)](https://doi.org/10.3758/PP.70.1.50) collected
more than 200,000 marked points from 161 observers over 260 everyday-object
contours. Strong curvature extrema were usually salient, but turning angle and
the extent to which a part protrudes also contributed. Other controlled work
finds task- and stimulus-dependent convexity/concavity effects. Most recently,
[Schmidtmann et al. (2026)](https://doi.org/10.1016/j.visres.2026.108865)
reported that, under severe point reduction, high-information (`surprisal`)
locations could preserve matching better than curvature extrema alone. Thus
curvature is an evidence-backed feature detector, not a complete perceptual
model.

Engineering consequence: detect dominant turns at more than one chord scale,
match their sign, magnitude, order, and approximate arc-length phase, and give
them a separate diagnostic. This makes the heart notch, lower heart tip, arrow
tip, arrowhead/shaft junctions, animal ears, and star points explicit quality
features. Small street wiggles should be below an angular tolerance.

### 5.6 Shape context and correspondence

[Belongie, Malik, and Puzicha (2002)](https://doi.org/10.1109/34.993558)
describe each sampled boundary point by the distribution of other points around
it, solve point correspondences, align the shapes, and penalise deformation.
This is valuable future work when feature phase shifts become too large for
local arc-length matching, but it is more expensive and can over-accommodate a
deformation unless regularised.

### 5.7 Extent, closure, and topology

Width/height ratios catch global collapse that local distances may hide.
Closed targets require a geographic start/end closure gate. Topological
properties—stroke count, component count, junction degree, intended
self-intersections, and turn order—should be checked explicitly when the shape
requires them. Closure alone is not a universal proxy for recognition:
[Tversky, Geisler, and Perry (2004)](https://doi.org/10.1016/j.visres.2004.06.011)
show that good continuation and proximity can explain some apparent closure
effects, while [Garrigan (2012)](https://doi.org/10.1068/p7145) finds a closed-
contour advantage for learning novel shapes. The safe conclusion is to measure
closure, continuation, and landmark structure separately.

### 5.8 Distance metric, descriptor, score, and probability are different

A mathematical metric `d` must satisfy non-negativity, identity of
indiscernibles, symmetry, and the triangle inequality. Fréchet and Hausdorff
distances are metrics on appropriate equivalence classes of curves/sets. A
turn sequence, landmark list, cycle rank, or shape context is a **descriptor**.
The repository's weighted, transformed `shape_fidelity` is a **similarity
score**. It has useful invariances, but it is not proven to obey the metric
axioms. Nor is `0.80` an 80% probability of human recognition.

This distinction prevents three common scientific errors:

- calling any bounded score a distance metric;
- interpreting an arbitrary monotone transform as a calibrated probability;
- tuning a threshold on test examples and then reporting it as independent
  evidence.

If a recognition probability is desired, it must be estimated from held-out
human labels, for example with a calibrated logistic or ordinal model. The
features can include the geometric diagnostics, but calibration quality must
be reported separately.

### 5.9 Invariance is a quotient choice, not automatically desirable

Translation, rotation, scale, travel direction, and closed-loop start phase
can be factored out only when they are irrelevant to the question. A normalized
shape recognizer may compare curves modulo similarity transforms, but final
route validation must retain the selected geographic placement and physical
scale. Otherwise a correctly shaped route in the wrong neighbourhood—or a
ten-metre heart that GNSS noise destroys—could score perfectly.

Semantics may also break geometric invariance. Mirroring a heart is harmless;
mirroring text is not. Reversing traversal preserves the displayed outline but
can change legality, grade, crossing sequence, and navigation difficulty.
Therefore maintain two layers:

1. **intrinsic shape:** invariant descriptors for retrieval and template-class
   comparison;
2. **situated route:** shared-frame geometry, direction, activity constraints,
   physical scale, and uncertainty.

### 5.10 Curve simplification is an optimisation problem

A waypoint cap makes simplification unavoidable, but uniform decimation and
ordinary deviation control do not guarantee preservation of turn order,
topology, or the globally best curve match. Formal curve simplification seeks
a curve `S'` with few links subject to an error bound:

\[
\min |S'|\quad\text{such that}\quad D(S,S')\leq\delta.
\]

Local and global Hausdorff/Fréchet variants have different algorithms and
complexities. The systematic analysis by [van de Kerkhof et al.
(2019)](https://doi.org/10.4230/LIPIcs.ESA.2019.67) shows that some variants are
polynomial and others NP-hard; [Bringmann and Chaudhury
(2020)](https://doi.org/10.20382/jocg.v11i2a5) gives cubic bounds for important
local variants. Progressive multiscale simplification can maintain consistent
representations across display/routing scales ([Buchin et al.,
2020](https://doi.org/10.1016/j.comgeo.2020.101620)).

For GPS art, a valid shortcut must additionally preserve:

- required landmark extrema and their order;
- intended self-intersections and stroke junctions;
- closed-loop status;
- maximum local deviation in physical metres; and
- a minimum feature size relative to expected GNSS error.

This makes “keep every curvature extremum” a useful heuristic but not an
optimal simplification theorem. A research implementation should compare it
against a shortcut-graph solver under Fréchet plus landmark/topology
constraints.

### 5.11 A structural graph for line art

After snapping near-coincident crossings with a stated tolerance, convert a
target drawing into a stroke graph `H_S=(V_S,E_S)`. Vertices are endpoints,
junctions, self-intersections, and selected semantic landmarks; edges are the
ordered subcurves between them. Useful invariants include:

- component count `c`;
- vertex-degree multiset;
- cycle rank `mu=|E|-|V|+c`;
- ordered turn signs around each stroke;
- adjacency of semantic parts; and
- stroke multiplicity/retracing.

These coarse invariants can reject catastrophic mismatches that point
distances miss, but they cannot establish visual identity: many unrelated
drawings share the same degree sequence and cycle rank. Graph-edit or shock-
graph methods add graded structural correspondence ([Klein, Sebastian, and
Kimia, 2001](https://cs.brown.edu/people/pklein/publications/2001shapeMatching.pdf)),
at greater computational and modelling cost.

Sketch-map research provides a complementary lesson. Hand sketches can distort
metric geometry while retaining order, orientation, and topology; qualitative
relation graphs can therefore align sketches with metric maps
([SketchMapia](https://doi.org/10.1080/13875868.2014.917378), [Lu et al.,
2023](https://doi.org/10.3389/feart.2023.1081445)). GPS-art templates are not
ordinary cognitive sketch maps, but the evidence supports using qualitative
relations alongside—not instead of—metric curve error.

### 5.12 Recommended metric decomposition

| Dimension | Measurement family | Desired invariance | Known blind spot |
|---|---|---|---|
| Ordered geometry | continuous/discrete Fréchet | reparameterisation; optionally direction/start phase | dominated by a worst deviation; sampling approximation |
| Outline support | Hausdorff, RMS/quantile bidirectional distance | sampling density | ignores order; outlier sensitivity varies |
| Local direction | tangent/turning function | translation and scale | smooths over missing semantic parts |
| Salient structure | multiscale extrema plus information/protrusion | small road noise | feature detector is not a human recognition model |
| Proportions | adjacent and total length ratios, extent | translation/rotation/scale where appropriate | says little about connectivity |
| Topology | components, degree, cycles, junction correspondence | continuous deformation | extremely coarse without correspondence |
| Physical execution | metres, grade, crossings, access, uncertainty | none | depends on incomplete/current data |
| Human outcome | naming, forced choice, pairwise preference | experimental randomisation | costly and population/task dependent |

No row subsumes the others. The scientific role of the composite is ranking;
the scientific role of the components is diagnosis and falsification.

## 6. Placement and graph optimisation

### 6.1 Search space

At minimum, search translation, rotation, and scale. A city's bounding-box long
axis is only a weak orientation prior; neighbourhood street grids can differ
substantially from the city-wide axis. Search should be hierarchical:

1. broad, cheap placement screening;
2. diverse shortlist selection;
3. full graph routing;
4. high-resolution validation;
5. bounded local refinement from measured results.

### 6.2 Proxy versus proof

Batch nearest-edge snapping estimates road density and geometric compatibility.
It does **not** establish connectivity, access, or an exportable route. Only a
Directions/custom graph path over the activity profile can provide that
evidence, and even it is only as current and complete as its source map.

### 6.3 Multi-objective ranking

Recognisability, distance, closure, feasibility, and diversity conflict. A
weighted geometric mean prevents one excellent component from fully hiding a
catastrophic one, but hard or lexicographic gates are still necessary. Keep the
raw component vector and ideally expose a Pareto set rather than implying that
one scalar is physical truth.

### 6.4 Alternative diversity

Top-k by score commonly returns near-duplicates. Route-choice work treats path
overlap explicitly; [Nassir et al. (2014)](https://doi.org/10.3141/2430-18)
incorporate overlap penalties while generating choice sets. When graph-edge
overlap is unavailable during preflight, diversity in position, orientation,
and scale is a defensible proxy. After full routing, shared-edge or geometric
overlap should replace that proxy.

### 6.5 Hosted router versus custom graph search

The hosted openrouteservice Directions API provides activity profiles and
connected routes but not the target-dependent edge cost from the GPS-art
papers. Its public service also caps a Directions request at 50 waypoints;
the [official restrictions](https://openrouteservice.org/restrictions/) and
[routing documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/directions/routing-options)
must be treated as operational constraints.

The same restrictions allow 5,000 locations in one snap request. The production
preflight uses at most 180 placements with 18 guide points each (3,240
locations), so batching stays inside the documented limit while avoiding one
network round trip per placement. The snap endpoint returns results in input
order and may return `null` when no edge is found within the radius; candidate
slices and coverage scoring preserve both behaviours before any Directions
request. See the official
[snapping endpoint documentation](https://giscience.github.io/openrouteservice/api-reference/endpoints/snapping/).

As of 2026-04-28, openrouteservice deprecated
`api.openrouteservice.org` and announced its shutdown for 2026-08-24. The
application default now uses `api.heigit.org/openrouteservice`; the old base URL
is still identified as a hosted service during the transition so a missing key
cannot accidentally trigger anonymous traffic. This is an operational
migration, not an algorithm change. See the
[official announcement](https://ask.openrouteservice.org/t/deprecating-api-openrouteservice-org-in-favour-of-api-heigit-org/7912).

Therefore the current ORS funnel is a measured approximation, not an
implementation of Waschk–Krüger or Li–Fu. A research-grade next engine would
load the local activity graph and perform target-aware graph search directly.

### 6.6 GPS art as reverse map matching

Classical map matching asks which graph path best explains an observed curve.
GPS-art planning asks the same geometric question with the causal direction
reversed: which graph path should be travelled so that its embedding resembles
the target curve? For a fixed target placement this is the **curve-to-graph
matching** problem formalised by [Alt, Efrat, Rote, and Wenk
(2003)](https://doi.org/10.1016/S0196-6774%2803%2900085-3):

\[
 P^* = \arg\min_{P\in\mathcal W(G)} d_F(T,\Gamma(P)),
\]

where \(\mathcal W(G)\) is the set of walks in the embedded road graph. Their
continuous-Fréchet map-matching algorithm is polynomial for polygonal target
curves and planar embedded graphs. If the target has \(p\) segments and the
graph has \(q\) edges, the stated bound is \(O(pq\log q)\) time and \(O(pq)\)
space. Reuse of graph vertices and edges is permitted in that formulation.

The useful computational object is a product state, not the road graph alone:

\[
    z=(x,s),\qquad x\in G,\quad s\in[0,1],
\]

where \(x\) is position on a road edge and \(s\) is progress along the target.
Two visits to the same intersection can have different meanings because they
correspond to different target phases. Waschk–Krüger's target-relative edge
cost and Fréchet free-space search are different approximations to this same
coupling. An ordinary shortest-path cost \(c(e)\) cannot express it unless the
state is augmented with target position or target features.

### 6.7 Complexity boundaries must be stated per formulation

It is inaccurate to label all shape-guided routing either “easy” or “NP-hard.”
The boundary changes with the admissible-walk rules:

- fixed-placement continuous curve-to-graph Fréchet matching allows a
  polynomial algorithm in the Alt et al. model;
- [Wylie and Zhu (2014)](https://arxiv.org/abs/1409.2456) show NP-completeness
  for several *discrete intermittent* variants when uniqueness, path length,
  or the number of distinct graph vertices is bounded;
- translation, rotation, scale, stroke order, one-way access, time-dependent
  restrictions, and several coupled objectives enlarge the search space, but
  each addition needs its own reduction or algorithmic analysis; and
- [Gudmundsson et al. (2022)](https://arxiv.org/abs/2211.02951) give
  conditional lower bounds for exact Fréchet queries on arbitrary planar
  graphs, together with more positive approximate results for structured
  graph/curve classes.

This evidence supports hierarchical placement, pruning, and approximation. It
does not by itself prove that the repository's full application-specific
problem is NP-hard.

### 6.8 Multi-stroke drawings, transfers, and route-inspection analogies

A multi-stroke target has an execution semantics that must be declared. If GPS
recording remains on between strokes, the transfer path is visible “ink.” If
recording may be paused, the output is a set of curves rather than one curve;
the pause policy, positioning delay, and export format become part of the
experiment. A planner that silently inserts connectors changes the target.

For a *fixed* set of required undirected road edges, finding the shortest
closed walk covering them is related to route inspection. The Chinese postman
case in [Edmonds and Johnson
(1973)](https://doi.org/10.1007/BF01580113) is polynomial, whereas the rural
postman/general required-subset setting studied by [Lenstra and Rinnooy Kan
(1976)](https://doi.org/10.1002/net.3230060305) is computationally hard. GPS
art is not identical to either problem because the required edges are usually
unknown: the algorithm must first decide which roads best instantiate each
stroke. The analogy is nevertheless useful after stroke-to-road assignment,
when ordering, orientation, retracing, and connector length remain.

### 6.9 Pareto optimisation instead of a hidden universal score

For candidate vector

\[
 f(P)=(d_{shape},d_{topology},d_{length},r_{risk},t_{compute}),
\]

candidate \(P_1\) dominates \(P_2\) only if it is no worse in every component
and strictly better in at least one. Non-dominated candidates form the Pareto
set. A weighted sum can recover supported portions of a convex front, but can
miss non-convex regions; [Kim and de Weck
(2005)](https://doi.org/10.1007/s00158-004-0465-1) discuss this limitation and
an adaptive weighting method. Consequences for this product are:

1. make legality and explicit safety exclusions hard constraints;
2. use an epsilon constraint for user requirements such as maximum length;
3. retain the raw objective vector and score provenance;
4. return a small, diverse set spanning meaningful trade-offs; and
5. treat a scalar score as a UI ordering convention, not a natural constant.

### 6.10 A road network has a finite spatial vocabulary

No optimiser can recover a feature for which the local graph supplies no
compatible connection or direction. At target phase \(s\), let
\(\Theta_G(x,r)\) be the set of road-edge directions reachable within radius
\(r\) of placement point \(x\), and let \(\theta_T(s)\) be the target tangent.
A directional-support diagnostic is

\[
 d_\theta(s)=\min_{\phi\in\Theta_G(x(s),r)}
     \operatorname{angdiff}(\theta_T(s),\phi).
\]

Large unsupported intervals predict unavoidable distortion before an expensive
route search. Connectivity and turn legality must still be checked: nearby
edges with suitable bearings may belong to different components or prohibit
the required transition. A second physical limit comes from feature scale. A
notch or arrowhead much smaller than intersection spacing, minimum feasible
detour, or expected cross-track GNSS error cannot be faithfully instantiated.
These are feasibility diagnostics, not universal cut-offs; their thresholds
must be estimated for each graph, activity, and receiver environment.

## 7. Map matching and execution

Nearest geometry is not enough for either planned or recorded tracks.
[Brakatsoulas et al. (2005)](https://www.vldb.org/conf/2005/papers/p853-brakatsoulas.pdf)
evaluate trajectory-aware map matching, and [Newson and Krumm
(2009)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/map-matching-ACM-GIS-camera-ready.pdf)
combine observation likelihood and network transition likelihood in a Hidden
Markov Model. Fréchet-based pedestrian work likewise emphasises sequence and
continuity.

These results imply two different data products:

- **planned route:** graph geometry returned by the router;
- **executed trace:** noisy observations, optionally map-matched after the
  activity without overwriting the raw record.

The planner must never claim that independently moved or snapped control points
form a feasible route until they have been re-routed as a connected sequence.

### 7.1 A probabilistic map-matching model

Let observations be \(y_{1:n}\), candidate graph states \(x_{1:n}\), and time
increments \(\Delta t_i\). An HMM map matcher estimates

\[
 \hat x_{1:n}=\arg\max_{x_{1:n}}
 \left[p(x_1)p(y_1\mid x_1)
 \prod_{i=2}^{n}p(y_i\mid x_i)
 p(x_i\mid x_{i-1},\Delta t_i)\right].
\]

The emission term measures whether a reported position is plausible for a road
state. The transition term compares network travel with the elapsed time and
observed displacement. This joint sequence model can reject a geometrically
nearest but disconnected parallel road. A single Gaussian emission is often a
poor description in an urban canyon because NLOS errors are biased and
heavy-tailed; robust mixtures or environment-dependent parameters are more
defensible hypotheses to test.

### 7.2 Matching can improve the display while hiding execution error

Post-hoc snapping is valuable for analysing which roads were probably used,
but it conditions the result on the same road graph that generated the plan.
It can therefore make a noisy trace look artificially faithful. Evaluation
must retain four separately named layers:

1. target drawing \(T\);
2. planned road geometry \(R\);
3. raw timestamped receiver observations \(Y\); and
4. inferred map-matched path \(M(Y,G)\).

Report \(D(T,R)\), \(D(R,Y)\), and \(D(T,Y)\) in addition to any
\(D(T,M(Y,G))\). Never replace the GPX evidence with the inferred path.

### 7.3 Online guidance and offline inference are different tasks

An offline matcher can use the whole trajectory; live navigation only has the
prefix and must tolerate delayed or wrong state decisions. GPS art is unusually
sensitive to a missed turn because a small local execution error can remove a
semantic landmark. Guidance should therefore surface uncertainty before
high-information junctions and use a recovery policy that minimises resulting
shape damage, not only additional distance.

## 8. GNSS and geographic uncertainty

### 8.1 Service performance is not phone accuracy

The U.S. government's [GPS Standard Positioning Service Performance Standard,
5th edition](https://www.gps.gov/technical/ps/2020-SPS-performance-standard.pdf)
specifies space/control-segment service performance. End-user error additionally
depends on antenna, chipset, satellite geometry, atmosphere, device filtering,
and environment. Do not present the service standard as a guaranteed phone
trace accuracy.

### 8.2 Urban canyon effects

Buildings block line-of-sight signals and create reflected/non-line-of-sight
measurements. Smartphone studies report errors of tens of metres in difficult
urban settings; for example, [Weng et al. (2023)](https://doi.org/10.1016/j.measurement.2023.113766)
attribute most measured code outliers in their Hong Kong experiment to NLOS
signals and improve their test accuracy substantially with mitigation.

Practical consequences:

- features smaller than the expected trace noise may disappear;
- parallel streets close together can be confused;
- dense high-rise areas need a larger execution-error budget even if their
  street graph looks ideal;
- the UI should warn about planned-versus-recorded differences.

### 8.3 Sampling and filtering

Low sampling rates increase ambiguity between consecutive positions and can
erase tight turns. High rates can expose more receiver noise and inflate raw
polyline length. Store timestamps and reported accuracy when available; avoid
arbitrary smoothing before preserving the original GPX. Evaluate the final
record at multiple sampling/noise scenarios.

### 8.4 Projection and distance

Latitude/longitude are angular coordinates. City-scale optimisation may use a
local metric projection or a carefully bounded equirectangular approximation;
route distance and safety decisions should use geodesic/network distance.
Dateline, polar, and large-region cases require explicit handling. Numeric
similarity must use one shared metric frame so translating or shrinking the
routed result is not normalised away.

### 8.5 Error is biased, anisotropic, heteroscedastic, and correlated

The common simulation \(\epsilon_i\sim\mathcal N(0,\sigma^2I)\) is a useful
baseline but not an urban GNSS model. Street geometry and building facades can
make cross-street uncertainty larger than along-street uncertainty; satellite
visibility changes over the route; NLOS produces non-zero bias; receiver
filters make consecutive errors correlated. A more informative local model is

\[
 \epsilon_i=b_{z_i}+\rho\epsilon_{i-1}+L_{z_i}\eta_i+o_i,
 \qquad \eta_i\sim\mathcal N(0,I),
\]

where context \(z_i\) selects bias \(b\), covariance
\(L L^\mathsf T\), and outlier process \(o_i\). This is still a model to be
calibrated, not a claim that all devices follow one distribution. Weng et al.'s
urban experiment reported that 92.5% of detected pseudorange outliers were
associated with NLOS reception and reduced one test's positioning error from
about 15 m to 4.6 m after mitigation. Those numbers demonstrate mechanism and
possible gain; they are not transferable guarantees.

### 8.6 Feature-to-noise ratio

For target landmark \(k\), define a characteristic physical feature size
\(h_k\): for example notch depth, separation of heart lobes, arrowhead width,
or distance between adjacent junctions. Let \(\sigma_{\perp,k}\) be an
environment- and direction-specific robust cross-track scale. Then

\[
 \mathrm{FNR}_k=\frac{h_k}{\sigma_{\perp,k}}
\]

is a useful dimensionless diagnostic. Low FNR predicts fragile recorded
features, but there is no scientifically established universal pass value. It
depends on sampling, bias, topology, display scale, smoothing, and the human
task. The value should be calibrated against repeated tracks and recognition,
not chosen aesthetically.

### 8.7 Sampling theory: use the analogy carefully

A polyline with corners is not band-limited, so the Nyquist theorem does not
give a literal universal GPS sampling rate. It does give the correct warning:
sampling must resolve the shortest time/length scale whose geometry matters.
If \(\ell_{min}\) is the shortest along-route separation between important
turns and speed is \(v\), a first design check is to obtain several independent
samples over \(\ell_{min}/v\), then test the actual receiver/filter rather than
declare that check sufficient. Distance-triggered sampling can preserve
geometry more uniformly than a fixed time interval when speed varies, provided
the device exposes it reliably.

### 8.8 Robustness should be estimated as a distribution

For each planned route, simulate or replay \(B\) plausible executions:

1. sample route progress and variable speed;
2. generate context-dependent correlated bias/noise and missing fixes;
3. apply the same recording and display pipeline used by the product;
4. compute component errors and landmark survival for every replicate; and
5. report median, interval/quantile, worst-tail summaries, and probability of
   violating each predeclared condition.

Optimisation may then minimise a robust risk such as

\[
 \mathcal R(P)=E[D(T,Y_P)]+\lambda\,
 \operatorname{CVaR}_{0.95}(D(T,Y_P)),
\]

where CVaR focuses on the worst five-percent tail. The distribution must be
validated with physical repeats; otherwise it measures robustness to the
assumed simulator only.

## 9. Road-data quality and safety

OpenStreetMap is volunteered geographic information. A global road-completeness
study by [Barrington-Leigh and Millard-Ball (2017)](https://doi.org/10.1371/journal.pone.0180698)
estimated high worldwide completeness but also large geographic variation.
Completeness of geometry does not imply correct access, surface, crossing,
one-way, construction, or temporal restriction attributes. ISO
[19157-1:2023](https://www.iso.org/standard/78900.html) provides the general
geographic-data-quality framework; it does not define a universal acceptable
threshold for this application.

Accordingly:

- select the correct walking/cycling profile;
- retain router warnings and map-data timestamps where possible;
- check barriers, crossings, private access, surface, lighting, elevation,
  traffic exposure, and temporary closures;
- never equate `on_roads=True` with a current real-world safety guarantee; and
- require user review before export/following.

### 9.1 Data quality is multidimensional and use-specific

[Barron, Neis, and Zipf
(2014)](https://doi.org/10.1111/tgis.12073) organise intrinsic OSM assessment
around multiple indicators rather than one “quality” number. For GPS art the
relevant failure modes include positional error, missing roads, false or stale
roads, incorrect connectivity, missing attributes, inconsistent tagging, and
temporal mismatch. They affect different claims: positional error changes the
drawing, connectivity error breaks routing, and missing access data threatens
legality. A dense-looking map can fail all three.

ISO 19157 supplies a vocabulary and evaluation framework, not an endorsement
of a particular dataset. Every reported quality result therefore needs a
scope: area, date, feature class, activity profile, reference source, sampling
method, and decision threshold.

### 9.2 Route utility is not distance plus an undocumented “safety score”

Empirical route-choice work shows that travellers trade time/distance against
route attributes. [Broach, Dill, and Gliebe
(2012)](https://doi.org/10.1016/j.tra.2012.07.005) estimate bicycle route
choice using attributes including traffic stress and facility types, while
walking studies likewise find sensitivity to environment and context. Grade
also has a non-linear physiological cost; [Minetti et al.
(2002)](https://doi.org/10.1152/japplphysiol.01177.2001) measured walking
energy cost across gradients. These studies support including observable
attributes, but their coefficients should not be transplanted to a different
city, population, or activity as universal human preferences.

A transparent route utility may be written

\[
 C(P)=\beta_d d(P)+\beta_g g(P)+\beta_t t(P)+
      \beta_c c(P)+\beta_s s(P),
\]

where the terms could represent distance, grade burden, traffic exposure,
crossings, and surface burden. Unless coefficients are locally estimated, show
the components and allow constraints rather than labelling \(C\) a probability
of safety. Missing values require an **unknown** state, not a favourable zero.

### 9.3 Three safety layers

1. **machine-enforceable exclusions:** prohibited access, motorways, known
   closures, impassable surfaces, invalid direction;
2. **risk indicators:** traffic class, crossings, lighting tags, grade,
   isolation, surface, construction age/provenance; and
3. **human/current review:** weather, works, events, daylight, personal
   capability, neighbourhood conditions, and discrepancies visible on site.

This separation prevents probabilistic-looking UI language from exceeding the
available evidence. A route can be graph-feasible and still be inappropriate
or dangerous.

## 10. Reading the `expected1` and `expected2` references

The two supplied images encode both an algorithmic and a product requirement.

### `expected1.png`: heart plus arrow

The red dashed line is the ideal drawing and the thick blue line is the
street-constrained result. Recognisability depends on preserving distinct
structural parts:

- both heart lobes;
- the concave centre notch;
- the lower heart tip;
- the arrow shaft as a separate elongated relation; and
- a pointed, directionally unambiguous arrowhead.

Average point proximity can remain acceptable after one of those features has
been destroyed. This image specifically motivates landmark and topology-aware
evaluation.

### `expected2.png`: arrow

The key invariants are shaft continuity, head direction, head width, and the
two head/shaft junctions. Minor street zigzags are less important. This is a
multiscale requirement: low-frequency topology and dominant corners should
outrank high-frequency road noise.

### A testable structural encoding of the references

The images should be converted from visual examples into annotated fixtures.
The following encoding is a hypothesis to be checked by an annotator, not
ground truth recovered from pixels:

| Reference | high-information landmarks | relations that should survive | likely catastrophic failures |
|---|---|---|---|
| heart in `expected1` | central concave notch, two lobe maxima, lower tip | notch lies between lobes; both sides converge on lower tip; closed outer cycle | filled-in notch, one lost lobe, open contour, rounded-away tip |
| attached arrow in `expected1` | shaft endpoints, two arrowhead tips, attachment/near-attachment region | long shaft leads away from heart; head is at distal end; two head arms meet shaft | head at wrong end, connector mistaken for heart edge, invisible transfer stroke |
| arrow in `expected2` | tail, two shaft/head shoulder transitions, tip | ordered tail→shaft→head→tip; two head arms form a pointed terminal structure | reversed direction, fork without tip, discontinuous shaft, large unintended loop |

Each landmark should store target arclength, type, scale, expected turn sign,
importance weight, and allowable correspondence interval. Each relation should
store adjacency/order and, where meaningful, a scale-normalised length or
angle interval. Route evaluation then returns both a numeric residual and a
failure label. “Arrow tip unmatched” is more actionable than “similarity fell
from 0.52 to 0.48.”

### Component and transfer ambiguity

The heart-plus-arrow example also exposes a representation question. If the
ideal art contains two disconnected strokes, a continuous GPS recording must
add a transfer path, retrace an existing path, or permit a pause. These outputs
are perceptually different. The fixture must state which is allowed before an
algorithm can be judged correct. Pixel proximity alone cannot infer that
policy.

### Proposed reference acceptance vector

Do not replace the reference with one cutoff. Store a vector such as

\[
 a=(L_{matched},R_{order},R_{topology},D_F,Q_{95},E_{length},F_{route}),
\]

where the first three measure landmark, order, and topology retention; the next
two measure global and robust local deviation; and the final terms measure
length accuracy and graph feasibility. Initial values are engineering
hypotheses. Only held-out human and physical-execution results can turn them
into empirically calibrated acceptance rules.

### Shared interface requirements

- show ideal and routed curves simultaneously;
- fit the map to both;
- make important guide/control points visible and editable;
- show candidate rank, distance, score, and warnings together; and
- provide genuinely diverse alternatives, not cosmetic duplicates.

The displayed 46–54% values also illustrate why a numeric threshold cannot be
assumed to be a law of perception. It must be calibrated against human
judgements.

## 11. Evaluation protocol required for scientific claims

### 11.1 Benchmark corpus

Stratify by:

- shape class: smooth, angular, concave, self-intersecting, open, closed,
  multi-stroke, text;
- graph class: orthogonal grid, radial, irregular historic core, suburban,
  sparse/rural;
- obstacles: rivers, railways, motorways, parks, disconnected components;
- activity profile and requested distance; and
- GNSS condition: open sky, tree cover, ordinary urban, urban canyon.

Retain the supplied expected/failure images as qualitative fixtures, then add
machine-readable target and route polylines so regression tests can be exact.

### 11.2 Automated outcomes

Report every component, not only a combined score:

- discrete Fréchet and robust bidirectional deviation;
- coverage and extra-excursion error;
- tangent/turn sequence;
- multiscale salient-landmark preservation;
- global extent and local/total length relations;
- topology, stroke, and closure checks;
- distance error and route feasibility;
- candidate overlap/diversity;
- runtime, external calls, and failure rate.

### 11.3 Human study

Use blinded participants who did not tune the algorithm. Suitable tasks are:

- free naming of the drawing;
- forced choice among plausible labels;
- pairwise preference between candidates;
- confidence and perceived distortion ratings; and
- route-followability/safety review by local users.

Split calibration and final test sets. Fit score weights/thresholds only on the
calibration set, report inter-rater agreement and uncertainty, and publish
confusion matrices by shape and city class. Run ablations removing each metric
to demonstrate that it contributes rather than merely sounding plausible.

The unit of analysis is not an isolated rating. Ratings are nested within
people, shapes, placements, and cities. For binary recognition, one suitable
confirmatory model is

\[
 \operatorname{logit}\Pr(y_{u,s,c,r}=1)=
 \beta_0+\beta^\mathsf T x_r+b_u+b_s+b_c,
\]

with predeclared fixed predictors \(x_r\) and random intercepts for participant
\(u\), shape \(s\), and city/context \(c\). Add random slopes only when the
design and sample size support them. Report coefficient uncertainty and
predicted probabilities, not only p-values. For pairwise preferences, a
Bradley–Terry-type model can estimate relative candidate strength while
accounting for repeated raters.

### 11.4 Planned-versus-executed validation

For a subset, physically traverse the routes with multiple devices or repeat
runs. Compare the intended contour, planned graph route, raw GNSS trace, and
post-hoc map match. Without this layer, claims apply only to route planning,
not to GPS art as it will actually appear.

### 11.5 Predeclared falsifiable hypotheses

Examples that turn design intuitions into science:

- **H1:** adding landmark/order features improves held-out human recognition
  over a geometry-only model at matched route length;
- **H2:** topology violations predict recognition failures after controlling
  for Fréchet and robust local deviation;
- **H3:** a GNSS-robust objective improves raw-trace landmark survival over a
  planned-geometry objective under repeated urban runs;
- **H4:** final-route overlap control increases perceived alternative diversity
  without reducing median recognition below a predeclared non-inferiority
  margin;
- **H5:** feature-to-noise ratio predicts physical landmark survival across
  devices and environments after controlling for feature type.

State the primary outcome, direction, exclusion rules, model, multiplicity
policy, and smallest practically important effect before observing the final
test set. A failed hypothesis is a useful result; moving thresholds after
seeing the test labels is not validation.

### 11.6 Splitting, leakage, and external validity

Randomly splitting candidate routes leaks nearly identical shapes and nearby
road networks across train and test. Use grouped splits by target identity and
spatial blocks, and reserve entire cities or graph classes for external tests.
[Roberts et al. (2017)](https://doi.org/10.1111/ecog.02881) explain why
spatially structured data require blocked rather than naive random
cross-validation. At minimum report:

1. an interpolation test on held-out placements in known cities;
2. a held-out-shape test;
3. a held-out-city/region test; and
4. a prospective physical-execution test collected after model freezing.

The candidate generator must run independently inside every validation fold.
Otherwise the test geography can influence placement, pruning, or weight
selection even if its labels remain hidden.

### 11.7 Reliability, calibration, and uncertainty

Use agreement statistics only for the question they answer. Krippendorff's
alpha can accommodate multiple raters and missing data, but agreement is not
validity and depends on prevalence/category definition; see [Hayes and
Krippendorff (2007)](https://doi.org/10.1080/19312450709336664). For model
uncertainty, resample at the highest independent unit—typically shape/city and
participant clusters—rather than treating thousands of ratings as independent.
The bootstrap originates with [Efron
(1979)](https://doi.org/10.1214/aos/1176344552), but the resampling scheme must
match this hierarchy.

If a UI value is presented as \(P(\text{recognized})\), test it as a
probability with held-out log loss, Brier score, calibration intercept/slope,
and a reliability diagram. ROC or rank correlation measure discrimination,
not probability calibration. If that evidence is absent, label the value a
relative similarity score.

### 11.8 Baselines, ablations, and effect sizes

The comparison set should include:

- nearest-edge/waypoint routing;
- geometry-only Fréchet or Hausdorff ranking;
- Waschk–Krüger-style target-relative search;
- Li–Fu-style invariant structural retrieval where applicable;
- the full proposed system; and
- ablations removing landmarks, topology, GNSS robustness, route cost, and
  diversity one at a time.

Run paired comparisons on the same target–city–distance cases. Publish the
number and type of outright failures; discarding infeasible outputs biases the
result. Report median/mean paired differences, an interpretable effect size,
and clustered confidence intervals. Determine sample size by simulation from a
plausible hierarchical model and the smallest effect worth detecting—there is
no universal participant count.

### 11.9 Minimum research-grade dataset schema

Every benchmark item should preserve enough provenance for replication:

| layer | minimum fields |
|---|---|
| target | stable ID/version, stroke polylines, open/closed flag, semantics, landmarks, relation graph, licence |
| placement | CRS, translation, rotation, scale, mirror flag, search seed, search-space bounds |
| road graph | extract/source, timestamp, bounding area, profile, edge IDs/geometries, attributes, restrictions |
| candidate | algorithm/config/version, raw objectives, constraints, runtime, seed, failure/warning codes |
| planned route | ordered edges, geometry, distance, elevation, transfers/retracing, router response provenance |
| execution | anonymised device class, timestamps, raw coordinates, reported accuracy, sampling policy, weather/context, matched path kept separately |
| human label | anonymised participant/block, task, alternatives/order, response, confidence, response time, exclusions |

Coordinates may disclose home, habits, or sensitive locations. Public datasets
need consent, spatial/privacy review, data minimisation, retention rules, and a
documented de-identification policy. Removing names alone does not anonymise a
trajectory.

## 12. What this repository implements

Implemented approximations:

- normalised templates and text strokes;
- translation/rotation/scale placement search;
- curvature-preserving guide sampling;
- batched nearest-edge preflight with explicit non-connectivity status;
- quality-and-transform-diverse Directions shortlist;
- activity-specific connected routing via ORS;
- shared-frame Fréchet, Hausdorff/coverage, turn, length, extent, closure, and
  distance measurements;
- **multiscale salient curvature-landmark scoring** with travel-direction and
  closed-loop start invariance;
- an explicit excess-reversal gate that compares near-U-turn events with the
  intended drawing, so a route cannot hide doubled-back strokes inside a good
  average curve score;
- retention of all fully routed candidates and manual re-routing after edits.

Geographic coverage uses the [KSH list of Hungary's 50 largest settlements on
1 January 2025](https://www.ksh.hu/stadat_files/fol/en/fol0014.html) as a
reproducible product boundary. All 50 have local centres and bounded urban
search areas, and the 12 formerly missing entries now also have terrain,
water, and infrastructure notes. Population is only a coverage criterion: it
does not prove that a city or neighbourhood has enough connected, legal roads
for a particular drawing. Preflight and full activity-specific routing still
measure that question per request.

The European extension adds 30 cities spanning western, northern, central,
southern, and eastern Europe. Selection uses the harmonised city concept and
territorial coverage documented by [Eurostat City Statistics](https://ec.europa.eu/eurostat/web/cities/methodology),
then deliberately balances regions instead of presenting a misleading
cross-country population ranking. [Boeing's street-network study](https://doi.org/10.1007/s41109-019-0189-1)
shows why one generic “European city” heuristic would be unsound: orientation
order, circuity, intersection structure, and segment lengths differ
substantially between cities. Accordingly, every selected city has local
search bounds and context for water, terrain, parks, historic cores, and major
infrastructure. These descriptions seed the transform search; they do not
replace activity-specific graph measurements.

### 12.1 City–shape recommendation model

The previous recommender attached one running and one cycling symbol to each
city name. That produced variety but did not establish that the nominated
geometry matched the route distance or street fabric. It could also recommend
a culturally associated but fragile outline—for example a multi-stroke animal—
without comparing it with the other 72 templates.

The replacement performs a complete deterministic registry audit. For every
template it measures stroke count, closure, normalized drawn length, sharp
turns, accumulated turning, four-axis orientation concentration, aspect ratio,
complexity, and an explicit routeability prior. Curated city descriptions are
converted to continuous grid-order, connectivity, barrier, terrain, and radial
traits. The supported detail level is the minimum of city capacity and an
activity/distance capacity; cycling is modelled separately because walkable and
drivable networks can differ in circuity and connectivity
([Boeing, 2017](https://arxiv.org/abs/1708.00836)).

All 73 templates receive a score. Automatic suggestions choose three
high-scoring, continuous candidates from different geometry families. Templates
with disconnected strokes remain available for explicit requests, but they do
not enter the automatic shortlist because their transfer legs can create lines
that are absent from the intended image. Powałka's candidate-ranking result
supports using this score only as a shortlist prior: the existing transform
search, activity-specific Directions route, and independent validation gates
still determine the returned route. The implementation and the exhaustive
city/template audit are documented in
[City-aware shape recommendations](city-shape-recommendations.md).

This is a quality-oriented engineering model, not a learned probability of
recognition. Its city inputs are curated prose rather than frozen
neighbourhood-scale graph measurements, and its shape weights have not yet been
calibrated against human labels. The UI therefore says “suggested,” gives a
plain-language reason, and preserves route checks rather than claiming an
optimal drawing.

Important gaps:

- ORS does not expose a target-dependent edge cost, so this is not exact
  shape-guided graph search;
- preflight snaps do not prove graph connectivity;
- local segment-length ratios and graph topology are only approximated by
  curve/landmark diagnostics;
- there is no calibrated human-recognition dataset yet;
- road-edge overlap is not yet used for final candidate diversity;
- GNSS execution noise is warned about but not simulated; and
- safety/access remain dependent on third-party map data and manual review.

### 12.2 Claim-to-evidence ledger

| Product statement | What the implementation may currently support | What it must not imply |
|---|---|---|
| “on roads” | selected control points are near routable geometry, or a Directions response supplied connected route geometry | every point is legal, current, accessible, or safe in reality |
| “shape fidelity 80%” | an internal monotone composite of documented geometric/structural features | 80% probability of human recognition or 20% physical error |
| “landmarks preserved” | detected multiscale turns were corresponded under stated tolerances | semantic parts are recognized by people |
| “route feasible” | a router found a path for its profile and map state | temporary closures, conditions, or individual capability were verified |
| “diverse alternatives” | candidates differ in transform and/or geometry under the implemented overlap proxy | statistically independent routes or meaningfully different user experiences |
| “GPS robust” | only valid after simulation plus held-out repeated physical traces | robustness inferred from planned road geometry alone |

This vocabulary should be shared by UI copy, tests, API schemas, and research
reports. It is a scientific control against claim inflation.

## 13. Prioritised research roadmap

1. **Human-labelled benchmark:** this is required before calling any threshold
   a recognisability threshold.
2. **Target-aware local graph engine:** reproduce/compare the Waschk–Krüger
   edge cost and Li–Fu invariant graph retrieval on the same corpus.
3. **Explicit topology and segment relations:** score junctions,
   self-intersections, sub-strokes, turning angles, and adjacent-length ratios.
4. **Final-route diversity:** calculate shared-edge or buffered geometric
   overlap after Directions routing.
5. **Feasibility model:** incorporate access, surface, elevation, crossings,
   lighting, and time-dependent restrictions with transparent provenance.
6. **GNSS robustness:** simulate and then physically measure sampling and
   urban-canyon noise.
7. **Pareto UI:** let users select recognisability, distance accuracy,
   simplicity, and safety trade-offs without hiding the raw metrics.
8. **Reproducibility package:** freeze road extracts, target annotations,
   configuration/seeds, raw objective vectors, failures, and an analysis
   script; external API responses alone are not indefinitely reproducible.
9. **Hierarchical human model:** calibrate recognition on grouped spatial
   splits and verify probability calibration prospectively.
10. **Execution-aware guidance:** warn before high-information turns and test
    whether shape-aware recovery preserves more landmarks after mistakes.

## 14. Accessible core bibliography

This is a curated theory spine, not padding: every group addresses a distinct
claim that a GPS-art system must make. DOI links may lead to publisher pages;
open manuscripts/repositories are linked where located.

### Direct GPS-art and embodied-drawing work

- Balduz, P. (2017). [Walk line drawing](https://www.cg.tuwien.ac.at/research/publications/2017/Balduz_01/).
- Rosner, D. K., et al. (2015). [Walking by Drawing](https://doi.org/10.1145/2702123.2702467).
- Baloian, N., Biella, D., & Luther, W. (2020). [GPS Drawing on Street Networks: Extracting Routes from Polygonal Coverings](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00075701/Hajian_et_al_2020_Collaborative_Technologies.pdf) [open book chapter].
- Waschk, A., & Krüger, J. (2019). [Automatic route planning for GPS art generation](https://doi.org/10.1007/s41095-019-0146-z); [open manuscript](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00072443/Waschk_et_al_Automatic_Route_Planning.pdf).
- Powałka, L. P. (2023). [Shape-guided artistic route finding](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad).
- Zhang, Y., Sun, C., Cheng, H., & Fu, Z. (2025). [Research on a road-graphic retrieval method for GPS art](https://dxkj.cbpt.cnki.net/portal/journal/portal/client/paper/a80384ddba058c588b4b7ad6ea9e233d) [Chinese; public bilingual abstract].
- Li, G., & Fu, Z. (2026). [Invariant Spatial Relation-Based Road Network Graphics Retrieval for GPS Art](https://doi.org/10.3390/ijgi15030098) [open access].

### Curve comparison, simplification, and structural shape

- Arkin, E. M., et al. (1991). [An Efficiently Computable Metric for Comparing Polygonal Shapes](https://doi.org/10.1109/34.75509).
- Alt, H., & Godau, M. (1995). [Computing the Fréchet Distance Between Two Polygonal Curves](https://doi.org/10.1142/S0218195995000064).
- Eiter, T., & Mannila, H. (1994). [Computing Discrete Fréchet Distance](https://www.kr.tuwien.ac.at/staff/eiter/et-archive/files/cdtr9464.pdf).
- Belongie, S., Malik, J., & Puzicha, J. (2002). [Shape Matching and Object Recognition Using Shape Contexts](https://doi.org/10.1109/34.993558).
- Klein, P. N., Sebastian, T. B., & Kimia, B. B. (2001). [Shape matching using edit-distance: an implementation](https://cs.brown.edu/people/pklein/publications/2001shapeMatching.pdf).
- van de Kerkhof, M., et al. (2019). [Global Curve Simplification](https://doi.org/10.4230/LIPIcs.ESA.2019.67) [open access].
- Bringmann, K., & Chaudhury, B. R. (2020). [Polyline simplification has cubic complexity](https://doi.org/10.20382/jocg.v11i2a5) [open access].
- Buchin, K., et al. (2020). [Progressive simplification of polygonal curves](https://doi.org/10.1016/j.comgeo.2020.101620).

### Curve-to-graph matching, graph routing, and optimisation

- Alt, H., Efrat, A., Rote, G., & Wenk, C. (2003). [Matching planar maps](https://doi.org/10.1016/S0196-6774%2803%2900085-3); [open manuscript](https://page.mi.fu-berlin.de/rote/Papers/pdf/matching-planar-maps.pdf).
- Wylie, T., & Zhu, B. (2014). [Intermittent Map Matching with the Discrete Fréchet Distance](https://arxiv.org/abs/1409.2456).
- Gudmundsson, J., et al. (2022). [Fréchet Distance Oracles for Realistic Graphs](https://arxiv.org/abs/2211.02951).
- Edmonds, J., & Johnson, E. L. (1973). [Matching, Euler tours and the Chinese postman](https://doi.org/10.1007/BF01580113).
- Lenstra, J. K., & Rinnooy Kan, A. H. G. (1976). [On general routing problems](https://doi.org/10.1002/net.3230060305).
- Warburton, A. (1987). [Approximation of Pareto Optima in Multiple-Objective, Shortest-Path Problems](https://doi.org/10.1287/opre.35.1.70).
- Kim, I. Y., & de Weck, O. L. (2005). [Adaptive weighted-sum method for bi-objective optimization](https://doi.org/10.1007/s00158-004-0465-1).
- Nassir, N., et al. (2014). [Choice Set Generation Algorithm Suitable for Measuring Route Choice Accessibility](https://doi.org/10.3141/2430-18).

### Perceptual organisation and contour recognition

- Attneave, F. (1954). [Some informational aspects of visual perception](https://doi.org/10.1037/h0054663).
- Richards, W., Dawson, B., & Whittington, D. (1986). [Encoding contour shape by curvature extrema](https://doi.org/10.1364/JOSAA.3.001483).
- Mokhtarian, F., & Mackworth, A. K. (1992). [A Theory of Multiscale, Curvature-Based Shape Representation](https://www.cs.ubc.ca/~mack/Publications/IEEE-PAMI92.pdf).
- Feldman, J., & Singh, M. (2005). [Information Along Contours and Object Boundaries](https://doi.org/10.1037/0033-295X.112.1.243).
- De Winter, J., & Wagemans, J. (2008). [Perceptual saliency of points along the contour of everyday objects](https://doi.org/10.3758/PP.70.1.50).
- Tversky, T., Geisler, W. S., & Perry, J. S. (2004). [Contour grouping: closure effects are explained by good continuation and proximity](https://doi.org/10.1016/j.visres.2004.06.011).
- Garrigan, P. (2012). [The Effect of Contour Closure on Shape Recognition](https://doi.org/10.1068/p7145).
- Schmidtmann, G., et al. (2026). [Connecting the dots—recognition of artificial and natural shapes relies on representing points of high information](https://doi.org/10.1016/j.visres.2026.108865) [open access].

### Sketch maps and qualitative spatial relations

- Schwering, A., et al. (2014). [SketchMapia: Qualitative representations for the alignment of sketch and metric maps](https://doi.org/10.1080/13875868.2014.917378).
- Lu, Y., et al. (2023). [Hand-drawn sketch and vector map matching based on topological features](https://doi.org/10.3389/feart.2023.1081445) [open access].

### Map matching, GNSS, and geographic data

- Brakatsoulas, S., et al. (2005). [On Map-Matching Vehicle Tracking Data](https://www.vldb.org/conf/2005/papers/p853-brakatsoulas.pdf).
- Newson, P., & Krumm, J. (2009). [Hidden Markov Map Matching Through Noise and Sparseness](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/12/map-matching-ACM-GIS-camera-ready.pdf).
- Zandbergen, P. A., & Barbeau, S. J. (2011). [Positional Accuracy of Assisted GPS Data from High-Sensitivity GPS-enabled Mobile Phones](https://doi.org/10.1017/S0373463311000051).
- Weng, D., et al. (2023). [Characterization and mitigation of urban GNSS multipath effects on smartphones](https://doi.org/10.1016/j.measurement.2023.113766).
- U.S. Government (2020). [GPS Standard Positioning Service Performance Standard, 5th edition](https://www.gps.gov/technical/ps/2020-SPS-performance-standard.pdf).
- Barron, C., Neis, P., & Zipf, A. (2014). [A comprehensive framework for intrinsic OpenStreetMap quality analysis](https://doi.org/10.1111/tgis.12073).
- Barrington-Leigh, C., & Millard-Ball, A. (2017). [The world's user-generated road map is more than 80% complete](https://doi.org/10.1371/journal.pone.0180698) [open access].
- ISO (2023). [ISO 19157-1:2023—Geographic information: Data quality](https://www.iso.org/standard/78900.html).

### Route choice and empirical validation

- Boeing, G. (2017). [The Morphology and Circuity of Walkable and Drivable Street Networks](https://arxiv.org/abs/1708.00836).
- Broach, J., Dill, J., & Gliebe, J. (2012). [Where do cyclists ride? A route choice model developed with revealed preference GPS data](https://doi.org/10.1016/j.tra.2012.07.005).
- Minetti, A. E., et al. (2002). [Energy cost of walking and running at extreme uphill and downhill slopes](https://doi.org/10.1152/japplphysiol.01177.2001).
- Roberts, D. R., et al. (2017). [Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure](https://doi.org/10.1111/ecog.02881).
- Hayes, A. F., & Krippendorff, K. (2007). [Answering the call for a standard reliability measure for coding data](https://doi.org/10.1080/19312450709336664).
- Efron, B. (1979). [Bootstrap methods: another look at the jackknife](https://doi.org/10.1214/aos/1176344552).
