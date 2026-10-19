"""Check maintained Markdown locations and local file links without network access."""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOC_SECTIONS = frozenset({
    "guides", "architecture", "reference", "development", "operations",
    "design", "research", "reports", "skills",
})
ENTRY_POINTS = {"README.md", "AGENTS.md", ".github/pull_request_template.md", "docs/index.md"}
FENCES = re.compile(r"(?ms)^ {0,3}(`{3,}|~{3,})[^\n]*\n.*?^ {0,3}\1[ \t]*(?:\n|$)")
LINKS = re.compile(r"\[[^\]]*\]\(\s*(<[^>]+>|[^()\s]+)")
REFERENCES = re.compile(r"(?m)^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)")
HTML_LINKS = re.compile(r"\b(?:src|href)\s*=\s*[\"']([^\"']+)[\"']")


def markdown_files(root: Path) -> list[Path]:
    output = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
    )
    return sorted({root / name for name in output.decode("utf-8").split("\0")
                   if name.endswith(".md") and (root / name).is_file()})


def check_documents(root: Path, paths: list[Path]) -> list[str]:
    errors = []
    for path in paths:
        relative = path.relative_to(root)
        parts = relative.parts
        native_skill = len(parts) == 4 and parts[:2] == (".agents", "skills") and parts[-1] == "SKILL.md"
        organized = len(parts) >= 3 and parts[0] == "docs" and parts[1] in DOC_SECTIONS
        if relative.as_posix() not in ENTRY_POINTS and not native_skill and not organized:
            errors.append(f"{relative.as_posix()}: move documentation into a docs/ section")
        content = FENCES.sub("", path.read_text(encoding="utf-8"))
        for pattern in (LINKS, REFERENCES, HTML_LINKS):
            for match in pattern.finditer(content):
                target = match[1].strip("<>")
                parsed = urlsplit(target)
                # Absolute web routes and anchors are not repository file links.
                if parsed.scheme or parsed.netloc or not parsed.path or parsed.path.startswith("/"):
                    continue
                destination = (path.parent / unquote(parsed.path)).resolve()
                if not destination.is_relative_to(root) or not destination.exists():
                    errors.append(f"{relative.as_posix()}: missing local link {target}")
    return errors


def main() -> None:
    paths = markdown_files(ROOT)
    errors = check_documents(ROOT, paths)
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Documentation layout and local file links verified: {len(paths)} Markdown files")


def on_post_build(config) -> None:
    """Preserve the published MkDocs URLs of relocated documentation."""
    docs = Path(config["docs_dir"]).resolve()
    site = Path(config["site_dir"]).resolve()
    moves = json.loads((docs / "page-redirects.json").read_text(encoding="utf-8"))

    def output(path: str) -> Path:
        page = Path(path)
        return page.with_suffix(".html") if page.name == "index.md" else page.with_suffix("") / "index.html"

    for old, new in moves.items():
        source = (site / output(old)).resolve()
        target = (site / output(new)).resolve()
        if not source.is_relative_to(site) or not target.is_relative_to(site):
            raise ValueError(f"Documentation redirect leaves the site directory: {old}")
        if source.exists() or not target.is_file():
            raise ValueError(f"Documentation redirect collides or has no target: {old} -> {new}")
        href = os.path.relpath(target, source.parent).replace("\\", "/")
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><title>Page moved</title>'
            f'<link rel="canonical" href="{html.escape(href, quote=True)}">'
            f'<meta http-equiv="refresh" content="0;url={html.escape(href, quote=True)}">'
            f'<a href="{html.escape(href, quote=True)}">Continue to the documentation</a>'
            f'<script>location.replace({json.dumps(href)}+location.search+location.hash)</script></html>',
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
