---
name: snap-and-roads
description: What snap-to-road does to a drawing, and how to use the simplify knob.
applies_to: [snap, refinement, planning]
tags: [ors, roads, simplify]
---

# Snap-to-road behaviour

- OpenRouteService routes through a bounded set of **guide points** along the
  drawing. Meaningful corners are protected; long edges are split to roughly
  400 m spacing until the 24-coordinate visual-guide budget is reached. The
  returned polyline is road-following; `snapped=True`.
- Without an ORS key the step falls back to a **great-circle connector**
  (`snapped=False`) — the shape is preserved exactly but is not runnable. In
  that mode `shape_fidelity` will be ~1.0; **the ValidationAgent caps the
  overall score at 0.4 and flags `on_roads=false`** so a straight-line route
  can never pass the recommendation or be silently labelled as a real route.
  It may still be exported as an explicitly unverified manual guide.
- `snap_radius_m` (default 120 m, set in `config/settings.yaml`) is passed to
  ORS as the per-coordinate `radiuses` parameter. It controls how far ORS may
  search for a road from each drawn point. Increase it if waypoints land on
  large building blocks or parks; decrease it if the route wanders too far
  from the intended shape.
- Snapping **distorts** the drawing: curves straighten, corners get cut, the
  route is usually 20–40% longer than the straight-line intent. That gap is
  exactly what `shape_fidelity` measures.
- A successful request can still be a poor drawing. Never treat
  `snapped=True` as a quality recommendation; fidelity, distance, closure, and
  overall score remain visible for ranking and editing.
- The `simplify_tolerance` (metres) denoises real road geometry. **Lower =
  more detail (better fidelity, longer GPX); higher = smoother (worse
  fidelity, smaller GPX).** Never simplify the straight-line fallback — it
  only discards drawn vertices.
- If a waypoint lands in a park/river with no nearby road, ORS routes around
  it, creating a spike. The RefinementAgent should nudge an offset, not rescale.
- Keep `continue_straight=false` for GPS art. Hearts, lettering, and other
  shapes contain cusps where the road route may need a U-turn; forcing straight
  travel can make an otherwise connected street route fail with ORS code 2009.
- Treat ORS error codes separately: widen the snap radius for code 2010
  (point not found), but for code 2009 remove the reported unconnectable
  interior via-point or reduce detail. Repeating larger radiuses for code 2009
  does not repair graph connectivity.
