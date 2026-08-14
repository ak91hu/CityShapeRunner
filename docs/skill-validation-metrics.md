---
name: validation-metrics
description: What each validation metric means and how to read a failing score.
applies_to: [validation, refinement, planning]
tags: [metrics, scoring]
---

# Reading validation metrics

The overall `score` is a weighted blend. Closed shapes: `0.5·fidelity + 0.3·distance_fit + 0.2·closure`. Open shapes: `0.6·fidelity + 0.4·distance_fit` (closure not applicable).

- **shape_fidelity** (0–1): how close the snapped route is to the *placed*
  drawing. It is a weighted geometric mean of shared-frame Fréchet/Hausdorff,
  bidirectional coverage, tangent sequence, multiscale salient landmarks,
  route-length preservation, and width/height preservation. The dominant
  metric.
  - `< 0.7` → the shape is below the recommended recognisability target; correct any
    large distance error, then test rotation/offset or tighten simplification.
- **distance_fit** (0–1): how well total distance matches the target (or the
  sport's bounds when no target is given).
  - `< 0.6` and route too long → shrink scale; too short → grow scale.
- **closure** (0–1, closed shapes only): 1.0 minus the normalised gap between
  the first and last snapped points.
  - `< 0.6` → the loop didn't close; shrink scale slightly or nudge an offset
    away from a dead-end.
- **landmark_similarity** (0–1): whether high-information corners, concave
  notches, tips, and their approximate arc-length phases survive at two
  observation scales. `< 0.7` means a semantic feature such as an arrow tip or
  heart notch was lost even if average outline coverage remains acceptable.
  Test a different placement/rotation before adding more guide points.
- **on_roads** (bool): `False` when ORS was unavailable and the route fell
  back to a straight-line connector. In that mode `shape_fidelity` is
  meaningless (~1.0, the drawing compared to itself), so the overall score is
  **capped at 0.4** — the route cannot pass the threshold and is flagged
  `below_threshold=true`. Verify `ORS_API_KEY` and provider reachability, then
  move, rotate, simplify, or shorten the guide if its points still cannot be
  connected.
- **Quality gates** control refinement and automatic verification independently: selected
  shape identity, road matching, score ≥ 0.72, combined fidelity ≥ 0.70,
  and each spatial, coverage, turning, landmark, length, and extent component
  ≥ 0.70. Distance fit must be ≥ 0.60; closure must be ≥ 0.60 for a
  closed shape. The loop continues while any applicable gate fails.
- **Candidate ordering:** normalise every numeric gate by its minimum, then
  rank the weakest gate first after partitioning gate-passing candidates ahead
  of failed candidates. This prevents an aggregate score or near-perfect
  distance from hiding a lost tip, turn, or silhouette, and prevents a higher
  average failure from outranking a route that passes every check.
- **Export rule:** passing every applicable gate enables an immediate
  automatic-check download only when `on_roads=true` / `snapped=true`. These
  thresholds are engineering heuristics, not scientific validation or a
  safety/access guarantee. A below-target road-routed selected-shape attempt
  remains visible and receives full GPX/TCX geometry, but the UI requires the
  user to inspect the evidence and explicitly accept that exact route first.
  An `on_roads=false` diagnostic is never an acceptance case: the API returns
  HTTP 503 and withholds route files.

When diagnosing, fix the **lowest** metric first — the overall score tracks it.
