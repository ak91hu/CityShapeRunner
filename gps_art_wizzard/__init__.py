"""GPS Art Wizard — AI-powered GPS art route planner.

Turn a natural-language prompt ("a dragon running through Budapest, ~30km")
into an evaluated route candidate. Road-matched candidates that meet the
minimum shape-fidelity requirement can be exported as GPX/TCX.

The system is built around a multi-agent workflow:

    Intent -> Shape -> Placement -> Snap-to-Road -> Validation
                       ^                                  |
                       |______ Refinement loop <__________|
                                                                -> Export

See :mod:`gps_art_wizzard.orchestrator` for the graph/loop engine.
"""

__version__ = "0.1.0"
