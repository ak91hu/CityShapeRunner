"""Skills: markdown capability docs in ``docs/skill-*.md`` loaded into prompts.

Each skill file has YAML frontmatter (``name``, ``description``,
``applies_to``, ``tags``) and a markdown body. At runtime an agent asks for
the skills that apply to it, and they are appended to its system prompt — so
the documentation in ``docs/`` is actively used during prompt construction.

All markdown lives in the single ``docs/`` folder (see the project README);
this module is the bridge from that folder into the prompt system.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "docs"

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    applies_to: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body: str = ""
    path: str = ""

    def applies_to_agent(self, agent: str) -> bool:
        return agent in self.applies_to or "all" in self.applies_to


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, m.group(2).strip()


@lru_cache(maxsize=1)
def load_all() -> tuple[Skill, ...]:
    """Load every ``docs/skill-*.md`` file, sorted by name for stable order."""
    if not DOCS_DIR.exists():
        return ()
    skills: list[Skill] = []
    for p in sorted(DOCS_DIR.glob("skill-*.md")):
        meta, body = _split_frontmatter(p.read_text(encoding="utf-8"))
        skills.append(
            Skill(
                name=str(meta.get("name", p.stem)),
                description=str(meta.get("description", "")),
                applies_to=list(meta.get("applies_to", []) or []),
                tags=list(meta.get("tags", []) or []),
                body=body,
                path=str(p),
            )
        )
    return tuple(skills)


def for_agent(agent: str) -> str:
    """Concatenated body of every skill that applies to ``agent``."""
    relevant = [s for s in load_all() if s.applies_to_agent(agent)]
    if not relevant:
        return ""
    blocks = [f"## Skill: {s.name}\n{s.description}\n\n{s.body}" for s in relevant]
    return "\n\n---\n\n".join(blocks)


def system_prompt_for(agent: str) -> str:
    """The base system prompt augmented with the agent's loaded skills."""
    from ..prompts import get

    base = get("system")
    skills = for_agent(agent)
    if not skills:
        return base
    return f"{base}\n\n# Loaded skills (from docs/)\n\n{skills}"
