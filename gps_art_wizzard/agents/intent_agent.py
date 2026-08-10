"""IntentAgent: turn the user's natural-language prompt into a structured Intent."""

from __future__ import annotations

import json
import math
import re

from ..config import get_settings
from ..llm import LLMResponse, extract_json, try_complete
from ..prompts import render
from ..state import Intent, WorkflowState
from ..tools.geocoder import MAJOR_EUROPEAN_CITIES, MAJOR_HUNGARIAN_CITIES
from .base import BaseAgent

_KNOWN_CITIES = [
    *MAJOR_HUNGARIAN_CITIES,
    *MAJOR_EUROPEAN_CITIES,
    "Keszthely", "Balatonfüred", "Visegrád", "Makó", "New York",
]


class IntentAgent(BaseAgent):
    name = "intent"

    def run(self, state: WorkflowState) -> WorkflowState:
        fallback = self._fallback(state.prompt)
        fallback_intent = self._parse(fallback.text)
        if self._is_complete_fallback(fallback_intent):
            # Common template/text requests are fully structured by local
            # rules. Avoiding a remote LLM call makes route generation faster
            # and removes nondeterministic numeric interpretation.
            intent = fallback_intent
        else:
            user = render("intent", prompt=state.prompt)
            resp = try_complete(
                lambda: fallback,
                messages=[{"role": "user", "content": user}],
                system=self.system_prompt,
                json_mode=True,
                temperature=0.1,
            )
            intent = self._parse(resp.text)
        state.intent = intent
        self._record(state, f"intent={intent}")
        return state

    @staticmethod
    def _is_complete_fallback(intent: Intent) -> bool:
        """Whether local parsing captured enough fields to skip an LLM."""
        return bool(
            intent.city
            and (intent.shape or intent.text or intent.suggest)
        )

    # -- parsing ------------------------------------------------------------- #
    def _parse(self, text: str) -> Intent:
        try:
            data = extract_json(text)
        except Exception:  # noqa: BLE001
            data = {}
        data = data if isinstance(data, dict) else {}
        sport = str(data.get("sport") or "run").lower()
        if sport not in ("run", "bike"):
            sport = "run"
        dist = data.get("distance_km")
        try:
            dist = float(dist) if dist is not None else None
        except (TypeError, ValueError):
            dist = None
        if dist is not None:
            if not math.isfinite(dist) or dist <= 0:
                dist = None
            else:
                lower, upper = get_settings().workflow.distance_bounds.get(sport, [3, 60])
                dist = min(float(upper), max(float(lower), dist))
        suggest = _parse_bool(data.get("suggest", False))
        shape = _clean_optional_text(data.get("shape"), max_length=80)
        # If suggesting, force shape to None — PlanningAgent will pick one.
        if suggest:
            shape = None
        return Intent(
            shape=shape,
            text=_clean_optional_text(data.get("text"), max_length=20),
            city=_clean_optional_text(data.get("city"), max_length=100),
            sport=sport,
            distance_km=dist,
            style=_clean_optional_text(data.get("style"), max_length=80),
            suggest=suggest,
        )

    # -- deterministic fallback --------------------------------------------- #
    def _fallback(self, text: str) -> LLMResponse:
        cfg = get_settings().workflow
        low = text.lower()

        sport = "bike" if any(w in low for w in ("bike", "cycle", "cycling", "bici")) else (
            "run" if any(w in low for w in ("run", "jog", "marathon")) else cfg.sport_default
        )
        dist_match = re.search(r"(\d+(?:\.\d+)?)\s*km", low)
        dist = float(dist_match.group(1)) if dist_match else None
        city = next((c for c in _KNOWN_CITIES if c.lower() in low), None)

        # Detect suggestion requests.
        suggest = any(w in low for w in (
            "suggest", "surprise", "recommend", "what should", "pick", "choose",
            "idea", "inspire", "any ",
        ))

        text_match = re.search(
            r"""\b(?:write|spell)\s+(?:the\s+(?:word|text)\s+)?["']?
                ([A-Za-z0-9 !?-]{1,20}?)
                (?=["']?(?:\s+(?:in|near|around|for|about)\b|$)|[,.;])""",
            text,
            flags=re.IGNORECASE | re.VERBOSE,
        )
        labelled_glyph_match = re.search(
            r"""\b(?:letter|number|digits?)\s+["']?
                ([A-Za-z0-9]{1,6})
                (?=["']?(?:\s+(?:in|near|around|for|about|while)\b|$)|[,.;])""",
            text,
            flags=re.IGNORECASE | re.VERBOSE,
        )
        drawn_text = (
            text_match.group(1).strip()
            if text_match
            else (
                labelled_glyph_match.group(1).strip()
                if labelled_glyph_match
                else None
            )
        )
        shape = None
        if not suggest:
            from ..tools import shape_library
            hit = shape_library.find_by_keyword(low)
            if hit:
                shape = hit[0]
            elif drawn_text:
                shape = "text"
        payload = {
            "shape": shape, "text": drawn_text, "city": city,
            "sport": sport, "distance_km": dist, "style": None, "suggest": suggest,
        }
        return LLMResponse(text=json.dumps(payload), provider="fallback", model="rules")


def _clean_optional_text(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()).strip()
    return cleaned[:max_length] or None


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    if isinstance(value, int | float):
        return value == 1
    return False
