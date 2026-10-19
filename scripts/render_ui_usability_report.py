"""Build a portable, evidence-backed UI comparison from retained browser audits."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import zipfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "test-results/ui-usability-2026-10-19"
OUTPUT = ROOT / "test-results/ui-hasznalhatosag-2026-10-19"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_records(suites, ancestry=()):
    for suite in suites:
        for spec in suite.get("specs", []):
            for test in spec["tests"]:
                last = test["results"][-1] if test["results"] else {}
                yield {
                    "file": spec["file"], "title": " / ".join((*ancestry, spec["title"])),
                    "project": test["projectName"], "outcome": test["status"],
                    "last_status": last.get("status"), "started_at": last.get("startTime", ""),
                    "errors": [error.get("message", "") for error in last.get("errors", [])],
                }
        yield from test_records(suite.get("suites", []), (*ancestry, suite["title"]))


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    before = read_json(EVIDENCE / "before/audit.json")
    after = read_json(EVIDENCE / "after-final/audit.json")
    # Refuse to associate screenshots with source that has since changed.
    for relative, expected in after["source_sha256"].items():
        if digest(ROOT / "frontend" / relative) != expected:
            raise SystemExit(f"Final audit is stale: {relative}")
    if len(before["views"]) != 18 or len(after["views"]) != 18:
        raise SystemExit("Both comparison audits must contain all 18 views")
    latest, runs = {}, []
    for path in sorted(EVIDENCE.glob("*.json")):
        report = read_json(path)
        if "config" not in report or "suites" not in report:
            continue
        records = list(test_records(report["suites"]))
        runs.append({"report": path.name, "stats": report["stats"]})
        for record in records:
            key = (record["file"], record["title"], record["project"])
            if key not in latest or record["started_at"] > latest[key]["started_at"]:
                latest[key] = {**record, "report": path.name}
    current = list(latest.values())
    unresolved = [r for r in current if r["outcome"] != "expected" or r["last_status"] != "passed"]
    if unresolved:
        raise SystemExit("Unresolved browser scenarios: " + json.dumps(unresolved, ensure_ascii=False))

    def metrics(audit):
        def action_position(view):
            return view["layout"].get("actionPosition") or next(
                c["top"] for c in view["layout"]["controls"] if c["label"].startswith("Review request")
            )

        return {
            "views": len(audit["views"]),
            "rule_observations": sum(len(v["violations"]) for v in audit["views"]),
            "node_observations": sum(len(rule["nodes"]) for v in audit["views"] for rule in v["violations"]),
            "rule_types": sorted({rule["id"] for v in audit["views"] for rule in v["violations"]}),
            "max_page_overflow_px": max(v["layout"]["overflow"] for v in audit["views"]),
            "incomplete_rule_observations": sum(len(v.get("incomplete", [])) for v in audit["views"]) if all("incomplete" in v for v in audit["views"]) else None,
            "review_button_document_top_px": {
                str(v["width"]): action_position(v)
                for v in audit["views"] if v["state"] == "planner"
            },
        }

    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "method": "Expert review, controlled browser fixtures, automated accessibility and layout checks, separate live API smoke checks. No participant study.",
        "before": metrics(before), "after": metrics(after),
        "source_sha256": after["source_sha256"],
        "baseline_provenance": "Retained original screenshots and raw audit; no complete frozen baseline source snapshot. This is a UI comparison, not a GPS accuracy benchmark.",
        "browser_validation": {
            "distinct_scenarios": len(current), "latest_outcomes": dict(Counter(r["outcome"] for r in current)),
            "by_project": dict(Counter(r["project"] for r in current)),
            "runs": sorted(runs, key=lambda r: r["stats"]["startTime"]), "latest_scenarios": current,
            "interpretation": "Initial full runs and subsequent targeted reruns are retained. Latest outcomes are matched by project, file and test title, never by changing line numbers. Not a single full-suite run on one final source snapshot.",
        },
        "live_api": {name: read_json(EVIDENCE / name / "smoke.json") for name in ("live-production", "live-development")},
        "limitations": ["No participant, screen reader or physical phone study", "Zero axe violations is not a WCAG certificate; incomplete checks require manual assessment", "Controlled UI fixtures do not measure GPS-art recognition, road accuracy or generation speed", "Layout pixel movement does not establish human time savings"],
    }
    OUTPUT.with_suffix(".json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    images = {}
    for phase, folder in (("before", "before"), ("after", "after-final")):
        for view in after["views"]:
            name = f'{view["width"]}-{view["state"]}'
            images[f"{phase}/{name}"] = "data:image/png;base64," + base64.b64encode((EVIDENCE / folder / f"{name}.png").read_bytes()).decode()

    project_rows = "".join(f"<tr><th>{html.escape(p)}</th><td>{n}</td></tr>" for p, n in sorted(summary["browser_validation"]["by_project"].items()))
    history_rows = "".join(f'<tr><td>{html.escape(r["report"])}</td><td>{r["stats"]["expected"]}</td><td>{r["stats"]["unexpected"]}</td></tr>' for r in summary["browser_validation"]["runs"])
    payload = json.dumps(images).replace("<", "\\u003c")
    page = """<!doctype html><html lang="hu"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Paceasso — használhatóság előtte és utána</title>
