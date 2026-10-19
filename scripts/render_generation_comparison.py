"""Render paired live-generation results, including regressions and failures.

PNG/HTML rendering uses the analysis-only matplotlib package.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gps_art_wizzard.quality import route_quality_rank  # noqa: E402
from gps_art_wizzard.state import Validation  # noqa: E402
from gps_art_wizzard.tools import geo, shape_similarity  # noqa: E402

METRICS = {
    "shape_fidelity": "Alakhűség", "spatial_similarity": "Térbeli egyezés",
    "coverage_similarity": "Körvonal-lefedés", "turning_similarity": "Jellegzetes kanyarok",
    "landmark_similarity": "Csúcsok és bemélyedések", "reversal_similarity": "Visszafordulások",
    "length_similarity": "Kerülők / nyúlás", "extent_similarity": "Arányok",
}
SHAPES = {"heart": "Szív", "star": "Csillag", "triangle": "Háromszög", "circle": "Kör"}


def to_xy(points, origin):
    arr = np.asarray(points, dtype=float)
    return np.column_stack((np.radians(arr[:, 1] - origin[1]) * geo.EARTH_R_M * math.cos(math.radians(origin[0])),
                            np.radians(arr[:, 0] - origin[0]) * geo.EARTH_R_M))


def center(points):
    arr = np.asarray(points)
    return tuple((arr.max(axis=0) + arr.min(axis=0)) / 2)


def line_error_m(ideal, points):
    """Symmetric RMS distance to full polylines, 512 arc-length samples each."""
    origin = center(ideal)
    first, second = LineString(to_xy(ideal, origin)), LineString(to_xy(points, origin))
    distances = [first.interpolate(t, normalized=True).distance(second) for t in np.linspace(0, 1, 512)]
    distances += [second.interpolate(t, normalized=True).distance(first) for t in np.linspace(0, 1, 512)]
    return float(np.sqrt(np.mean(np.square(distances))))


def measurement(row):
    v = row.get("validation") or {}
    connected = bool(row.get("road_connected") and row.get("provider_geometry_preserved"))
    result = {"connected": connected, "elapsed_seconds": row["elapsed_seconds"],
              "shape_fidelity": v.get("shape_fidelity") if connected else None,
              "actual_distance_km": v.get("actual_distance_km") if connected else None,
              "quality_passed": connected and bool(row.get("quality", {}).get("passed")),
              "failed_gates": row.get("quality", {}).get("failed_gates", []),
              "routing_failures": row.get("workflow", {}).get("routing_failures", {}),
              "degraded_reasons": row.get("workflow", {}).get("degraded_reasons", []),
              "directions_requests": row.get("actual_directions_requests", row.get("workflow", {}).get("routing_requests", {}).get("directions", 0)),
              "candidate_count": row.get("candidate_count", 0),
              "gpx_vertex_count_preserved": row.get("gpx_vertex_count_preserved"),
              "gpx_max_error_m": row.get("gpx_max_error_m"),
              "quota_wait_union_seconds": row.get("quota_wait_union_seconds", 0.0),
              "components": {key: v.get(key) for key in METRICS}}
    if connected:
        result["distance_error_pct"] = abs(v["actual_distance_km"] - row["case"]["distance_km"]) / row["case"]["distance_km"] * 100
        result["outline_rms_error_m"] = line_error_m(row["ideal_points"], row["points"])
        xy = to_xy(row["ideal_points"], center(row["ideal_points"]))
        result["reference_extent_m"] = float(np.ptp(xy, axis=0).max())
        result["outline_rms_normalized_pct"] = result["outline_rms_error_m"] / result["reference_extent_m"] * 100
        common = shape_similarity.similarity_diagnostics_between_routes(row["ideal_points"], row["points"])
        result["common_score_matches_native"] = common.fidelity == v["shape_fidelity"]
        if {"score", "closure", "distance_fit", "shape_fidelity"} <= v.keys():
            result["app_quality_rank"] = list(route_quality_rank(Validation(**v)))
    return result


def compare_pair(case, before, after):
    a, b = measurement(before), measurement(after)
    comparable = a["connected"] and b["connected"]
    engine_equal = before.get("ors_engines") == after.get("ors_engines") and bool(before.get("ors_engines"))
    clean = bool(comparable and engine_equal and not a["routing_failures"] and not b["routing_failures"]
                 and a.get("common_score_matches_native") and b.get("common_score_matches_native")
                 and not before.get("execution_error") and not after.get("execution_error"))
    pair = {"case": case, "original": a, "current": b, "engine_revisions_equal": engine_equal,
            "both_connected": comparable, "clean_comparison": clean}
    if comparable:
        pair["fidelity_delta_pp"] = (b["shape_fidelity"] - a["shape_fidelity"]) * 100
        pair["distance_error_delta_pp"] = b["distance_error_pct"] - a["distance_error_pct"]
        pair["outline_rms_delta_m"] = b["outline_rms_error_m"] - a["outline_rms_error_m"]
        pair["placement_shift_m"] = geo.haversine(*center(before["ideal_points"]), *center(after["ideal_points"]))
    pair["time_delta_seconds"] = b["elapsed_seconds"] - a["elapsed_seconds"]
    if a.get("app_quality_rank") is not None and b.get("app_quality_rank") is not None:
        pair["app_rank_change"] = ((b["app_quality_rank"] > a["app_quality_rank"])
                                   - (b["app_quality_rank"] < a["app_quality_rank"]))
    return pair


def road_lines(snapshot):
    elements = json.loads(snapshot.read_text(encoding="utf-8"))["elements"]
    nodes = {item["id"]: (item["lat"], item["lon"]) for item in elements if item.get("type") == "node"}
    return [[nodes[n] for n in item.get("nodes", []) if n in nodes] for item in elements
            if item.get("type") == "way" and item.get("tags", {}).get("highway")]


def plot_pair(before, after, roads, path):
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["path.simplify"] = False
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection

    fig, axes = plt.subplots(1, 2, figsize=(13, 6), constrained_layout=True)
    plotted = []
    for row in (before, after):
        if not row.get("points"):
            plotted.append(None)
            continue
        origin = center(row["ideal_points"])
        plotted.append((origin, to_xy(row["ideal_points"], origin), to_xy(row["points"], origin)))
    limit = max((float(np.abs(np.vstack((item[1], item[2]))).max()) for item in plotted if item), default=1000) * 1.12
    for ax, row, points, color, title in zip(axes, (before, after), plotted,
                                           ("#b55a20", "#147958"), ("Eredeti", "Új"), strict=True):
        if points:
            origin, ideal, actual = points
            streets = [to_xy(line, origin) for line in roads if len(line) >= 2]
            ax.add_collection(LineCollection(streets, colors="#c9cdd0", linewidths=0.45, zorder=0))
            ax.plot(ideal[:, 0], ideal[:, 1], color="#222222", linestyle="--", linewidth=1.3, label="Célalakzat", zorder=3)
            ax.plot(actual[:, 0], actual[:, 1], color=color, linewidth=2.2, label="ORS-útvonal", zorder=2)
            v = row["validation"]
            ax.set_title(f"{title} · alakhűség {v['shape_fidelity'] * 100:.2f}%\n{v['actual_distance_km']:.3f} km · {row['elapsed_seconds']:.2f} s")
            ax.legend(loc="lower left", fontsize=8)
        else:
            ax.set_title(title)
            ax.text(0.5, 0.5, "Nem készült összefüggő utcai útvonal", ha="center", transform=ax.transAxes)
        ax.set_xlim(-limit, limit)
        ax.set_ylim(-limit, limit)
        ax.set_aspect("equal")
        ax.set_xlabel("Kelet–nyugat [m]")
        ax.set_ylabel("Észak–dél [m]")
        ax.grid(alpha=0.15)
    fig.suptitle("Azonos méretarány és északi irány; a panelek középpontja a saját célalakzat közepe", fontsize=10)
    fig.supxlabel("Utcák: © OpenStreetMap contributors · Útvonalak: openrouteservice / HeiGIT", fontsize=8)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def text_num(value, digits=2):
    return "—" if value is None else f"{value:.{digits}f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    folder = args.folder.resolve()
    data = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    for row in data["records"]:
        evidence_path = folder / f"{row['case']['id']}-{row['variant']}.http.json"
        if evidence_path.exists():
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            row["actual_directions_requests"] = sum("/directions/" in item["endpoint"] for item in evidence)
            row["actual_snap_requests"] = sum("/snap/" in item["endpoint"] for item in evidence)
    indexed = {(row["case"]["id"], row["variant"]): row for row in data["records"]}
    roads = road_lines(folder / "osm-snapshot.json")
    pairs, cards, table = [], [], []
    for case in data["manifest"]["cases"]:
        before, after = indexed.get((case["id"], "original")), indexed.get((case["id"], "current"))
        if before is None or after is None:
            if args.allow_partial:
                continue
            raise ValueError(f"Missing paired run: {case['id']}")
        pair = compare_pair(case, before, after)
        a, b, clean = pair["original"], pair["current"], pair["clean_comparison"]
        pairs.append(pair)
        label = f"{SHAPES.get(case['shape'], case['shape'])} · {case['distance_km']} km · {'futás' if case['sport'] == 'run' else 'kerékpár'}"
        fidelity = " → ".join(text_num(x["shape_fidelity"] * 100 if x["shape_fidelity"] is not None else None) for x in (a, b))
        error = " → ".join(text_num(x.get("distance_error_pct")) for x in (a, b))
        elapsed = " → ".join(text_num(x["elapsed_seconds"]) for x in (a, b))
        passed = " → ".join("igen" if x["quality_passed"] else "nem" for x in (a, b))
        label_note = "" if clean else "<br><small>API/összevetési hiba: nem döntő mérés</small>"
        table.append(f"<tr><th>{html.escape(label)}{label_note}</th><td>{fidelity}</td><td>{error}</td><td>{elapsed}</td><td>{passed}</td></tr>")
        image_path = folder / f"{case['id']}-comparison.png"
        plot_pair(before, after, roads, image_path)
        image_data = base64.b64encode(image_path.read_bytes()).decode()
        components = "".join(f"<tr><th>{title}</th><td>{text_num(a['components'].get(key) * 100 if a['components'].get(key) is not None else None, 4)}</td><td>{text_num(b['components'].get(key) * 100 if b['components'].get(key) is not None else None, 4)}</td></tr>" for key, title in METRICS.items())
        details = []
        for name, row in (("Eredeti", a), ("Új", b)):
            details.append(f"<p><b>{name}</b> · körvonal RMS-eltérés a saját célalakzathoz: {text_num(row.get('outline_rms_error_m'), 3)} m "
                           f"({text_num(row.get('outline_rms_normalized_pct'), 3)}% a saját célalakzat legnagyobb kiterjedéséhez mérve) · "
                           f"Directions-kérések: {row['directions_requests']} · útvonaljelölt-próbák: {row['candidate_count']}<br>"
                           f"Kvótára várakozást tartalmazó falióraidő: {text_num(row['quota_wait_union_seconds'])} s "
                           "(párhuzamos várakozások uniója; a teljes időből nem vonjuk le)<br>"
                           f"Sikertelen ellenőrzések: {html.escape(', '.join(row['failed_gates']) or 'nincs')}<br>"
                           f"API-hibák: {html.escape(json.dumps(row['routing_failures']))} · "
                           f"Keret/fallback jelzések: {html.escape(', '.join(row['degraded_reasons']) or 'nincs')}</p>")
        location = f"<p>A célalakzat középpontjának eltolódása: <b>{text_num(pair.get('placement_shift_m'))} m</b>.</p>" if pair["both_connected"] else ""
        if "app_rank_change" in pair:
            rank_text = {-1: "az eredeti útvonal az erősebb", 0: "azonos rang", 1: "az új útvonal az erősebb"}[pair["app_rank_change"]]
            location += f"<p>Az alkalmazás saját, változatlan minőségi rangsora szerint: <b>{rank_text}</b>.</p>"
        cards.append(f"<section><h2>{html.escape(label)}</h2>{location}<img alt='Eredeti és új utcai útvonal, a célalakzattal' src='data:image/png;base64,{image_data}'>"
                     + "".join(details) + f"<details><summary>Minden alakhűségi részmutató (0–100)</summary><table><thead><tr><th>Mutató</th><th>Eredeti</th><th>Új</th></tr></thead><tbody>{components}</tbody></table></details></section>")
    valid = [pair for pair in pairs if pair["clean_comparison"]]
    summary = {
        "paired_cases": len(pairs), "both_connected": sum(p["both_connected"] for p in pairs),
        "clean_comparisons": len(valid),
        "original_quality_passes": sum(p["original"]["quality_passed"] for p in pairs),
        "current_quality_passes": sum(p["current"]["quality_passed"] for p in pairs),
        "fidelity_improved_cases": sum(p.get("fidelity_delta_pp", 0) > 1e-9 for p in valid),
        "fidelity_worsened_cases": sum(p.get("fidelity_delta_pp", 0) < -1e-9 for p in valid),
        "app_rank_improved_cases": sum(p.get("app_rank_change", 0) > 0 for p in valid),
        "app_rank_worsened_cases": sum(p.get("app_rank_change", 0) < 0 for p in valid),
        "mean_fidelity_delta_pp": statistics.mean(p["fidelity_delta_pp"] for p in valid) if valid else None,
        "mean_original_fidelity_pct": statistics.mean(p["original"]["shape_fidelity"] * 100 for p in valid) if valid else None,
        "mean_current_fidelity_pct": statistics.mean(p["current"]["shape_fidelity"] * 100 for p in valid) if valid else None,
        "median_time_delta_seconds": statistics.median(p["time_delta_seconds"] for p in valid) if valid else None,
        "engine_equal_pairs": sum(p["engine_revisions_equal"] for p in pairs),
        "pairs_with_provider_failures": sum(bool(p["original"]["routing_failures"] or p["current"]["routing_failures"]) for p in pairs),
        "original_distance_within_20_percent": sum(p["original"].get("distance_error_pct", float("inf")) <= 20 for p in pairs),
        "current_distance_within_20_percent": sum(p["current"].get("distance_error_pct", float("inf")) <= 20 for p in pairs),
    }
    report = {"manifest": data["manifest"], "summary": summary, "pairs": pairs,
              "retry_audit": data.get("retries", []),
              "physical_error_definition": "Symmetric RMS distance to full polylines, 512 uniform arc-length samples on each line, shared local metre frame.",
              "interpretation": "No failed cases omitted. Higher geometric fidelity does not imply human recognition or route safety."}
    (folder / "comparison.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    heading = "RÉSZEREDMÉNY · " if args.allow_partial else ""
    evidence_timing = (
        "Az eredeti futások korábban rögzített, változatlan nyers API-bizonyítékait használtuk újra; "
        "az új változat friss kérésekkel futott. Azonos kódú eredeti, OSM-pillanatkép és tesztesetek, "
        "páronként ellenőrzött ORS-verzió. Az időadatok nem egymás közé illesztett mérések."
        if data["manifest"].get("original_evidence_reused_from") else
        "A változatok sorban, váltakozó AB/BA sorrendben futottak, futásonként saját API-kérésekkel."
    )
    document = f"""<!doctype html><html lang="hu"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GPS-art: páros összehasonlítás</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#173530;background:#f4f3ed;max-width:1180px;margin:2rem auto;padding:0 1rem}}section,header{{background:white;padding:1.3rem;margin:1.4rem 0;border:1px solid #d5ddd7;border-radius:12px}}table{{border-collapse:collapse;width:100%;font-size:.94rem}}th,td{{padding:.6rem;text-align:left;border-bottom:1px solid #dbe0dc}}img{{width:100%;height:auto}}.scroll{{overflow:auto}}code{{word-break:break-all}}h1{{line-height:1.15}}small{{color:#53655f}}</style>
