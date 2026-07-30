"""Prompt registry: load ``prompts/*.txt`` and substitute ``{vars}``.

Templates use ``{name}`` (optionally ``{name:spec}``) placeholders. Literal
braces — e.g. the JSON example blocks in the templates — are left untouched,
because a regex only substitutes tokens whose name matches a provided kwarg.
"""

from __future__ import annotations

import logging
import re
from functools import cache
from pathlib import Path

log = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).resolve().parent

_TOKEN = re.compile(r"\{([a-zA-Z_]\w*)(?::([^}]*))?\}")


@cache
def get(name: str) -> str:
    """Return the raw template text for ``name`` (without extension)."""
    path = PROMPT_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def render(name: str, **kwargs: object) -> str:
    """Return the template for ``name`` with known ``{name}`` tokens substituted.

    Only tokens whose name is in ``kwargs`` are replaced; everything else
    (including literal JSON braces) is preserved verbatim.
    """

    def repl(m: re.Match) -> str:
        key, spec = m.group(1), m.group(2)
        if key not in kwargs:
            return m.group(0)  # leave unknown tokens intact
        value = kwargs[key]
        try:
            return format(value, spec) if spec else str(value)
        except (ValueError, TypeError):
            return str(value)

    return _TOKEN.sub(repl, get(name))
