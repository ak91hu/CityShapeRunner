---
name: prompt-engineering
description: How the agents must format LLM output. Applies to every agent.
applies_to: [all]
tags: [llm, json, discipline]
---

# Prompt engineering rules for this system

- Reply with **JSON only**. No markdown fences, no commentary, no apologies.
  If the schema has a field you cannot fill, emit `null` — never invent a value.
- Keys and value types must match the schema exactly. Booleans are `true`/`false`,
  numbers are bare (no units, no commas), strings are double-quoted.
- Never narrate your reasoning in the response. Put any reasoning in a short
  `"rationale"` string if the schema asks for one.
- If the user's request is ambiguous, pick the most reasonable default and
  proceed — do not ask a clarifying question. The pipeline must stay autonomous.
- Distances are always in **kilometres**. Sports are `"run"` or `"bike"` only.
- Coordinates are **[lat, lon]** in decimal degrees, or **[x, y]** in unit space
  — the prompt will say which. Never mix the two.
- Keep responses small. Emit 40–120 points for a shape, never hundreds.
