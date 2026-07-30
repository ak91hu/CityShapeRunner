"""Tests for the skills loader: docs/skill-*.md are discovered and injected."""

from __future__ import annotations

from gps_art_wizzard.skills import for_agent, load_all, system_prompt_for

_EXPECTED = {
    "prompt-engineering",
    "planning",
    "shape-design",
    "route-placement",
    "snap-and-roads",
    "validation-metrics",
    "refinement-heuristics",
}


def test_all_skills_loaded():
    names = {s.name for s in load_all()}
    assert _EXPECTED <= names, f"missing skills: {_EXPECTED - names}"


def test_applies_to_routing():
    shape_block = for_agent("shape")
    assert "Skill: shape-design" in shape_block
    assert "Skill: refinement-heuristics" not in shape_block  # not for shape
    refine_block = for_agent("refinement")
    assert "Skill: refinement-heuristics" in refine_block
    # shape-design applies_to [shape, planning] -> not included for refinement
    assert "Skill: shape-design" not in refine_block


def test_all_skill_applies_everywhere():
    # prompt-engineering has applies_to: [all] -> present for every agent.
    for agent in ["intent", "planning", "shape", "placement", "snap",
                  "validation", "refinement", "export"]:
        assert "Skill: prompt-engineering" in for_agent(agent), agent


def test_system_prompt_for_includes_base_and_skills():
    sp = system_prompt_for("shape")
    assert "GPS Art Wizard" in sp  # base system.txt content
    assert "Loaded skills" in sp
    assert "shape-design" in sp


def test_unknown_agent_gets_only_all_skills():
    block = for_agent("nonexistent-agent")
    assert "Skill: prompt-engineering" in block
    # shape-design applies_to [shape, planning] -> not included for unknown
    assert "Skill: shape-design" not in block
