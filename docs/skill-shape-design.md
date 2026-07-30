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
  LLM-generated curves are Catmull-Rom smoothed at output. The routing sampler
  protects authored turns and inserts guides roughly every 250 m, up to the
  provider's 50-coordinate limit.
- **Include distinctive features** that make the shape read as the intended
  object: notches, lobes, ears, tails. A cat needs pointy ears; a fish needs
  a tail fin; a heart needs two lobes and a V-bottom.
- **Round off sharp corners slightly** — they collapse when snapped to roads.
- **Avoid long thin spikes** and deep narrow notches — they collapse to a single
  road.
- **No self-intersection.** Crossed lines produce a tangled GPX. Check it.
- **Use one continuous outline when possible.** Disconnected ears, eyes, or
  decorative strokes require visible transfer routes and usually reduce
  recognisability. The cat, dog, and tree templates deliberately integrate
  their distinctive features into one closed silhouette.
- **Aspect ratio ≤ 2:1** reads best. Stretch a shape and the streets can't
  follow. If the user wants "tall", warn via the plan's `difficulty`.
- **Text:** every A–Z letter and 0–9 digit is available through the simplex
  vector font. Treat each glyph stroke as its own sub-path, keep letters wide
  enough for roads to trace, and prefer one to four characters per route.
- **Normalisation is automatic** (centroid → origin, max side → 1.0). Emit raw
  proportions; do not pre-normalise.
- When drawing freely, align the shape's long axis with the X axis —
  PlacementAgent rotates it to the street grid afterwards.
