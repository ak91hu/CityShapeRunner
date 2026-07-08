"""One-time authoring tool that writes the seed SVG artwork files.

The generated SVGs are the real assets consumed by app.core.geometry.parse_svg.
Run:  python scripts/generate_shapes.py
"""
from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHAPES_DIR = ROOT / "data" / "shapes"
ARTWORKS = ROOT / "data" / "seed" / "artworks.json"


# --------------------------------------------------------------------------- #
# SVG element helpers
# --------------------------------------------------------------------------- #

def svg(inner: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">\n'
        f"{inner}\n</svg>\n"
    )


def polygon(points, stroke="black", fill="none") -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{pts}" stroke="{stroke}" fill="{fill}" stroke-width="2"/>'


def polyline(points, stroke="black") -> str:
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polyline points="{pts}" stroke="{stroke}" fill="none" stroke-width="2"/>'


def circle(cx, cy, r, stroke="black", fill="none") -> str:
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="{stroke}" fill="{fill}" stroke-width="2"/>'


def ellipse(cx, cy, rx, ry, stroke="black", fill="none") -> str:
    return f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" stroke="{stroke}" fill="{fill}" stroke-width="2"/>'


def rect(x, y, w, h, stroke="black", fill="none") -> str:
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" stroke="{stroke}" fill="{fill}" stroke-width="2"/>'


def path(d, stroke="black", fill="none") -> str:
    return f'<path d="{d}" stroke="{stroke}" fill="{fill}" stroke-width="2"/>'


def line(x1, y1, x2, y2, stroke="black") -> str:
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="2"/>'


# --------------------------------------------------------------------------- #
# Generative point helpers
# --------------------------------------------------------------------------- #

