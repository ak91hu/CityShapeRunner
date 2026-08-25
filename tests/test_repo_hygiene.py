"""Repository hygiene guards.

Ad-hoc pytest runs with custom ``--basetemp`` values historically littered the
repo root with scratch directories (see docs/2026-07-30-lessons-learned.md).
The junk was removed once; these tests keep it from coming back unnoticed:

1. legacy scratch directory names must not reappear at the repo root;
2. ``.gitignore`` must keep covering every scratch pattern such runs generate.
"""

from __future__ import annotations

from gps_art_wizzard.config import ROOT

# Historical accident names, deleted once already. If one of these shows up
# again, an ad-hoc run recreated it - delete it instead of extending this list.
LEGACY_SCRATCH_DIRS = (
    ".codex-test-temp",
    ".pytest-commit-20260813",
    ".pytest-full-image-reference",
    ".pytest-full-timed-readiness",
    ".pytest-prompt-precision-final-20260813",
    ".pytest-status-audit",
    ".pytest-status-final",
    ".pytest-tmp-ai-final-full",
    ".pytest-tmp-ai-full",
    ".pytest-tmp-hungarian-final-20260811",
    ".pytest-tmp-hungarian-shapes-20260811",
    ".pytest-tmp-niche-20260812",
    ".pytest-ui-fix-20260813",
    ".pytest-ui-fix-final-20260813",
    ".pytest-word-semantics-final-20260813",
    ".tmp-test",
    ".tmp-verify",
    "pytest-tmp-city-shape",
    "pytest-tmp-city-shape-2",
)

# Dirs locked by a zombie process handle during the original cleanup; they are
# empty (or emptied) and must be removed manually once the handle is released.
KNOWN_LOCKED_LEFTOVERS = frozenset({
    ".pytest-commit-20260813",
    ".pytest-status-audit",
    ".pytest-status-final",
})


def test_legacy_scratch_directories_do_not_reappear():
    survivors = [
        name
        for name in LEGACY_SCRATCH_DIRS
        if (ROOT / name).exists() and name not in KNOWN_LOCKED_LEFTOVERS
    ]
    assert survivors == [], (
        f"scratch directories reappeared in the repo root: {survivors}; "
        "delete them and add their pattern to .gitignore"
    )


def test_gitignore_covers_every_scratch_pattern():
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    for pattern in (
        ".pytest-*/",  # suffixed --basetemp dirs incl. .pytest-tmp/
        ".tmp*/",  # .tmp/ and .tmp-test/-style scratch
        "pytest-tmp*/",  # non-dot variants
        ".codex-test-temp/",
    ):
        assert pattern in gitignore, f".gitignore no longer covers {pattern}"


def test_pinned_basetemp_stays_inside_the_ignored_scratch_set():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '--basetemp=.pytest-tmp"' in pyproject, (
        "pyproject addopts must keep the default basetemp under .pytest-tmp/"
    )


def test_northflank_cd_default_matches_combined_service_response():
    """Enabled CD is omitted by the service API and must remain deployable."""

    helper = (ROOT / ".github/scripts/deploy-northflank.sh").read_text(
        encoding="utf-8"
    )
    assert ".data.disabledCD // false" in helper
    assert ".data.disabledCD // true" not in helper
