---
name: shape-design
description: Principles for designing shapes that survive being snapped to roads.
applies_to: [shape, planning]
tags: [geometry, shapes, drawability]
---

# Designing drawable GPS-art shapes

A shape must be **recognisable after road-snapping**, which straightens curves
and cuts corners. Design for that, not for a perfect vector outline.

- **Prefer closed outlines** for icons (heart, star, animal silhouettes). Open
  shapes (letters, arrows) are fine but harder to read on a map.
- **Author meaningful geometry, not point count.** Curves may be densely
  sampled, while angular outlines should keep only meaningful corners.
  LLM-generated curves are Catmull-Rom smoothed only when that does not
  introduce a self-intersection. The routing sampler
  protects authored turns and inserts guides roughly every 250 m, up to the
  provider's 50-coordinate limit.
- **Include distinctive features** that make the shape read as the intended
  object: notches, lobes, ears, tails. A cat needs pointy ears; a fish needs
  a tail fin; a heart needs two lobes and a V-bottom. For animals, spend the
  limited landmark budget on the head profile and lower-body stance before
  decorative detail.
- **Round off sharp corners slightly** — they collapse when snapped to roads.
- **Avoid long thin spikes** and deep narrow notches — they collapse to a single
  road.
- **No self-intersection.** Crossed lines produce a tangled GPX. Check it.
- **Use one continuous outline when possible.** Disconnected ears, eyes, or
  decorative strokes require visible transfer routes and usually reduce
  recognisability. The cat, dog, and tree templates deliberately integrate
  their distinctive features into one closed silhouette; bird and bat do too.
- **Keep canonical targets unique.** Run the rotation-, scale-, phase-, and
  direction-independent catalog audit when adding or changing a template. A
  second name must not encode the same map-bound contour.
- **Aspect ratio ≤ 2:1** reads best. Stretch a shape and the streets can't
  follow. If the user wants "tall", warn via the plan's `difficulty`.
- **Text:** every A–Z letter and 0–9 digit is available through the simplex
  vector font. Treat each glyph stroke as its own sub-path, keep letters wide
  enough for roads to trace, and prefer one to four characters per route.
- **Normalisation is automatic** (centroid → origin, max side → 1.0). Emit raw
  proportions; do not pre-normalise.
- When drawing freely, align the shape's long axis with the X axis —
  PlacementAgent rotates it to the street grid afterwards.

The focused evidence and the automated 73-template comparison are documented
in [Recognisable and unique GPS-art templates](shape-template-uniqueness.md).