<header><h1>{heading}Eredeti és új GPS-art generátor</h1><p>Szeged · rögzített OSM-keresési hálózat · valódi ORS-útvonalak.</p><p>{html.escape(evidence_timing)}</p>
<p>Eredeti commit: <code>{data['manifest']['original_commit']}</code><br>OSM-pillanatkép: <code>{data['manifest']['osm_snapshot_sha256']}</code></p>
<p>Hibamentesen összevethető párok: {len(valid)}/{len(pairs)}. Ezekben az alakhűség {summary['fidelity_improved_cases']} esetben javult, {summary['fidelity_worsened_cases']} esetben romlott. Minden minőségi ellenőrzésen átment (minden futást számítva): eredeti {summary['original_quality_passes']}/{len(pairs)}, új {summary['current_quality_passes']}/{len(pairs)}.</p>
<p>A hibamentesen összevethető esetek egyenlő súlyú alakhűségi átlaga: <b>{text_num(summary['mean_original_fidelity_pct'])}% → {text_num(summary['mean_current_fidelity_pct'])}%</b>; különbség: <b>{text_num(summary['mean_fidelity_delta_pp'])} százalékpont</b>.</p>
<p>A százalékos alakhűség geometriai mérőszám, nem emberi felismerési arány. Minden romló, hibás és keretkorlátos eset szerepel. Egy város és egy futás/verzió/eset alapján nincs általános minőségi vagy sebességgarancia.</p>
<p>A 20%-os távhibahatáron belül maradt: eredeti {summary['original_distance_within_20_percent']}/{len(pairs)}, új {summary['current_distance_within_20_percent']}/{len(pairs)}. API-időtúllépés miatt végzett ismétlések: {len(data.get('retries', []))}. Az első kísérletet a nyers adatok megőrzik; a megismételt futás azonos seeddel/kóddal futott, kiválasztását nem a minőségi pontszám határozta meg.</p>
<div class="scroll"><table><thead><tr><th>Eset</th><th>Alakhűség %<br>eredeti → új</th><th>Távhiba %<br>eredeti → új</th><th>Idő s<br>eredeti → új</th><th>Minden ellenőrzés<br>eredeti → új</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<small>Az idő teljes, instrumentált generálási falióraidő, a kvótavárakozással együtt. A teszt legfeljebb {data['manifest'].get('request_limit_per_60_seconds', 'korlát nélküli')} kérést indított 60,5 másodpercenként, közös, a futások között is megőrzött számlálóval. A várakozások külön szerepelnek, de összegük nem vonható le egyszerűen a teljes időből a párhuzamos munka miatt. Ez nem kvótavédelem nélküli produkciós sebességmérés. A pontozás közös implementációval újraellenőrizve. A körvonal fizikai RMS-eltérése mindkét vonalon 512 egyenletes ívhosszú mintából számolt távolság a teljes másik vonalig. Nem a közúti pozíció pontosságának becslése.</small></header>{''.join(cards)}</html>"""
    (folder / "comparison.html").write_text(document, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
