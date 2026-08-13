# Custom free-text shape generation

## Goal

The catalog is a fast path, not a boundary. A request such as “an octopus
wearing a crown in Budapest, running, 12 km” must retain the complete drawing
idea, create a route-oriented outline when a model provider is available, and
explain any fallback honestly when it is not.

“Supported” does not mean that every noun can be converted into a recognisable
street route. It means that the request is preserved, generation is bounded and
validated, malformed geometry cannot enter routing, and the user can compare
the intended line with the routed result before exporting it.

## Research findings

Several adjacent research areas point to the same engineering pattern:

1. [Sketch-RNN](https://arxiv.org/abs/1704.03477) represents recognisable
   drawings as compact stroke sequences. This supports using ordered vector
   points rather than asking for a raster image and tracing its pixels.
2. [DeepSVG](https://papers.nips.cc/paper/2020/hash/bcf9d6bd14a2095866ce8c950b702341-Abstract.html)
   separates high-level shapes from low-level drawing commands. The application
   follows the same boundary: intent parsing owns the semantic request, while
   ShapeAgent owns only route geometry.
3. [IconShop](https://arxiv.org/abs/2304.14400) reports that a uniquely
   decodable vector token sequence is central to reliable text-guided icon
   synthesis. A strict JSON point-list schema is less expressive than full SVG,
   but it is deterministic to parse, easy to bound, and maps directly to this
   route engine.
4. [Chat2SVG](https://openaccess.thecvf.com/content/CVPR2025/papers/Wu_Chat2SVG_Vector_Graphics_Generation_with_Large_Language_Models_and_Image_CVPR_2025_paper.pdf)
   uses an LLM for a semantic vector scaffold and separate optimisation for
   geometric quality. This argues against trusting one raw model response as a
   finished route. GPS Art Wizard substitutes executable topology checks, a
   bounded repair request, and road-network optimisation for the paper's image
   diffusion stages.
5. [Waschk and Krüger](https://doi.org/10.1007/s41095-019-0146-z) show that
   ordinary waypoint routing can seriously deform GPS art, while
   [Powałka](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)
   combines transform search, several route candidates, evaluation, and
   interactive correction. Therefore a valid generated silhouette is only the
   start of the process; placement and routed measurements remain authoritative.
6. Cartographic simplification research explicitly checks topology because
   simplification can introduce boundary crossings. The
   [USGS summary of Kronenfeld et al.](https://pubs.usgs.gov/publication/70210904)
   records self-intersection as an evaluated failure mode and topology checks as
   its mitigation. The custom-shape smoother therefore cannot silently replace
   a simple control polygon with a crossed curve.
7. OpenAI's [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
   distinguishes ordinary JSON mode—which guarantees only parseable JSON—from
   strict schema adherence. Anthropic documents the same constrained-decoding
   approach for its [supported newer Claude models](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
   and Ollama accepts a schema directly in its native
   [`format` field](https://docs.ollama.com/capabilities/structured-outputs).
   Provider-level constraints can prevent structural retries, but local
   geometry checks remain necessary because a schema cannot prove topology or
   recognisability.

The practical conclusion is a staged pipeline with cheap deterministic checks
around one structured generative call, rather than a chain of unconstrained
model calls. The single response carries two alternatives so topology failure
in the preferred drawing does not immediately spend a repair request.

## Implemented decision pipeline

### 1. Preserve the request locally

IntentAgent removes city, activity, and distance clauses but keeps semantic
modifiers such as “flying”, “wearing a crown”, or “riding a bicycle”. A catalog
keyword is used only when it describes the whole candidate. This prevents a
composite request containing “crown” from collapsing to the built-in crown
template.

Suggestion detection uses word-bounded task phrases. Object names such as
“pickaxe” and “idea bulb” no longer trigger suggestion mode by substring.

The fast path also understands common Hungarian route phrasing. It separates
inflected settlement names (for example `Budapesten`, `Győrben`, and `Pécsen`),
Hungarian running/cycling words, decimal-comma distances, request verbs, and
recommendation phrases. The original object wording and its modifiers remain
intact for generation, while route metadata is kept in structured intent
fields. Requests that cannot be separated confidently still use intent-model
inference rather than an aggressive local guess.

### 2. Spend inference only on geometry

Known templates and text remain fully local. A locally parsed custom request
also uses deterministic city planning because curated placement context already
provides the rotation, offset, and difficulty prior. The usual custom request
therefore needs one model call—the shape scaffold—not separate intent, planning,
and shape calls.

### 3. Treat the description as untrusted data

The shape and style values are JSON-encoded before prompt interpolation. The
prompt states that embedded instructions are data and narrows output to one JSON
schema. The server never executes generated SVG, XML, Python, or JavaScript.

### 4. Generate route-oriented control geometry

The model first emits three to six identifying silhouette cues, including
modifiers and relationships, then creates two meaningfully different route
scaffolds and marks the one it expects to remain clearest at thumbnail size.
Each alternative uses 20–48 meaningful control points, normally as one closed
outer silhouette. ShapeAgent tries the preferred alternative first and then
the other one, but accepts either only after the same executable geometry
checks. This separates a semantic preference from authoritative topology.

When a compound request contains a catalogued base subject—such as “a robot
holding an umbrella”—the prompt also receives a compact trusted copy of that
base contour. The model must preserve its major masses, proportions,
concavities, and part hierarchy while changing the contour for the requested
pose or accessory. The earliest named subject is used, so a held object does
not accidentally replace the main subject as the geometry anchor. Uncatalogued
subjects continue without an anchor.

The model is told not to substitute a stock category icon and to omit eyes,
shading, texture, and other details that would require disconnected transfer
lines. Point density is reserved for meaningful curvature changes rather than
tiny interpolated steps.

The same point-list contract is also passed to capable providers as a JSON
schema. OpenAI uses strict `json_schema`, OpenCode Zen sends this job to its
configured GPT-5.4 mini Responses model with strict `text.format`, local Ollama
uses its schema-valued `format`, and documented Claude 4.5+ families use
Anthropic's structured-output configuration. Older or custom models retain
portable JSON mode plus the full local validator, because silently assuming a
model feature would turn compatibility errors into needless fallback routes.

### 5. Run executable geometry checks

Before placement, the parser enforces:

- JSON list structure and finite numeric coordinate pairs;
- a strict response contract of at most eight strokes and 96 points per stroke
  in each of exactly two alternatives; the defensive legacy parser remains
  capped at 240 points per stroke and 800 points in total;
- exact closure when the response declares a closed drawing;
- at least six control points for generated geometry;
- non-degenerate width and height;
- a maximum 4:1 defensive aspect-ratio boundary;
- coordinates in the documented `[-10, 10]` range; and
- no self-intersection in any substantial stroke;
- no multi-stroke design whose artificial connectors exceed 45% of its
  authored drawing length; and
- no placement-invariant duplicate of a registered catalog route.

The prompt targets the stricter 2:1 design preference. The 4:1 executable limit
allows naturally tall or wide subjects while still rejecting geometry that is
not a useful city-scale scaffold.

### 6. Repair once, then stop

If the preferred alternative is invalid, ShapeAgent tries the second one from
the same response before making another network call. If both are malformed,
collapsed, extremely stretched, duplicated, or self-crossing, it sends one
low-temperature repair request containing both validation reasons. A fixed
single retry prevents accidental latency and cost loops. If the repair also
fails, deterministic fallback takes over.

### 7. Smooth without erasing identity or changing topology

Custom control paths use the centripetal Catmull–Rom parameterisation described
by [Yuksel, Schaefer, and Keyser](https://cemyuksel.com/research/catmullrom_param/).
Unlike the former uniform formula, it cannot introduce a cusp or
self-intersection inside one spline segment merely because controls are unevenly
spaced. Turns of at least 70 degrees keep their adjacent segments linear so
ears, tips, and notches survive smoothing. The whole smoothed stroke is still
accepted only if it remains simple; otherwise the original control polygon is
retained.

Normalisation uses the route-length-weighted centroid rather than the raw mean
of control points. Adding more controls around one detailed feature therefore
cannot drag the whole drawing's placement off-centre. If multiple essential
strokes remain, an exact bounded dynamic program chooses their order and
direction to minimise connector length. Later guide-point selection preserves
important curvature while respecting the routing provider's waypoint budget.

### 8. Cache only successful custom drawings

A 128-entry process-local least-recently-used cache keys successful generated
geometry by a SHA-256 digest of the normalized request and style plus a schema
version. Validation or prompt-contract changes bump that version. The raw
custom wording is not retained in the cache key or value.
Callers receive fresh path lists so one route cannot mutate another. Provider
failures and deterministic fallbacks are never cached, so a short outage cannot
poison later requests.

### 9. Degrade honestly

Without a working model provider, the app renders the complete ASCII-normalised
requested phrase—for example `text:PLATYPUS`, never `P label`—and marks its
source as `fallback`. It does not rename a star as a platypus. The result screen
and fit decision retain the requested drawing name and explain the substitution.

### 10. Keep road evidence authoritative

Generated geometry enters the same placement preflight, activity-specific
Directions routing, independent recognition gates, editor, and explicit-review
flow as catalog shapes. A model-created outline receives no automatic quality
credit merely because its JSON was valid.

## Alternatives considered

| Option | Strength | Why it is not the default now |
|---|---|---|
| Text-to-raster image, then vector tracing | Can use strong image generators and visual conditioning | Adds another provider, raster artefacts, tracing ambiguity, more latency, and far too many vertices for street routing. |
| Full SVG generation | Bézier paths are compact and expressive | Safely parsing every SVG feature is a much larger attack and compatibility surface; most SVG semantics are irrelevant to a one-line route. |
| Three or more generated candidates on every request | Better chance of one strong silhouette | Output and validation cost rises quickly. Two alternatives in one structured response cover the common topology-failure case without tripling inference output. |
| Always substitute the nearest catalog shape | Fast and deterministic | Violates the named request and fails precisely where custom support matters. It remains only an explicitly disclosed last-resort route option. |
| Treat the model's preferred alternative as proof | Cheap semantic opinion | It is not independent evidence. The preference only controls trial order; executable geometry checks and routed measurements remain authoritative. |

## Remaining limitations and next experiments

Geometry validation cannot prove that a silhouette looks like the requested
object. The next meaningful quality step is an offline labelled evaluation set:
common objects, composite objects, abstract symbols, multilingual descriptions,
prompt-injection attempts, and deliberately impossible route ideas. Human raters
should score the intended outline before routing and the final line after
routing separately.

If that evaluation shows semantic generation is still the main bottleneck,
test a vision-language verifier on rendered outline thumbnails before routing.
The current two-scaffold response improves resilience and recognisability but
must not be described as a guarantee without labelled human agreement data.

User-supplied sketches or images are a separate feature. They require file
validation, foreground extraction, vectorisation, topology repair, and explicit
privacy handling; they should not be silently treated as the same problem as a
text-only custom shape.
