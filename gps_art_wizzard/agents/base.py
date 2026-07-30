"""Base agent: the node interface every agent implements.

Agents are *pure transforms*: ``run(state) -> state`` (mutating in place is
fine and idiomatic here). This mirrors a LangGraph node so the orchestrator
can be swapped for one later without touching agents.
"""

from __future__ import annotations

import logging

from ..skills import system_prompt_for
from ..state import WorkflowState


class BaseAgent:
    name: str = "base"

    def run(self, state: WorkflowState) -> WorkflowState:  # pragma: no cover - interface
        raise NotImplementedError

    @property
    def log(self) -> logging.Logger:
        return logging.getLogger(f"gps_art_wizzard.agent.{self.name}")

    @property
    def system_prompt(self) -> str:
        """Base system prompt + the skills loaded for this agent from docs/."""
        return system_prompt_for(self.name)

    def _record(self, state: WorkflowState, note: str) -> None:
        self.log.info(note)
        state.history.append({"agent": self.name, "iteration": state.iterations, "note": note})
