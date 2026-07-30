---
name: route-placement
description: How to place a shape onto a real city at the target distance.
applies_to: [placement, planning]
tags: [geo, placement, scaling]
---

# Placing a shape on a real city

- **Centre on the city's geocoded point**, offset only when refining to escape
  a park/river. Offsets accumulate in `lat_offset_m` / `lon_offset_m`.
- **Scale to the target distance**, not to a bounding box. PlacementAgent
  divides the target by the stitched unit-path length and a conservative
  sport-specific road-network factor. RefinementAgent then corrects the scale
  from the actual routed distance using `target / actual`.
- If the prompt omits distance, use a practical 8 km running or 20 km cycling
  target. Do not use the midpoint of the allowed activity range.
- **Rotate to the local street grid when reliable map context provides its
  orientation.** The city bounding box's long axis is only a coarse
  city-extent fallback; it is not a measured street bearing. Grid cities (NYC,
  Barcelona) usually snap more cleanly than irregular old-core cities, but the
  routed result and fidelity score decide whether a rotation is suitable.
- **Equirectangular projection** is used (good to ~50 km). Don't place routes
  bigger than that — split them.
- **Sport bounds** (run ~3–60 km, bike ~10–200 km) are hard limits; if the
  target sits outside, clamp and flag it in the plan.
- Correct a large measured distance error first. When distance is reasonably
  close but `shape_fidelity` is low, test rotations and nearby offsets.
