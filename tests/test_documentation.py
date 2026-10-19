"""Keep documentation organized and detect broken links before publication."""

import json

import pytest

from scripts.check_documentation import ROOT, check_documents, markdown_files, on_post_build


def test_repository_documentation_has_valid_locations_and_local_links():
    assert check_documents(ROOT, markdown_files(ROOT)) == []


def test_links_support_encoded_paths_references_and_html_but_skip_code_and_urls(tmp_path):
    guide = tmp_path / "docs/guides/start.md"
    guide.parent.mkdir(parents=True)
    (guide.parent / "my diagram.svg").write_text("<svg/>", encoding="utf-8")
    guide.write_text('''# Guide
[diagram](<my%20diagram.svg>)
![reference][diagram]
[diagram]: my%20diagram.svg
<img src="my%20diagram.svg">
[online](https://example.com/remote.md)
[section](#guide)
[health](/health)
```markdown
[example](does-not-exist.md)
```
''', encoding="utf-8")
    assert check_documents(tmp_path, [guide]) == []
    guide.write_text('[missing](lost.md)\n<img src="lost.svg">', encoding="utf-8")
    errors = check_documents(tmp_path, [guide])
    assert len(errors) == 2
    assert any("lost.md" in error for error in errors)
    assert any("lost.svg" in error for error in errors)


def test_scattered_markdown_is_rejected_but_native_tool_entry_points_are_allowed(tmp_path):
    paths = []
    for relative in ("README.md", "AGENTS.md", ".agents/skills/example/SKILL.md", "frontend/NOTES.md"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Notes\n", encoding="utf-8")
        paths.append(path)
    assert check_documents(tmp_path, paths) == [
        "frontend/NOTES.md: move documentation into a docs/ section"
    ]


def test_moved_published_pages_have_relative_redirects(tmp_path):
    docs, site = tmp_path / "docs", tmp_path / "site"
    docs.mkdir()
    moves = {"testing.md": "development/testing.md", "implementation/index.md": "architecture/index.md"}
    (docs / "page-redirects.json").write_text(json.dumps(moves), encoding="utf-8")
    for path in (site / "development/testing/index.html", site / "architecture/index.html"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<h1>Target</h1>", encoding="utf-8")
    on_post_build({"docs_dir": docs, "site_dir": site})
    assert 'href="../development/testing/index.html"' in (site / "testing/index.html").read_text(encoding="utf-8")
    assert 'href="../architecture/index.html"' in (site / "implementation/index.html").read_text(encoding="utf-8")


def test_redirects_cannot_write_outside_the_generated_site(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "page-redirects.json").write_text(json.dumps({"../../outside.md": "index.md"}), encoding="utf-8")
    with pytest.raises(ValueError, match="leaves the site directory"):
        on_post_build({"docs_dir": docs, "site_dir": tmp_path / "site"})
    assert not (tmp_path.parent / "outside").exists()
