---
name: planning
description: How the PlanningAgent chooses a strategy before any drawing happens.
applies_to: [planning]
tags: [planning, strategy]
---

# Planning a GPS-art route

The plan runs once, after Intent and before Shape. It commits a strategy so the
downstream agents don't each guess independently. The planner receives known
map context plus a coarse city-extent heading and uses them to decide **where**
in the city to place the shape and **how** to rotate it.

Decide:
- **shape_strategy**: `template` (a known shape exists), `text` (the user asked
  for letters/words), or `llm` (draw freely). Prefer template/text — they are
  reliable; reserve `llm` for shapes no template matches.
- **difficulty**: `easy` (closed icon on a grid city), `medium` (text, or
  complex silhouette), `hard` (free drawing on an old-core city). This is a
  hint to the user/UI, not a control.
- **rotation_hint_deg**: align to a local street grid only when the map context
  supports that orientation. `city_extent_heading` comes from the city
  bounding box and is a low-confidence geometric fallback, not a measured
  street-grid bearing. Adjust it for the chosen area; leave `null` when there
  is no defensible orientation.
- **scale_hint**: optional multiplier on the target distance. Use ~1.0; only
  deviate to pre-correct known overshoot (road following adds ~25-40%).
- **lat_offset_m / lon_offset_m**: offset the shape centre from the city centre
  to position it in the best neighbourhood for road following. Use the map
  context to choose a dense grid area away from water/parks. Typical range:
  -3000 to +3000 metres. 0/0 = city centre (often not ideal).
- **placement_hints**: one short sentence of freeform advice (e.g. "shift east
  if the west side hits the river"). Read by RefinementAgent if it needs to nudge.

Map-aware heuristics:
- Budapest → offset east (+lon) to the Pest grid, rotation ~0 or ~90.
- Paris → offset to central arrondissements, rotation ~30.
- Berlin → offset to Mitte/Prenzlauer Berg, rotation ~30.
- New York → offset to Midtown, rotation ~30 (Broadway diagonal).
- Barcelona → L'Eixample grid, rotation ~0 — excellent for clean shapes.
- Keszthely → offset NORTH (away from Lake Balaton), keep shapes compact.

Emit the plan as strict JSON per the prompt schema. Never block; always commit
a best-guess plan.
