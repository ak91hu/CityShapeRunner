"""Skills system: load ``docs/skill-*.md`` and inject into agent prompts."""

from .loader import Skill, for_agent, load_all, system_prompt_for

__all__ = ["Skill", "for_agent", "load_all", "system_prompt_for"]