def star_points(cx=50, cy=52, r_out=42, r_in=17, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        ang = math.radians(rot + i * 180 / n)
        r = r_out if i % 2 == 0 else r_in
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    pts.append(pts[0])
    return pts


def sun_rays(cx=50, cy=50, r=22, n=12, ray=14):
    out = []
    for i in range(n):
        a = math.radians(i * 360 / n)
        x1, y1 = cx + r * math.cos(a), cy + r * math.sin(a)
        x2, y2 = cx + (r + ray) * math.cos(a), cy + (r + ray) * math.sin(a)
        out.append(line(x1, y1, x2, y2))
    return "\n".join(out)


def flower_petals(cx=50, cy=44, r=10, n=6, dist=16):
    out = []
    for i in range(n):
        a = math.radians(i * 360 / n - 90)
        px, py = cx + dist * math.cos(a), cy + dist * math.sin(a)
        out.append(circle(px, py, r))
    return "\n".join(out)


def reg_poly_pts(cx, cy, r, n, rot=0):
    """Regular polygon vertices (closed: last == first)."""
    pts = []
    for i in range(n):
        a = math.radians(rot + i * 360 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pts.append(pts[0])
    return pts


def spiral_pts(cx, cy, r0, r1, turns, n=80):
    """Archimedean spiral from r0 to r1 over *turns* revolutions."""
    pts = []
    for i in range(n + 1):
        t = i / n
        ang = t * turns * 2 * math.pi
        r = r0 + (r1 - r0) * t
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def wave_pts(x0, x1, y, amp, n=3, steps=80):
    """Sine-wave polyline from x0 to x1 with *n* full oscillations."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = x0 + (x1 - x0) * t
        yv = y + amp * math.sin(t * n * 2 * math.pi)
        pts.append((x, yv))
    return pts


def snowflake(cx, cy, r):
    """Six-spoke snowflake with branches at midpoints."""
    parts = []
    for i in range(6):
        a = math.radians(i * 60)
        x2, y2 = cx + r * math.cos(a), cy + r * math.sin(a)
        parts.append(line(cx, cy, x2, y2))
        mx = cx + r * 0.55 * math.cos(a)
        my = cy + r * 0.55 * math.sin(a)
        for da in (55, -55):
            ba = a + math.radians(da)
            parts.append(line(mx, my, mx + 12 * math.cos(ba), my + 12 * math.sin(ba)))
    return "\n".join(parts)


# --------------------------------------------------------------------------- #
# Shape definitions — each value is the inner SVG markup for viewBox 0 0 100 100
# --------------------------------------------------------------------------- #

SHAPES: dict[str, str] = {

    # ----------------------------------------------------------------- Basic
    "heart": path("M50 88 C 18 66, 8 44, 26 30 C 38 20, 50 28, 50 42 C 50 28, 62 20, 74 30 C 92 44, 82 66, 50 88 Z"),
    "star": polygon(star_points()),
    "circle": circle(50, 50, 42),
    "smiley": "\n".join([
        circle(50, 50, 42),
        circle(38, 42, 4, fill="black"),
        circle(62, 42, 4, fill="black"),
        path("M34 60 Q 50 74 66 60"),
    ]),
    "triangle": polygon([(50, 12), (88, 82), (12, 82)]),
    "square": rect(18, 18, 64, 64),
    "diamond": polygon([(50, 12), (88, 50), (50, 88), (12, 50)]),
    "cross": polygon([(42, 14), (58, 14), (58, 42), (86, 42), (86, 58), (58, 58), (58, 86), (42, 86), (42, 58), (14, 58), (14, 42), (42, 42)]),
    "arrow": polygon([(14, 44), (60, 44), (60, 28), (88, 50), (60, 72), (60, 56), (14, 56)]),
    "spiral": polyline(spiral_pts(50, 50, 5, 36, 2.5, 90)),
    "infinity": path("M20 50 C 20 28, 44 28, 50 50 C 56 72, 80 72, 80 50 C 80 28, 56 28, 50 50 C 44 72, 20 72, 20 50 Z"),
    "wave": polyline(wave_pts(12, 88, 50, 16, 2, 80)),
    "crescent": path("M38 16 C 18 28, 18 72, 38 84 C 26 68, 26 32, 38 16 Z"),
    "clover": "\n".join([
        circle(50, 32, 15),
        circle(32, 50, 15),
        circle(68, 50, 15),
        circle(50, 68, 15),
        polyline([(50, 68), (50, 88)]),
    ]),
    "hexagon": polygon(reg_poly_pts(50, 50, 40, 6, -90)),

    # --------------------------------------------------------------- Animals
    "dog": "\n".join([
        polygon([(30, 30), (35, 12), (45, 28)]),
        polygon([(70, 30), (65, 12), (55, 28)]),
        circle(50, 45, 26),
        ellipse(50, 60, 14, 10),
        circle(44, 42, 3, fill="black"),
        circle(56, 42, 3, fill="black"),
    ]),
    "cat": "\n".join([
        polygon([(28, 32), (30, 10), (46, 26)]),
        polygon([(72, 32), (70, 10), (54, 26)]),
        circle(50, 48, 26),
        polygon([(50, 52), (46, 60), (54, 60)]),
        polyline([(40, 66), (30, 62), (40, 58)]),
        polyline([(60, 66), (70, 62), (60, 58)]),
    ]),
    "fish": "\n".join([
        ellipse(45, 50, 28, 18),
        polygon([(70, 50), (88, 36), (88, 64)]),
        circle(34, 46, 3, fill="black"),
    ]),
    "bird": polyline([(12, 55), (35, 35), (50, 52), (65, 35), (88, 55)]),
    "rabbit": "\n".join([
        ellipse(40, 28, 7, 20),
        ellipse(60, 28, 7, 20),
        ellipse(50, 62, 26, 24),
        circle(42, 56, 3, fill="black"),
        circle(58, 56, 3, fill="black"),
        ellipse(50, 66, 6, 4),
    ]),
    "dinosaur": "\n".join([
        polygon([(12, 78), (20, 40), (32, 30), (40, 44), (52, 30), (64, 42), (74, 32), (86, 44), (82, 60), (70, 64), (66, 78), (12, 78)]),
        polyline([(20, 40), (24, 22), (28, 40)]),
        polyline([(40, 44), (44, 28), (48, 44)]),
        polyline([(60, 42), (64, 26), (68, 42)]),
        circle(78, 38, 3, fill="black"),
    ]),
    "butterfly": "\n".join([
        ellipse(32, 40, 20, 24),
        ellipse(68, 40, 20, 24),
        ellipse(32, 64, 14, 12),
        ellipse(68, 64, 14, 12),
        ellipse(50, 50, 3, 24),
        polyline([(50, 26), (46, 14)]),
        polyline([(50, 26), (54, 14)]),
    ]),
    "elephant": "\n".join([
        ellipse(40, 58, 28, 22),
        circle(72, 48, 18),
        path("M84 50 C 90 56, 88 72, 76 76 C 70 77, 72 68, 78 62"),
        ellipse(60, 40, 10, 16),
        rect(28, 74, 8, 12),
        rect(50, 74, 8, 12),
        circle(74, 44, 2, fill="black"),
    ]),
    "horse": "\n".join([
        ellipse(42, 52, 24, 14),
        polygon([(58, 46), (72, 32), (84, 30), (86, 36), (78, 38), (68, 44), (60, 56)]),
        polyline([(32, 64), (32, 86)]),
        polyline([(52, 64), (52, 86)]),
        polyline([(72, 32), (68, 22), (74, 28)]),
        path("M20 48 C 14 44, 14 58, 20 56"),
        circle(80, 34, 2, fill="black"),
    ]),
    "turtle": "\n".join([
        ellipse(50, 50, 30, 22),
        ellipse(82, 50, 10, 8),
        ellipse(20, 50, 7, 5),
        ellipse(28, 68, 8, 6),
        ellipse(72, 68, 8, 6),
        ellipse(28, 32, 8, 6),
        ellipse(72, 32, 8, 6),
        circle(84, 48, 2, fill="black"),
    ]),
    "snake": "\n".join([
        polyline([(15, 75), (30, 58), (45, 75), (60, 58), (75, 75), (85, 58)]),
        circle(86, 54, 6),
        polyline([(92, 52), (88, 50)]),
        circle(86, 52, 2, fill="black"),
    ]),
    "dolphin": "\n".join([
        path("M14 60 C 20 44, 50 38, 70 46 C 80 50, 86 44, 88 38 L 84 58 C 78 66, 60 68, 40 64 C 28 62, 18 64, 14 60 Z"),
        path("M40 44 C 36 34, 44 30, 48 40"),
        polygon([(84, 52), (90, 44), (88, 58)]),
        circle(24, 54, 2, fill="black"),
    ]),
    "whale": "\n".join([
        path("M12 55 C 25 38, 55 36, 75 48 C 82 52, 86 46, 88 38 L 84 58 C 76 68, 55 68, 35 63 C 22 60, 15 60, 12 55 Z"),
        polygon([(84, 50), (90, 42), (88, 58)]),
        polyline([(40, 38), (36, 24), (42, 28)]),
        polyline([(46, 36), (44, 22), (50, 26)]),
        circle(68, 50, 2, fill="black"),
    ]),
    "owl": "\n".join([
        circle(50, 48, 28),
        polygon([(30, 28), (36, 14), (44, 26)]),
        polygon([(70, 28), (64, 14), (56, 26)]),
        circle(40, 44, 8),
        circle(60, 44, 8),
        circle(40, 44, 3, fill="black"),
        circle(60, 44, 3, fill="black"),
        polygon([(50, 50), (46, 56), (54, 56)]),
        polyline([(38, 76), (42, 84)]),
        polyline([(62, 76), (58, 84)]),
    ]),
    "penguin": "\n".join([
        ellipse(50, 56, 22, 28),
        circle(50, 28, 14),
        polygon([(50, 30), (44, 34), (56, 34)]),
        circle(44, 26, 3, fill="black"),
        circle(56, 26, 3, fill="black"),
        ellipse(28, 56, 7, 18),
        ellipse(72, 56, 7, 18),
        ellipse(42, 84, 8, 5),
        ellipse(58, 84, 8, 5),
    ]),
    "bear": "\n".join([
        circle(50, 50, 28),
        circle(30, 30, 10),
        circle(70, 30, 10),
        circle(50, 58, 12),
        circle(50, 54, 4, fill="black"),
        circle(40, 44, 3, fill="black"),
        circle(60, 44, 3, fill="black"),
    ]),
    "giraffe": "\n".join([
        ellipse(38, 60, 24, 16),
        polygon([(48, 54), (58, 52), (66, 28), (58, 24), (52, 26), (46, 50)]),
        circle(62, 20, 10),
        polyline([(28, 72), (28, 86)]),
        polyline([(48, 72), (48, 86)]),
        polygon([(60, 14), (56, 8), (62, 12)]),
        polygon([(68, 16), (66, 10), (72, 14)]),
        circle(64, 20, 2, fill="black"),
    ]),
    "crab": "\n".join([
        ellipse(50, 50, 22, 16),
        polygon([(26, 42), (14, 36), (16, 48), (10, 52)]),
        polygon([(74, 42), (86, 36), (84, 48), (90, 52)]),
        polyline([(30, 56), (20, 66), (22, 70)]),
        polyline([(38, 60), (30, 72), (32, 76)]),
        polyline([(62, 60), (70, 72), (68, 76)]),
        polyline([(70, 56), (80, 66), (78, 70)]),
        circle(42, 46, 2, fill="black"),
        circle(58, 46, 2, fill="black"),
    ]),
    "dragonfly": "\n".join([
        ellipse(20, 35, 16, 10),
        ellipse(80, 35, 16, 10),
        ellipse(22, 55, 16, 10),
        ellipse(78, 55, 16, 10),
        ellipse(50, 48, 5, 30),
        circle(50, 22, 7),
        circle(48, 20, 2, fill="black"),
        circle(52, 20, 2, fill="black"),
    ]),
    "shark": "\n".join([
        path("M12 55 C 28 47, 55 47, 70 50 C 80 52, 84 48, 88 42 L 84 58 C 78 64, 60 65, 40 62 C 25 60, 15 60, 12 55 Z"),
        polygon([(48, 47), (44, 32), (56, 38)]),
        polygon([(82, 52), (88, 44), (88, 58)]),
        circle(72, 52, 2, fill="black"),
    ]),
    "fox": "\n".join([
        polygon([(50, 16), (28, 28), (34, 40), (22, 70), (50, 58), (78, 70), (66, 40), (72, 28)]),
        circle(40, 38, 3, fill="black"),
        circle(60, 38, 3, fill="black"),
        polygon([(50, 48), (44, 54), (56, 54)]),
    ]),
    "swan": "\n".join([
        path("M18 62 C 18 44, 36 36, 52 40 C 60 42, 66 38, 72 30 C 68 36, 70 42, 64 44 C 56 46, 46 48, 42 56 C 34 62, 22 68, 18 62 Z"),
        circle(74, 28, 6),
        polygon([(80, 26), (86, 28), (80, 30)]),
    ]),
    "frog": "\n".join([
        ellipse(50, 55, 28, 22),
        circle(38, 32, 10),
        circle(62, 32, 10),
        circle(38, 32, 4, fill="black"),
        circle(62, 32, 4, fill="black"),
        path("M40 66 Q 32 74 24 68"),
        path("M60 66 Q 68 74 76 68"),
        path("M44 60 Q 50 64 56 60"),
    ]),

    # ---------------------------------------------------------------- Sports
    "bicycle": "\n".join([
        circle(28, 70, 16),
        circle(72, 70, 16),
        polyline([(28, 70), (50, 70), (72, 70)]),
        polyline([(50, 70), (50, 45), (72, 70)]),
        polyline([(50, 45), (38, 70)]),
        polyline([(50, 45), (58, 40)]),
    ]),
    "runner": "\n".join([
        circle(52, 24, 8),
        polyline([(52, 32), (50, 55), (40, 78)]),
        polyline([(50, 55), (66, 72)]),
        polyline([(52, 38), (38, 50)]),
        polyline([(52, 38), (68, 30)]),
    ]),
    "trophy": "\n".join([
        polygon([(34, 20), (66, 20), (60, 50), (40, 50)]),
        polyline([(34, 24), (24, 34), (34, 40)]),
        polyline([(66, 24), (76, 34), (66, 40)]),
        rect(46, 50, 8, 14),
        rect(34, 64, 32, 10),
    ]),
    "swimmer": "\n".join([
        circle(50, 30, 8),
        polyline([(50, 38), (36, 48), (60, 48), (44, 60)]),
        polyline(wave_pts(12, 88, 68, 8, 3, 60)),
    ]),
    "skier": "\n".join([
        circle(50, 22, 8),
        polyline([(50, 30), (52, 54), (42, 76)]),
        polyline([(52, 54), (66, 70)]),
        polyline([(48, 38), (34, 48)]),
        polyline([(48, 38), (62, 32)]),
        polyline([(16, 80), (82, 76)]),
    ]),
    "soccer-ball": "\n".join([
        circle(50, 50, 36),
        polygon([(50, 26), (62, 34), (57, 48), (43, 48), (38, 34)]),
        polyline([(50, 26), (50, 14)]),
        polyline([(62, 34), (74, 30)]),
        polyline([(57, 48), (66, 60)]),
        polyline([(43, 48), (34, 60)]),
        polyline([(38, 34), (26, 30)]),
    ]),
    "basketball": "\n".join([
        circle(50, 50, 36),
        polyline([(14, 50), (86, 50)]),
        polyline([(50, 14), (50, 86)]),
        path("M18 24 Q 50 50 82 24"),
        path("M18 76 Q 50 50 82 76"),
    ]),
    "tennis-racket": "\n".join([
        ellipse(50, 34, 22, 26),
        rect(47, 60, 6, 24),
        line(38, 14, 38, 54),
        line(62, 14, 62, 54),
        line(32, 24, 68, 24),
        line(32, 44, 68, 44),
    ]),
    "dumbbell": "\n".join([
        rect(12, 42, 10, 16),
        rect(22, 47, 56, 6),
        rect(78, 42, 10, 16),
    ]),
    "medal": "\n".join([
        polyline([(34, 14), (44, 42)]),
        polyline([(66, 14), (56, 42)]),
        circle(50, 58, 22),
        circle(50, 58, 12),
    ]),
    "kayak": "\n".join([
        ellipse(50, 56, 34, 8),
        circle(50, 46, 7),
        line(24, 42, 35, 56),
        line(76, 42, 65, 56),
    ]),

    # ---------------------------------------------------------------- Nature
    "tree": "\n".join([
        polygon([(50, 12), (78, 50), (22, 50)]),
        rect(45, 50, 10, 30),
    ]),
    "leaf": path("M50 12 C 80 30, 78 64, 50 88 C 22 64, 24 30, 50 12 Z"),
    "mountain": "\n".join([
        polygon([(10, 80), (38, 30), (60, 80)]),
        polygon([(50, 80), (72, 40), (90, 80)]),
    ]),
    "flower": "\n".join([
        flower_petals(),
        circle(50, 44, 8, fill="black"),
        polyline([(50, 54), (50, 88)]),
        polyline([(50, 70), (38, 60)]),
    ]),
    "sun": "\n".join([
        sun_rays(),
        circle(50, 50, 20),
    ]),
    "river": path("M8 50 Q 22 35 36 50 T 64 50 T 92 50"),
    "moon": path("M60 14 C 36 20, 28 50, 54 82 C 36 66, 38 32, 60 14 Z"),
    "cloud": path("M18 62 C 10 62, 10 50, 22 50 C 22 36, 40 34, 46 46 C 52 36, 68 36, 70 48 C 82 46, 86 56, 80 62 Z"),
    "snowflake": snowflake(50, 50, 34),
    "mushroom": "\n".join([
        path("M20 52 C 20 24, 80 24, 80 52 Z"),
        rect(42, 52, 16, 30),
    ]),
    "cactus": "\n".join([
        rect(45, 28, 10, 58),
        polyline([(30, 62), (30, 48), (40, 48), (40, 58)]),
        polyline([(60, 58), (60, 48), (70, 48), (70, 62)]),
    ]),
    "palm-tree": "\n".join([
        polyline([(50, 88), (50, 48)]),
        path("M50 48 Q 30 38, 14 46"),
        path("M50 48 Q 70 38, 86 46"),
        path("M50 48 Q 36 26, 22 26"),
        path("M50 48 Q 64 26, 78 26"),
        path("M50 48 Q 50 22, 50 16"),
    ]),
    "ocean-wave": path("M10 55 Q 22 30, 35 55 Q 48 80, 62 55 Q 75 30, 88 55"),
    "fire": path("M50 88 C 32 78, 30 58, 46 50 C 40 40, 42 28, 50 14 C 56 26, 60 34, 56 42 C 66 38, 70 48, 62 54 C 72 56, 70 74, 50 88 Z"),
    "lightning": polygon([(56, 10), (38, 48), (50, 48), (34, 90), (60, 48), (48, 48), (56, 10)]),
    "raindrop": path("M50 14 C 30 40, 28 68, 50 86 C 72 68, 70 40, 50 14 Z"),

    # -------------------------------------------------- City / Landmarks
    "bridge": "\n".join([
        rect(22, 30, 8, 40),
        rect(70, 30, 8, 40),
        polyline([(26, 30), (50, 18), (74, 30)]),
        polyline([(15, 70), (85, 70)]),
        polyline([(26, 30), (26, 70)]),
        polyline([(74, 30), (74, 70)]),
        polyline([(35, 70), (35, 38)]),
        polyline([(65, 70), (65, 38)]),
    ]),
    "crown": polygon([(15, 70), (15, 40), (32, 55), (50, 30), (68, 55), (85, 40), (85, 70), (15, 70)]),
    "parliament": "\n".join([
        rect(15, 45, 70, 30),
        polygon([(40, 45), (50, 28), (60, 45)]),
        rect(20, 60, 6, 15), rect(30, 60, 6, 15), rect(44, 60, 6, 15), rect(56, 60, 6, 15), rect(66, 60, 6, 15), rect(76, 60, 6, 15),
    ]),
    "danube-wave": path("M8 55 Q 22 30 36 55 T 64 55 T 92 55"),
    "castle": "\n".join([
        rect(20, 40, 60, 40),
        polygon([(20, 40), (20, 28), (26, 34), (32, 28), (38, 34), (44, 28), (50, 34), (56, 28), (62, 34), (68, 28), (74, 34), (80, 28), (80, 40)]),
        rect(30, 55, 14, 25),
        rect(60, 50, 8, 8), rect(40, 50, 8, 8),
    ]),
    "cathedral": "\n".join([
        rect(30, 50, 40, 30),
        polygon([(30, 50), (50, 22), (70, 50)]),
        polyline([(50, 22), (50, 8)]),
        polyline([(46, 12), (50, 4), (54, 12)]),
        rect(44, 60, 5, 20), rect(51, 60, 5, 20),
    ]),
    "viaduct": "\n".join([
        polyline([(8, 55), (92, 55)]),
        path("M16 55 Q 20 80 26 55"),
        path("M30 55 Q 34 80 40 55"),
        path("M44 55 Q 48 80 54 55"),
        path("M58 55 Q 62 80 68 55"),
        path("M72 55 Q 76 80 82 55"),
    ]),
    "great-church": "\n".join([
        rect(25, 45, 50, 35),
        rect(20, 55, 8, 25), rect(72, 55, 8, 25),
        polygon([(20, 55), (24, 40), (28, 55)]),
        polygon([(72, 55), (76, 40), (80, 55)]),
        rect(45, 60, 10, 20),
    ]),
    "tower": "\n".join([
        rect(38, 30, 24, 58),
        polygon([(38, 30), (50, 14), (62, 30)]),
        rect(44, 48, 12, 14),
    ]),
    "lighthouse": "\n".join([
        polygon([(42, 80), (42, 36), (46, 28), (54, 28), (58, 36), (58, 80)]),
        polygon([(46, 28), (50, 18), (54, 28)]),
        circle(50, 33, 4),
        rect(36, 80, 28, 6),
    ]),
    "windmill": "\n".join([
        rect(44, 38, 12, 50),
        polygon([(44, 38), (50, 28), (56, 38)]),
        circle(50, 36, 4),
        line(50, 36, 50, 16),
        line(50, 36, 70, 36),
        line(50, 36, 50, 56),
        line(50, 36, 30, 36),
    ]),
    "colosseum": "\n".join([
        ellipse(50, 55, 38, 26),
        ellipse(50, 55, 24, 16),
        path("M20 58 Q 24 68 28 58"),
        path("M30 58 Q 34 68 38 58"),
        path("M60 58 Q 64 68 68 58"),
        path("M70 58 Q 74 68 78 58"),
    ]),
    "pyramid": "\n".join([
        polygon([(12, 82), (50, 14), (88, 82)]),
        polyline([(50, 14), (50, 82)]),
    ]),
    "arch": path("M18 82 L 18 50 Q 50 18 82 50 L 82 82"),
    "obelisk": polygon([(44, 82), (44, 28), (47, 22), (50, 14), (53, 22), (56, 28), (56, 82)]),

    # ----------------------------------------------------------------- Funny
    "duck": "\n".join([
        circle(40, 40, 16),
        ellipse(52, 58, 24, 16),
        polygon([(54, 40), (66, 36), (66, 44)]),
        circle(36, 38, 3, fill="black"),
    ]),
    "pizza": "\n".join([
        circle(50, 50, 40),
        polyline([(50, 50), (50, 12)]),
        polyline([(50, 50), (82, 65)]),
        polyline([(50, 50), (18, 65)]),
    ]),
    "rocket": "\n".join([
        polygon([(50, 10), (62, 40), (62, 70), (38, 70), (38, 40)]),
        polygon([(38, 70), (28, 86), (38, 78)]),
        polygon([(62, 70), (72, 86), (62, 78)]),
        circle(50, 42, 6),
    ]),
    "ghost": "\n".join([
        path("M28 72 L 28 40 C 28 18, 72 18, 72 40 L 72 72 L 68 76 L 64 72 L 60 76 L 56 72 L 52 76 L 48 72 L 44 76 L 40 72 L 36 76 L 32 72 L 28 76 Z"),
        circle(40, 38, 4, fill="black"),
        circle(60, 38, 4, fill="black"),
    ]),
    "skull": "\n".join([
        circle(50, 42, 28),
        rect(40, 60, 20, 14),
        circle(40, 42, 6, fill="black"),
        circle(60, 42, 6, fill="black"),
        polygon([(50, 50), (46, 58), (54, 58)]),
        line(44, 64, 44, 74),
        line(48, 64, 48, 74),
        line(52, 64, 52, 74),
        line(56, 64, 56, 74),
    ]),
    "bat": "\n".join([
        path("M50 46 C 46 40, 42 44, 38 46 C 30 40, 20 42, 12 52 C 22 48, 30 54, 34 58 C 38 54, 44 58, 50 60 C 56 58, 62 54, 66 58 C 70 54, 78 48, 88 52 C 80 42, 70 40, 62 46 C 58 44, 54 40, 50 46 Z"),
        circle(50, 44, 5),
        polygon([(46, 38), (44, 32), (48, 36)]),
        polygon([(54, 38), (56, 32), (52, 36)]),
    ]),
    "pumpkin": "\n".join([
        ellipse(50, 56, 34, 26),
        polyline([(50, 30), (50, 82)]),
        polyline([(34, 36), (36, 74)]),
        polyline([(66, 36), (64, 74)]),
        rect(47, 22, 6, 10),
    ]),
    "snowman": "\n".join([
        circle(50, 72, 16),
        circle(50, 46, 12),
        circle(50, 26, 9),
        circle(50, 46, 2, fill="black"),
        circle(50, 40, 2, fill="black"),
        polyline([(38, 46), (22, 38)]),
        polyline([(62, 46), (78, 38)]),
        rect(42, 14, 16, 6),
        rect(45, 6, 10, 10),
        circle(46, 24, 2, fill="black"),
        circle(54, 24, 2, fill="black"),
        polygon([(50, 28), (53, 30), (47, 30)]),
    ]),
    "gingerbread-man": "\n".join([
        circle(50, 22, 12),
        polyline([(50, 34), (50, 55)]),
        polyline([(50, 38), (28, 48), (22, 42)]),
        polyline([(50, 38), (72, 48), (78, 42)]),
        polyline([(50, 55), (38, 78), (30, 76)]),
        polyline([(50, 55), (62, 78), (70, 76)]),
        circle(46, 20, 2, fill="black"),
        circle(54, 20, 2, fill="black"),
    ]),
    "robot": "\n".join([
        rect(32, 20, 36, 28),
        line(50, 20, 50, 12),
        circle(50, 9, 3),
        circle(42, 32, 4, fill="black"),
        circle(58, 32, 4, fill="black"),
        rect(40, 40, 20, 4),
        rect(34, 52, 32, 30),
        line(34, 60, 66, 60),
        rect(24, 56, 10, 20),
        rect(66, 56, 10, 20),
    ]),
    "alien": "\n".join([
        ellipse(50, 38, 22, 28),
        ellipse(40, 36, 6, 8, fill="black"),
        ellipse(60, 36, 6, 8, fill="black"),
        path("M40 16 Q 50 8, 60 16"),
        rect(42, 64, 16, 20),
        polyline([(42, 70), (30, 78)]),
        polyline([(58, 70), (70, 78)]),
    ]),
    "octopus": "\n".join([
        circle(50, 38, 24),
        path("M30 56 Q 22 72, 28 84"),
        path("M38 60 Q 34 76, 40 86"),
        path("M44 62 Q 42 80, 48 86"),
        path("M56 62 Q 58 80, 52 86"),
        path("M62 60 Q 66 76, 60 86"),
        path("M70 56 Q 78 72, 72 84"),
        circle(42, 34, 3, fill="black"),
        circle(58, 34, 3, fill="black"),
    ]),
    "musical-note": "\n".join([
        circle(36, 68, 10),
        polyline([(44, 68), (44, 22)]),
        path("M44 22 C 60 26, 62 36, 54 42"),
    ]),
    "guitar": "\n".join([
        ellipse(35, 62, 18, 24),
        circle(35, 62, 7),
        rect(40, 26, 7, 36),
        rect(38, 18, 11, 8),
    ]),
    "cupcake": "\n".join([
        polygon([(30, 55), (70, 55), (64, 85), (36, 85)]),
        path("M28 55 C 28 38, 40 30, 50 34 C 60 30, 72 38, 72 55 Z"),
        circle(50, 28, 6),
    ]),
    "balloon": "\n".join([
        ellipse(50, 38, 20, 26),
        polygon([(47, 62), (53, 62), (50, 67)]),
        polyline([(50, 67), (46, 90)]),
    ]),

    # --------------------------------------------------------------- Symbols
    "anchor": "\n".join([
        circle(50, 22, 8),
        line(50, 30, 50, 78),
        line(32, 42, 68, 42),
        path("M20 68 C 20 80, 80 80, 80 68"),
        line(20, 68, 28, 62),
        line(80, 68, 72, 62),
    ]),
    "key": "\n".join([
        circle(28, 36, 14),
        circle(28, 36, 6),
        polyline([(28, 50), (28, 82)]),
        polyline([(28, 70), (40, 70)]),
        polyline([(28, 76), (36, 76)]),
    ]),
    "compass": "\n".join([
        circle(50, 50, 38),
        polygon([(50, 18), (56, 50), (50, 82), (44, 50)]),
    ]),
    "flag": "\n".join([
        line(30, 12, 30, 88),
        polygon([(30, 14), (78, 14), (70, 30), (78, 46), (30, 46)]),
    ]),
    "map-pin": "\n".join([
        path("M50 14 C 32 14, 24 30, 24 42 C 24 60, 50 84, 50 84 C 50 84, 76 60, 76 42 C 76 30, 68 14, 50 14 Z"),
        circle(50, 38, 8),
    ]),
    "globe": "\n".join([
        circle(50, 50, 38),
        ellipse(50, 50, 38, 14),
        ellipse(50, 50, 14, 38),
        line(12, 50, 88, 50),
    ]),
    "envelope": "\n".join([
        rect(14, 28, 72, 44),
        polyline([(14, 28), (50, 56), (86, 28)]),
    ]),
    "heart-arrow": "\n".join([
        path("M50 78 C 26 60, 16 42, 30 30 C 40 22, 50 28, 50 40 C 50 28, 60 22, 70 30 C 84 42, 74 60, 50 78 Z"),
        line(16, 16, 86, 84),
        polygon([(86, 84), (76, 80), (80, 74)]),
        polygon([(16, 16), (22, 12), (24, 22)]),
    ]),
    "diamond-ring": "\n".join([
        circle(50, 60, 22),
        polygon([(50, 18), (38, 32), (50, 44), (62, 32)]),
        line(44, 28, 56, 28),
    ]),
    "music": "\n".join([
        circle(30, 68, 9),
        circle(62, 60, 9),
        line(38, 68, 38, 24),
        line(70, 60, 70, 20),
        line(38, 24, 70, 20),
    ]),
    "sailboat": "\n".join([
        polygon([(50, 10), (50, 60), (15, 60)]),
        polygon([(55, 20), (85, 60), (55, 60)]),
        polygon([(10, 65), (90, 65), (80, 80), (20, 80)]),
        line(50, 10, 50, 80),
    ]),
    "wolf": "\n".join([
        polygon([(20, 35), (15, 20), (30, 25), (40, 30), (50, 25), (60, 30), (70, 25), (85, 20), (80, 35), (75, 50), (60, 60), (50, 75), (40, 60), (25, 50), (20, 35)]),
        polygon([(25, 25), (22, 15), (30, 22)]),
        polygon([(75, 25), (78, 15), (70, 22)]),
        circle(35, 38, 3, fill="black"),
        circle(65, 38, 3, fill="black"),
    ]),
    "deer": "\n".join([
        polyline([(30, 20), (28, 10), (25, 15), (22, 8)]),
        polyline([(40, 20), (42, 10), (45, 15), (48, 8)]),
        ellipse(50, 45, 25, 30),
        polyline([(50, 75), (45, 88)]),
        polyline([(55, 75), (60, 88)]),
        circle(42, 40, 3, fill="black"),
    ]),
    "squirrel": "\n".join([
        path("M30 70 C 15 60, 15 40, 30 35 C 35 25, 45 20, 55 25"),
        circle(55, 30, 18),
        polygon([(45, 18), (42, 10), (52, 15)]),
        polygon([(62, 18), (60, 10), (68, 15)]),
        circle(50, 28, 3, fill="black"),
        ellipse(58, 35, 8, 5),
    ]),
    "hedgehog": "\n".join([
        ellipse(50, 60, 35, 22),
        polygon([(15, 60), (8, 50), (15, 45)]),
        polyline([(25, 45), (22, 35)]), polyline([(35, 42), (33, 32)]),
        polyline([(45, 40), (44, 28)]), polyline([(55, 40), (56, 28)]),
        polyline([(65, 42), (67, 32)]), polyline([(75, 45), (78, 35)]),
        circle(18, 55, 3, fill="black"),
    ]),
    "bee": "\n".join([
        ellipse(45, 55, 22, 16),
        path("M25 40 C 15 25, 25 20, 35 35"),
        path("M55 35 C 65 20, 70 30, 60 45"),
        polyline([(35, 45), (35, 65)]), polyline([(45, 45), (45, 65)]), polyline([(55, 45), (55, 65)]),
        circle(30, 50, 3, fill="black"),
    ]),
    "ant": "\n".join([
        circle(25, 50, 10), circle(50, 50, 12), circle(75, 50, 10),
        polyline([(20, 40), (10, 30)]), polyline([(20, 60), (10, 70)]),
        polyline([(80, 40), (90, 30)]), polyline([(80, 60), (90, 70)]),
        circle(22, 45, 3, fill="black"),
    ]),
    "spider": "\n".join([
        circle(50, 50, 22),
        polyline([(35, 35), (15, 25)]), polyline([(35, 45), (12, 45)]), polyline([(35, 55), (15, 65)]),
        polyline([(65, 35), (85, 25)]), polyline([(65, 45), (88, 45)]), polyline([(65, 55), (85, 65)]),
        circle(44, 45, 3, fill="black"), circle(56, 45, 3, fill="black"),
    ]),
    "seahorse": "\n".join([
        path("M50 10 C 40 15, 35 30, 40 40 C 45 50, 35 60, 40 75 C 45 85, 55 88, 60 80"),
        circle(45, 15, 6),
        polyline([(40, 30), (55, 35)]),
    ]),
    "jellyfish": "\n".join([
        path("M20 45 C 20 25, 80 25, 80 45"),
        polyline([(25, 45), (22, 75)]), polyline([(35, 45), (33, 80)]),
        polyline([(45, 45), (45, 85)]), polyline([(55, 45), (57, 80)]),
        polyline([(65, 45), (67, 75)]), polyline([(75, 45), (78, 70)]),
    ]),
    "starfish": "\n".join([
        polygon(reg_poly_pts(50, 50, 42, 5) + [reg_poly_pts(50, 50, 42, 5)[0]]),
    ]),
    "volcano": "\n".join([
        polygon([(15, 80), (35, 40), (40, 30), (60, 30), (65, 40), (85, 80)]),
        path("M40 30 Q 35 15 45 10 Q 50 5 55 10 Q 60 15 55 25"),
        polyline([(50, 10), (50, 25)]),
    ]),
    "waterfall": "\n".join([
        polygon([(30, 15), (70, 15), (65, 85), (35, 85)]),
        polyline([(35, 20), (35, 80)]), polyline([(45, 18), (45, 82)]),
        polyline([(55, 18), (55, 82)]), polyline([(65, 20), (65, 80)]),
    ]),
    "rainbow": "\n".join([
        path("M10 80 C 10 30, 90 30, 90 80"),
        path("M18 80 C 18 38, 82 38, 82 80"),
        path("M26 80 C 26 46, 74 46, 74 80"),
    ]),
    "tornado": "\n".join([
        path("M20 10 C 40 15, 60 15, 80 10 C 75 30, 70 40, 75 50 C 65 60, 55 65, 60 75 C 50 80, 45 85, 50 90"),
    ]),
    "island": "\n".join([
        path("M10 60 C 20 50, 40 45, 50 45 C 60 45, 80 50, 90 60"),
        polygon([(30, 45), (40, 20), (50, 25), (60, 18), (65, 40)]),
        polyline([(10, 60), (10, 65), (90, 65), (90, 60)]),
    ]),
    "desert": "\n".join([
        path("M5 70 C 15 50, 25 65, 35 55 C 45 45, 55 65, 65 55 C 75 45, 85 65, 95 70"),
        circle(80, 25, 12),
    ]),
    "forest": "\n".join([
        polygon([(15, 75), (15, 50), (5, 50), (25, 25), (15, 50)]),
        polygon([(40, 75), (40, 45), (28, 45), (50, 15), (72, 45), (60, 45), (60, 75)]),
        polygon([(85, 75), (85, 55), (75, 55), (90, 35), (95, 55), (90, 75)]),
    ]),
    "canyon": "\n".join([
        polygon([(5, 20), (30, 25), (30, 80), (5, 85)]),
        polygon([(95, 20), (70, 25), (70, 80), (95, 85)]),
        polyline([(30, 40), (70, 40)]), polyline([(30, 60), (70, 60)]),
    ]),
    "glacier": "\n".join([
        polygon([(10, 80), (25, 50), (40, 65), (55, 45), (70, 60), (85, 50), (90, 80)]),
        polyline([(25, 50), (25, 80)]), polyline([(40, 65), (40, 80)]),
        polyline([(55, 45), (55, 80)]), polyline([(70, 60), (70, 80)]), polyline([(85, 50), (85, 80)]),
    ]),
    "aurora": "\n".join([
        path("M5 50 C 15 20, 30 60, 45 25 C 60 55, 75 20, 95 45"),
        path("M5 65 C 15 35, 30 70, 45 40 C 60 65, 75 35, 95 55"),
    ]),
    "balloon": "\n".join([
        ellipse(50, 35, 25, 30),
        polygon([(48, 62), (52, 62), (53, 70), (47, 70)]),
        polyline([(47, 70), (43, 85)]), polyline([(53, 70), (57, 85)]),
    ]),
    "cake": "\n".join([
        rect(20, 40, 60, 40),
        rect(15, 30, 70, 15),
        polyline([(20, 40), (80, 40)]),
        line(30, 30, 30, 15), line(50, 30, 50, 10), line(70, 30, 70, 15),
    ]),
    "ice-cream": "\n".join([
        path("M35 45 C 35 25, 65 25, 65 45"),
        polygon([(35, 45), (65, 45), (50, 85)]),
        polyline([(40, 55), (50, 70), (60, 55)]),
    ]),
    "donut": "\n".join([
        circle(50, 50, 35),
        circle(50, 50, 12),
    ]),
    "coffee": "\n".join([
        rect(25, 35, 40, 40),
        path("M65 42 C 80 42, 80 60, 65 60"),
        polyline([(30, 25), (30, 20), (35, 20), (35, 25)]),
        polyline([(45, 25), (45, 18), (50, 18), (50, 25)]),
        polyline([(60, 25), (60, 20), (65, 20), (65, 25)]),
    ]),
    "hotdog": "\n".join([
        path("M15 50 C 15 35, 85 35, 85 50 C 85 65, 15 65, 15 50"),
        rect(10, 42, 80, 16),
    ]),
    "hamburger": "\n".join([
        ellipse(50, 25, 35, 12),
        rect(15, 25, 70, 10),
        rect(15, 35, 70, 8),
        ellipse(50, 50, 35, 12),
        rect(15, 50, 70, 8),
        ellipse(50, 70, 35, 10),
    ]),
    "cocktail": "\n".join([
        polygon([(20, 30), (80, 30), (50, 55)]),
        line(50, 55, 50, 85),
        rect(40, 85, 20, 5),
        circle(50, 15, 5),
        line(50, 20, 50, 30),
    ]),
    "pretzel": "\n".join([
        path("M25 50 C 15 30, 35 20, 50 40 C 65 20, 85 30, 75 50 C 85 70, 65 80, 50 60 C 35 80, 15 70, 25 50"),
    ]),
    "sunglasses": "\n".join([
        circle(28, 45, 18), circle(72, 45, 18),
        line(46, 45, 54, 45),
        rect(10, 42, 36, 6), rect(54, 42, 36, 6),
    ]),
    "shield": "\n".join([
        path("M50 10 L 80 20 L 80 50 C 80 70, 50 85, 50 85 C 50 85, 20 70, 20 50 L 20 20 Z"),
    ]),
    "sword": "\n".join([
        polygon([(48, 8), (52, 8), (52, 65), (48, 65)]),
        rect(38, 65, 24, 6),
        rect(47, 71, 6, 15),
    ]),
    "ring": "\n".join([
        circle(50, 55, 22),
        polygon([(42, 30), (58, 30), (55, 15), (45, 15)]),
        polyline([(42, 30), (42, 35)]), polyline([(58, 30), (58, 35)]),
    ]),
    "crystal": "\n".join([
        polygon([(50, 8), (70, 30), (60, 85), (40, 85), (30, 30)]),
        polyline([(30, 30), (50, 40), (70, 30)]),
        polyline([(50, 40), (50, 85)]),
    ]),
    "gem": "\n".join([
        polygon([(50, 10), (75, 35), (60, 85), (40, 85), (25, 35)]),
        polyline([(25, 35), (50, 45), (75, 35)]),
        polyline([(50, 45), (50, 85)]),
    ]),
    "star8": "\n".join([
        polygon(reg_poly_pts(50, 50, 42, 8) + [reg_poly_pts(50, 50, 42, 8)[0]]),
    ]),
    "pentagon": "\n".join([
        polygon(reg_poly_pts(50, 50, 42, 5) + [reg_poly_pts(50, 50, 42, 5)[0]]),
    ]),
    "octagon": "\n".join([
        polygon(reg_poly_pts(50, 50, 42, 8) + [reg_poly_pts(50, 50, 42, 8)[0]]),
    ]),
    "queen-crown": "\n".join([
        polygon([(10, 70), (10, 40), (22, 55), (35, 30), (50, 45), (65, 30), (78, 55), (90, 40), (90, 70)]),
        circle(10, 40, 4, fill="black"), circle(50, 45, 4, fill="black"), circle(90, 40, 4, fill="black"),
        rect(10, 65, 80, 8),
    ]),
    "skateboard": "\n".join([
        rect(8, 40, 84, 12),
        circle(20, 58, 6), circle(80, 58, 6),
    ]),
    "surfboard": "\n".join([
        path("M5 50 C 10 35, 90 35, 95 50 C 90 65, 10 65, 5 50"),
    ]),
    "kayak": "\n".join([
        path("M10 50 C 15 35, 85 35, 90 50 C 85 65, 15 65, 10 50"),
        line(50, 35, 50, 65),
        circle(50, 50, 8),
    ]),
    "canoe": "\n".join([
        path("M8 50 C 12 38, 88 38, 92 50 C 88 62, 12 62, 8 50"),
        line(20, 42, 20, 58), line(80, 42, 80, 58),
    ]),
    "golf-club": "\n".join([
        line(55, 8, 55, 70),
        path("M55 70 C 50 75, 45 80, 40 82 C 38 84, 36 82, 38 80"),
    ]),
    "hockey-stick": "\n".join([
        line(55, 8, 55, 70),
        path("M55 70 C 50 78, 40 82, 35 80 C 30 78, 28 82, 32 84"),
    ]),
    "volleyball": "\n".join([
        circle(50, 50, 38),
        path("M15 40 C 35 45, 65 45, 85 40"),
        path("M20 65 C 40 55, 60 55, 80 65"),
    ]),
    "bowling": "\n".join([
        circle(50, 55, 28),
        circle(42, 48, 4, fill="black"), circle(50, 45, 4, fill="black"), circle(58, 48, 4, fill="black"),
    ]),
    "archery-bow": "\n".join([
        path("M20 10 C 5 40, 5 60, 20 90"),
        line(20, 10, 20, 90),
        polygon([(20, 48), (80, 50), (20, 52)]),
    ]),
    "parachute": "\n".join([
        path("M10 40 C 10 15, 90 15, 90 40"),
        polyline([(10, 40), (35, 65)]), polyline([(35, 40), (40, 65)]),
        polyline([(65, 40), (60, 65)]), polyline([(90, 40), (65, 65)]),
        rect(35, 65, 30, 18),
    ]),
}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    SHAPES_DIR.mkdir(parents=True, exist_ok=True)
    artworks = json.loads(ARTWORKS.read_text(encoding="utf-8"))["items"]
    missing = [a["id"] for a in artworks if a["id"] not in SHAPES]
    if missing:
        raise SystemExit(f"Missing SVG definitions for: {missing}")
    extra = [sid for sid in SHAPES if sid not in {a["id"] for a in artworks}]
    if extra:
        raise SystemExit(f"SVG definitions without catalog entries: {extra}")
    for art in artworks:
        aid = art["id"]
        (SHAPES_DIR / f"{aid}.svg").write_text(svg(SHAPES[aid]), encoding="utf-8")
    print(f"Wrote {len(artworks)} SVG files to {SHAPES_DIR}")


if __name__ == "__main__":
    main()
