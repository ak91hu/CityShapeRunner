"""Node graph: instantiate the agents that form the pipeline.

This is intentionally a thin registry so the graph structure is visible in one
place. The orchestrator owns the edges (linear pipeline + refinement loop);
agents themselves stay edge-unaware.
"""

from __future__ import annotations

from .agents import (
    ExportAgent,
    IntentAgent,
    PlacementAgent,
    PlanningAgent,
    PreflightAgent,
    RefinementAgent,
    ShapeAgent,
    SnapAgent,
    ValidationAgent,
)
from .agents.base import BaseAgent


def build_nodes() -> dict[str, BaseAgent]:
    return {
        "intent": IntentAgent(),
        "planning": PlanningAgent(),
        "shape": ShapeAgent(),
        "placement": PlacementAgent(),
        "preflight": PreflightAgent(),
        "snap": SnapAgent(),
        "validation": ValidationAgent(),
        "refinement": RefinementAgent(),
        "export": ExportAgent(),
    }


# Ordered list of the linear (non-loop) nodes.
LINEAR_ORDER = [
    "intent",
    "planning",
    "shape",
    "placement",
    "preflight",
    "snap",
    "validation",
]
