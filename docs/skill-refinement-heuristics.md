---
name: refinement-heuristics
description: Concrete tweak recipes for lifting a failing validation score.
applies_to: [refinement]
tags: [refinement, heuristics, loops]
---

# Deterministic refinement recipes

Use measured route geometry, never an LLM's interpretation of numeric values.
Each new transform starts from the best-known draft so weak transformations do
not compound, while every measured candidate remains available to the user.

| Worst metric | Likely cause | Tweak |
|---|---|---|
| `shape_fidelity` low | wrong rotation, poor grid placement, or over-simplification | Test a bounded rotation/offset candidate and reduce `simplify_tolerance` |
| `distance_fit` low, route too long | road detour overhead | `scale_factor = target / actual` (bounded to `[0.35, 1.5]`) |
| `distance_fit` low, route too short | drawing is too small | `scale_factor = target / actual` (bounded to `[0.35, 1.5]`) |
| `closure` low (closed shape) | loop open over a park/river | Shrink slightly and test a nearby grid offset |

Rules:
- **Do not promote regression.** Keep the best measured candidate selected,
  retain weaker candidates for comparison/editing, and continue the remaining
  bounded variants.
- **Never repeat an already measured draft.** Record scale, rotation, offsets, and
  simplification tolerance for every measured candidate. Skip an identical
  signature on later passes.
- **Bracket non-linear distance response.** Test `target / actual` first. If
  that draft scores lower, test `sqrt(target / actual)` from the best-known
  draft before changing grid placement. Road distance can jump at bridges,
  motorways, and disconnected blocks; resubmitting the full ratio cannot find
  the transition.
- **Preserve promising alignment.** Once fidelity reaches roughly 0.45, a
  large distance correction changes scale only; it must not rotate away the
  best-known street-grid fit.
- **Explore distinct grids.** Alternate rotation signs and offsets so retries
  sample different nearby street topology. Prefer a pure neighbourhood shift
  before combining a shift with a large rotation.
- Use at most eight refinement passes: two scale brackets and six distinct
  grid/orientation candidates.
- After the configured iteration budget is exhausted, return the best
  candidate with `below_threshold=true`, preserve all alternatives, and export
  only with a clear recommended-target warning.