<style>body{margin:0;overflow-wrap:anywhere;background:#f3f1ea;color:#20382f;font:16px/1.6 system-ui}main{max-width:1160px;margin:auto;padding:24px}h1{font-size:clamp(1.8rem,5vw,3rem);line-height:1.15}h2{margin-top:2rem}p{max-width:85ch}a{color:#163f30}table{table-layout:fixed;border-collapse:collapse;width:100%;margin:1rem 0}th:first-child,td:first-child{width:50%}th,td{text-align:left;padding:10px;border-bottom:1px solid #a8b5a9}select{font:inherit;padding:10px;margin:4px;max-width:100%}.comparison{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}.comparison figure{margin:0;min-width:0;background:white;border:1px solid #a8b5a9}.comparison figcaption{padding:12px;font-weight:700}.comparison img{width:100%;height:auto;display:block}.note{border-left:4px solid #226047;padding:10px 16px;background:#e3eddf}.scroll{overflow-x:auto}.hashes{font:12px monospace;overflow-wrap:anywhere}summary{cursor:pointer;padding:12px}details{border:1px solid #a8b5a9;margin-top:16px;padding:8px}@media(max-width:640px){main{padding:16px}.comparison{grid-template-columns:1fr}th,td{padding:8px}}</style>
<main><p>Paceasso · 2026. október 19.</p><h1>Áttekinthetőbb tervezés mobilon és asztali gépen</h1>
<p>Szakértői feladatbejárás és mérhető böngészős ellenőrzés. A fő művelet közvetlenül a szövegmező után következik; a mobilos útvonalválasztás függőleges, a dialógusok kezelik a fókuszt és a háttér inaktivitását.</p>
<p class="note">Nem résztvevőkkel végzett kutatás. Az alábbi képek szabályozott API- és térképcsempe-válaszokkal készültek. A rajzok és a semleges térképháttér tesztadatok: ez a jelentés a kezelőfelületet vizsgálja. Az eredeti GPS-pontossági összehasonlítás külön bizonyítékcsomag.</p>
<h2>Pontos összehasonlítás</h2><p>Mindkét változatnál ugyanaz a 18 állapot-/méretkombináció: 1440, 390 és 320 CSS-pixel × hat állapot. Az ismétlődő nézetekben ugyanaz a hiba többször is szerepelhet.</p>
<table><thead><tr><th>Mért adat</th><th>Előtte</th><th>Utána</th></tr></thead><tbody>
<tr><th>Axe-szabálytípusok hibával</th><td>BEFORE_RULES</td><td>AFTER_RULES</td></tr>
<tr><th>Szabálysértés-megfigyelések</th><td>BEFORE_OBS</td><td>AFTER_OBS</td></tr>
<tr><th>Érintett elem-megfigyelések</th><td>BEFORE_NODES</td><td>AFTER_NODES</td></tr>
<tr><th>Legnagyobb oldalszintű vízszintes kilógás</th><td>28 px</td><td>0 px</td></tr>
<tr><th>Továbbgomb dokumentumpozíciója, 390 px</th><td>1218,6 px</td><td>930,5 px</td></tr>
<tr><th>Tab a szövegmezőtől a fő műveletig</th><td>Opcionális minták a gomb előtt</td><td>1 lépés</td></tr></tbody></table>
<p>A gomb helyzete elrendezési adat, nem mért emberi időnyereség. Az axe nem eldönthető eredményeit a nyers JSON megőrzi; a nulla automatikus hiba nem megfelelőségi tanúsítvány.</p>
<h2>Képernyők egymás mellett</h2><label>Szélesség <select id="width"><option>390</option><option>320</option><option>1440</option></select></label>
<label>Állapot <select id="state"><option value="planner">Ötlet megadása</option><option value="fields">Külön mezők</option><option value="review">Kérés ellenőrzése</option><option value="result">Útvonalak</option><option value="result-review">Felülvizsgálandó jelölt</option><option value="dialog">Jóváhagyó dialógus</option></select></label>
<div class="comparison"><figure><figcaption>Előtte</figcaption><img id="before" alt="Eredeti felület"></figure><figure><figcaption>Utána</figcaption><img id="after" alt="Javított felület"></figure></div>
<h2>Böngészős bizonyíték</h2><p>DISTINCT különböző teszteset legutóbbi eredménye sikeres. Az első teljes futások hibáit is megőrizzük, majd célzottan újrateszteljük az érintett folyamatokat. Ez több futás összevont eredménye, nem egyetlen teljes futás a végső forráson.</p>
<table><thead><tr><th>Motor és profil</th><th>Különböző esetek</th></tr></thead><tbody>PROJECT_ROWS</tbody></table>
<details><summary>Minden megőrzött futás, az első hibákkal együtt</summary><div class="scroll"><table><thead><tr><th>Nyers jelentés</th><th>Sikeres</th><th>Sikertelen</th></tr></thead><tbody>HISTORY_ROWS</tbody></table></div></details>
<p>További ellenőrzés: 14 egységteszt; termelési build; 320–1440 pixeles elrendezések, 200%-os gyökér-betűméret, billentyűzet, megszakítás, orientációváltás és galéria. Élő FastAPI- és Vite-próba: 145 sablon és kérésellenőrzés 1440/390 pixelen. Nem indult valódi útvonalgenerálás vagy közzététel.</p>
<h2>Értelmezési korlátok</h2><p>Nincs résztvevői feladatidő, SUS, NVDA-/VoiceOver-vizsgálat vagy fizikai telefonos próba. Az előtte állapot képei és auditja megmaradt, de nincs hozzá teljesen befagyasztott forrásmásolat. A végső auditot SHA-256 azonosítók kötik a jelenlegi UI-forráshoz. A vizsgálat nem bizonyít GPS-art-minőséget vagy generálási gyorsulást.</p>
<h2>Kutatási alap</h2><p><a href="https://www.nngroup.com/articles/ten-usability-heuristics/">NN/G: használhatósági heurisztikák</a> · <a href="https://www.nngroup.com/articles/progressive-disclosure/">Opcionális részletek fokozatos feltárása</a> · <a href="https://design-system.service.gov.uk/patterns/check-answers/">GOV.UK: kérés ellenőrzése</a> · <a href="https://www.w3.org/WAI/WCAG22/Understanding/reflow.html">W3C: reflow</a> · <a href="https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html">W3C: kontraszt</a> · <a href="https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/">WAI: modális dialógus</a>.</p>
<p>A teljes módszer, megállapításlista és reprodukálás: <code>docs/reports/2026-10-19-usability.md</code>. A ZIP a nyers adatokat, a kezdeti sikertelen futásokat, képeket és a vizsgált forrásokat is tartalmazza; a manifest minden csomagolt fájlhoz SHA-256 azonosítót rendel.</p>
<details><summary>Végső UI-forrás azonosítói</summary><div class="hashes">HASHES</div></details></main>
<script>const images=IMAGES;function update(){const key=document.getElementById('width').value+'-'+document.getElementById('state').value;for(const phase of ['before','after'])document.getElementById(phase).src=images[phase+'/'+key]}document.getElementById('width').addEventListener('change',update);document.getElementById('state').addEventListener('change',update);update();</script></html>"""
    replacements = {
        "BEFORE_RULES": len(summary["before"]["rule_types"]), "AFTER_RULES": len(summary["after"]["rule_types"]),
        "BEFORE_OBS": summary["before"]["rule_observations"], "AFTER_OBS": summary["after"]["rule_observations"],
        "BEFORE_NODES": summary["before"]["node_observations"], "AFTER_NODES": summary["after"]["node_observations"],
        "DISTINCT": len(current), "PROJECT_ROWS": project_rows, "HISTORY_ROWS": history_rows,
        "HASHES": "<br>".join(html.escape(f"{key}: {value}") for key, value in after["source_sha256"].items()),
        "IMAGES": payload,
    }
    for key, value in replacements.items():
        page = page.replace(key, str(value))
    OUTPUT.with_suffix(".html").write_text(page, encoding="utf-8")
    sources = [ROOT / "frontend" / p for p in after["source_sha256"]]
    sources += [ROOT / p for p in ("docs/reports/2026-10-19-usability.md", "docs/design/ui-design.md")]
    sources += [ROOT / "frontend" / p for p in ("package.json", "playwright.config.js", "playwright.cross-browser.config.js", "scripts/audit-usability.mjs", "scripts/smoke-usability.mjs")]
    sources += list((ROOT / "frontend/tests").rglob("*.js")) + list((ROOT / "frontend/unit").rglob("*.js"))
    sources += [Path(__file__)]
    evidence_files = [p for folder in ("before", "after-final", "live-production", "live-development") for p in (EVIDENCE / folder).rglob("*") if p.is_file()]
    evidence_files += list(EVIDENCE.glob("*.json"))
    files = sorted(set(sources + evidence_files + [OUTPUT.with_suffix(".json"), OUTPUT.with_suffix(".html")]))
    manifest = {p.relative_to(ROOT).as_posix(): digest(p) for p in files}
    with zipfile.ZipFile(OUTPUT.with_suffix(".zip"), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("manifest-sha256.json", json.dumps(manifest, indent=2))
    print(json.dumps({"before": summary["before"], "after": summary["after"], "distinct_scenarios": len(current), "zip_files": len(files), "html_bytes": OUTPUT.with_suffix(".html").stat().st_size}, ensure_ascii=False))


if __name__ == "__main__":
    main()
