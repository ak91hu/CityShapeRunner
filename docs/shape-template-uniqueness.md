# Recognisable and unique GPS-art templates

## Decision

Catalog templates are authored as route targets, not as decorative icons. Each
animal should keep a different, readable silhouette after road snapping, and no
two canonical names may encode the same routed contour under translation,
uniform scale, rotation, a different closed-loop start, or reversed traversal.

The focused redesign replaces the former animal drawings with:

| Template | Recognition-bearing contour features | Route constraint |
|---|---|---|
| Cat | Sitting side profile, two pointed ears, muzzle, chest/front paws, raised curved tail | One closed outline; the tail is broad and does not retrace the body |
| Dog | Standing side profile, broad raised tail, floppy ear, long muzzle, chest, belly, and two separated legs | One closed outline; limb notches remain shallow enough for street snapping |
| Bird | Top-view flight silhouette with one beak, long tapered wings, two secondary-feather notches, and a forked tail | One closed outline replaces four disconnected strokes and their visible transfers |
| Bat | Two pointed ears, short body/tail axis, broad leading wing edges, and three membrane scallops per side | One closed outline; scallops are deliberately wider than a typical junction-scale wiggle |
| Diamond | Flat gemstone crown and tapered pavilion | Replaces the former square rotated by 45 degrees |

The web catalog also gives every one of its 141 options a recognisable visible
marker. Cat, dog, bird, and bat use separate animal glyphs; the same cleanup
covers every previously repeated marker in the animal category.

## Research synthesis

The implementation uses primary research for constraints, then makes explicit
engineering inferences for this application:

1. Attneave's contour-abstraction experiment found strong agreement on the
   points people chose to retain; these concentrated around the largest changes
   in contour direction. He also demonstrated an economical cat drawing made
   from high-curvature contour points. This supports spending the template's
   limited landmark budget on ears, muzzle, paws, wing tips, scallops, and tail
   notches rather than uniformly adding detail
   ([Attneave, 1954](https://doi.org/10.1037/h0054663)).
2. In an animal/non-animal decision experiment, silhouettes performed similarly
   to shaded line drawings. The head outline was the most salient region,
   followed by the lower torso and legs. This directly motivates distinct head
   profiles for cat and dog and retaining their lower-body stance
   ([Lloyd-Jones, Gehrke, and Lauder, 2010](https://doi.org/10.1027/1618-3169/a000015)).
3. Shape Contexts compare point distributions on contours after correspondence
   and alignment, with invariance to translation and scale and optional rotation
   invariance. The catalog guard needs the narrower problem of detecting the
   same authored polyline, so a deterministic resampled Procrustes comparison is
   sufficient and easier to audit than a semantic classifier
   ([Belongie, Malik, and Puzicha, 2002](https://vision.ucsd.edu/publications/2002/shape-matching-and-object-recognition-using-shape-contexts)).
4. Waschk and Krüger show that ordinary waypoint routing may erase detail,
   create detours, or degenerate into U-turns when too many off-street points
   are forced. They explicitly note that fine structures are hard to place on a
   street network. This rules out whiskers, eyes, narrow ears, individual
   feathers, and other decorative sub-strokes as catalog geometry
   ([Waschk and Krüger, 2019](https://duepublico2.uni-due.de/servlets/MCRFileNodeServlet/duepublico_derivate_00072443/Waschk_et_al_Automatic_Route_Planning.pdf)).
5. Powałka treats placement and routing as a candidate-search problem with
   translation, rotation, scale, graph-aware cost, evaluation, and interactive
   correction. This supports testing uniqueness independently of pose while
   leaving actual street fit to the existing multi-placement routing pipeline
   ([Powałka, 2023](https://repository.tudelft.nl/record/uuid%3A11e9b0c2-5d67-475a-8653-71c7afe03dad)).

The resulting rule is not “more points means more detail.” It is “preserve a
small number of diagnostic contour events at street-scale separation.” This is
an engineering inference from the studies above, not a claim that the current
coordinates or thresholds were experimentally optimal.

## Automated catalog audit

`tools/shape_uniqueness.py` audits the actual route target:

1. normalize every template and join its sub-paths with the production
   deterministic transfer policy;
2. resample 96 positions uniformly by travelled arc length;
3. remove translation and uniform scale;
4. fit the best planar rotation;
5. for closed outlines, try every cyclic start phase;
6. compare both traversal directions; and
7. fail the catalog if normalized RMS Procrustes distance is at most `0.02`.

Reflection remains distinct because production placement rotates but does not
mirror a template. The audit compares the line that would be sent toward the
map, so disconnected strokes and their transfer segments cannot hide behind a
different source representation.

Before the redesign, `square` and `diamond` scored exactly `0.0`: they were the
same contour under rotation. After the expansion, the complete 128-template
matrix contains 8,128 unique pairs and no duplicate below the guard threshold.
The closest remaining intentional relatives are `circle` and `octagon`, around
`0.025`; the smooth circle and eight preserved corners remain separate targets.

The guard proves uniqueness of catalog targets, not uniqueness of every routed
result in every location. On an extremely sparse street graph, different
targets can still collapse onto the same few streets. That downstream risk is
handled by target-specific route fidelity, turning, extent, collapse, and
manual-review gates rather than by pretending the source audit can predict all
street networks.

## Regression coverage

- all four redesigned animals must be one simple closed path;
- every pair among cat, dog, bird, and bat must remain well outside the
  duplicate threshold;
- the distance must ignore translation, scale, rotation, loop start, and route
  direction on a synthetic contour;
- all 8,128 canonical template pairs must pass the duplicate audit;
- diamond and square must remain materially distinct; and
- all 141 visible catalog options must remain labelled, with direct assertions for
  cat, dog, bird, and bat.
