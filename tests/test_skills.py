"""Tests for runtime skill discovery and prompt injection from docs/skills/."""

from __future__ import annotations

import shutil

from gps_art_wizzard.skills import for_agent, load_all, loader, system_prompt_for

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
    assert "Paceasso" in sp  # base system.txt content
    assert "Loaded skills" in sp
    assert "shape-design" in sp


def test_unknown_agent_gets_only_all_skills():
    block = for_agent("nonexistent-agent")
    assert "Skill: prompt-engineering" in block
    # shape-design applies_to [shape, planning] -> not included for unknown
    assert "Skill: shape-design" not in block


def test_installed_package_loads_runtime_skills_without_a_source_checkout(tmp_path, monkeypatch):
    installed = tmp_path / "share" / "paceasso" / "skills"
    shutil.copytree(loader.SKILLS_DIR, installed)
    monkeypatch.setattr(loader, "__file__", str(tmp_path / "lib/site-packages/gps_art_wizzard/skills/loader.py"))
    monkeypatch.setattr(loader.sys, "prefix", str(tmp_path))
    assert loader._default_skills_directory() == installed
    monkeypatch.setattr(loader, "SKILLS_DIR", loader._default_skills_directory())
    load_all.cache_clear()
    try:
        assert {skill.name for skill in load_all()} == _EXPECTED
        assert "Skill: shape-design" in system_prompt_for("shape")
    finally:
        load_all.cache_clear()
