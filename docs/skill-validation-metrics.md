---
name: validation-metrics
description: What each validation metric means and how to read a failing score.
applies_to: [validation, refinement, planning]
tags: [metrics, scoring]
---

# Reading validation metrics

The overall `score` is a weighted blend. Closed shapes: `0.5·fidelity + 0.3·distance_fit + 0.2·closure`. Open shapes: `0.6·fidelity + 0.4·distance_fit` (closure not applicable).

- **shape_fidelity** (0–1): how close the snapped route is to the *placed*
  drawing, via shared-frame Fréchet + Hausdorff distance. The dominant metric.
  - `< 0.7` → the shape is below the recommended recognisability target; correct any
    large distance error, then test rotation/offset or tighten simplification.
- **distance_fit** (0–1): how well total distance matches the target (or the
  sport's bounds when no target is given).
  - `< 0.6` and route too long → shrink scale; too short → grow scale.
- **closure** (0–1, closed shapes only): 1.0 minus the normalised gap between
  the first and last snapped points.
  - `< 0.6` → the loop didn't close; shrink scale slightly or nudge an offset
    away from a dead-end.
- **on_roads** (bool): `False` when ORS was unavailable and the route fell
  back to a straight-line connector. In that mode `shape_fidelity` is
  meaningless (~1.0, the drawing compared to itself), so the overall score is
  **capped at 0.4** — the route cannot pass the threshold and is flagged
  `below_threshold=true`. Fix by providing a valid `ORS_API_KEY`.
- **Quality gates** control the refinement loop: road matching, score ≥ 0.72,
  shape fidelity ≥ 0.70, distance fit ≥ 0.60, and closure ≥ 0.60 when
  applicable. The loop continues while any gate fails.
- **Candidate ordering:** normalise fidelity, distance fit, and closure by their
  recommended minima, then rank the weakest gate first. This prevents a near-perfect
  distance from hiding an unrecognisable shape and guides the search toward a
  balanced result.
- **Export warnings:** road matching, score ≥ 0.72, shape fidelity ≥ 0.70,
  distance fit ≥ 0.60, and closure ≥ 0.60 define the recommended state. Missing
  a target does not delete the candidate or its GPX.

When diagnosing, fix the **lowest** metric first — the overall score tracks it.
