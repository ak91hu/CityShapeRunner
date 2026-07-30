"""Parametric shape templates in unit space.

Each template returns a list of sub-paths (a single closed outline for most
shapes). Shapes are *not* normalised here — :func:`geo.normalize_shape` does
that. The :data:`SHAPES` registry maps a canonical name to its generator.

Curved templates use enough samples for a smooth, recognisable outline;
angular templates retain only their meaningful corners. The road-routing stage
then selects a bounded set of curvature-preserving via-points.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable

from .geo import Path

ShapeGen = tuple[str, list[Path], bool]  # (name, paths, closed)


def _samples(n: int) -> list[float]:
    return [2 * math.pi * i / n for i in range(n + 1)]


def _lerp(a: tuple[float, float], b: tuple[float, float], n: int) -> Path:
    """Generate ``n`` evenly-spaced points from ``a`` to ``b`` (inclusive)."""
    return [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]


# --------------------------------------------------------------------------- #
# Core shapes (high-detail)
# --------------------------------------------------------------------------- #
def heart() -> ShapeGen:
    t = _samples(400)
    pts: Path = [
        (
            16 * math.sin(a) ** 3,
            13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a),
        )
        for a in t
    ]
    return ("heart", [pts], True)


def star(points: int = 5, inner_ratio: float = 0.52) -> ShapeGen:
    n = points * 2
    angles = [math.pi / 2 + 2 * math.pi * i / n for i in range(n + 1)]
    pts: Path = []
    for i, a in enumerate(angles):
        r = 1.0 if i % 2 == 0 else inner_ratio
        pts.append((r * math.cos(a), r * math.sin(a)))
    return ("star", [pts], True)


def circle() -> ShapeGen:
    t = _samples(360)
    pts = [(math.cos(a), math.sin(a)) for a in t]
    return ("circle", [pts], True)


def butterfly() -> ShapeGen:
    """A routable butterfly silhouette with no self-intersecting inner loops.

    The former mathematical butterfly curve traversed overlapping lobes for
    roughly forty unit-lengths. On a street graph that collapsed into a long,
    unrecognisable detour. This outline keeps the antennae and four wings while
    remaining a single short loop suitable for ORS via-points.
    """
    vertices: Path = [
        (0.0, 0.15),
        (-0.20, 0.46),
        (-0.46, 1.08),
        (-0.10, 0.68),
        (-0.72, 0.98),
        (-1.18, 0.48),
        (-0.72, 0.06),
        (-0.98, -0.52),
        (-0.34, -0.44),
        (0.0, -0.96),
        (0.34, -0.44),
        (0.98, -0.52),
        (0.72, 0.06),
        (1.18, 0.48),
        (0.72, 0.98),
        (0.10, 0.68),
        (0.46, 1.08),
        (0.20, 0.46),
        (0.0, 0.15),
    ]
    points: Path = []
    for start, end in zip(vertices, vertices[1:], strict=False):
        segment = _lerp(start, end, 6)
        points.extend(segment[:-1])
    points.append(vertices[-1])
    return ("butterfly", [points], True)


def fish() -> ShapeGen:
    # Detailed fish: body ellipse + dorsal fin + tail fin + eye.
    t = _samples(300)
    body: Path = [
        (math.cos(a) * (1 + 0.25 * math.cos(a)), 0.45 * math.sin(a) + 0.08 * math.sin(2 * a))
        for a in t
    ]
    # Tail fin — two spread arcs.
    tail_top: Path = _lerp((1.25, 0.0), (1.65, 0.45), 20)
    tail_edge: Path = _lerp((1.65, 0.45), (1.65, -0.45), 20)
    tail_bot: Path = _lerp((1.65, -0.45), (1.25, 0.0), 20)
    tail = tail_top + tail_edge[1:] + tail_bot[1:]
    # Dorsal fin.
    dorsal: Path = []
    for i in range(41):
        f = i / 40
        x = -0.3 + 0.5 * f
        y = 0.42 + 0.25 * math.sin(math.pi * f)
        dorsal.append((x, y))
    return ("fish", [body, tail, dorsal], False)


def arrow() -> ShapeGen:
    pts: Path = [
        (-1.0, 0.0), (0.6, 0.0), (0.6, 0.4), (1.0, 0.0),
        (0.6, -0.4), (0.6, 0.0), (-1.0, 0.0),
    ]
    return ("arrow", [pts], False)


def triangle() -> ShapeGen:
    pts: Path = [(-1.0, -0.6), (1.0, -0.6), (0.0, 1.0), (-1.0, -0.6)]
    return ("triangle", [pts], True)


def square() -> ShapeGen:
    pts: Path = [(-1.0, -1.0), (1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0)]
    return ("square", [pts], True)


def cat() -> ShapeGen:
    """Single-stroke cat-head silhouette with unmistakable pointed ears."""
    vertices: Path = [
        (0.0, -0.92),
        (-0.38, -0.82),
        (-0.68, -0.56),
        (-0.82, -0.18),
        (-0.78, 0.30),
        (-0.92, 0.98),
        (-0.34, 0.66),
        (0.0, 0.72),
        (0.34, 0.66),
        (0.92, 0.98),
        (0.78, 0.30),
        (0.82, -0.18),
        (0.68, -0.56),
        (0.38, -0.82),
        (0.0, -0.92),
    ]
    points: Path = []
    for start, end in zip(vertices, vertices[1:], strict=False):
        points.extend(_lerp(start, end, 3)[:-1])
    points.append(vertices[-1])
    return ("cat", [points], True)


def dog() -> ShapeGen:
    """Single-stroke side-view dog with raised tail, muzzle, ear, and legs."""
    vertices: Path = [
        (-1.0, 0.58),
        (-0.74, 0.16),
        (-0.56, 0.34),
        (0.20, 0.34),
        (0.40, 0.62),
        (0.58, 0.42),
        (0.80, 0.36),
        (1.0, 0.22),
        (0.78, 0.10),
        (0.54, 0.14),
        (0.42, -0.18),
        (0.48, -0.72),
        (0.18, -0.72),
        (0.08, -0.26),
        (-0.30, -0.26),
        (-0.38, -0.72),
        (-0.68, -0.72),
        (-0.62, -0.08),
        (-0.80, 0.10),
        (-1.0, 0.58),
    ]
    points: Path = []
    for start, end in zip(vertices, vertices[1:], strict=False):
        points.extend(_lerp(start, end, 3)[:-1])
    points.append(vertices[-1])
    return ("dog", [points], True)


def diamond() -> ShapeGen:
    pts: Path = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0), (0.0, 1.0)]
    return ("diamond", [pts], True)


def moon() -> ShapeGen:
    # Crescent moon with high-detail arcs.
    t_outer = [math.pi * 0.3 + math.pi * 1.4 * i / 200 for i in range(201)]
    outer = [(math.cos(a) * 0.9, math.sin(a) * 0.9) for a in t_outer]
    t_inner = [math.pi * 0.3 + math.pi * 1.4 * i / 200 for i in range(201)]
    inner = [(math.cos(a) * 0.7 + 0.25, math.sin(a) * 0.75) for a in reversed(t_inner)]
    pts: Path = outer + inner
    return ("moon", [pts], True)


def flower() -> ShapeGen:
    # 5-petal flower with smooth, well-defined petals.
    t = _samples(300)
    pts: Path = []
    for a in t:
        r = 0.45 + 0.40 * abs(math.cos(2.5 * a))
        pts.append((r * math.cos(a), r * math.sin(a)))
    return ("flower", [pts], True)


def tree() -> ShapeGen:
    # One continuous silhouette. The former closed canopy + separate trunk
    # forced an unavoidable transfer line through the drawing and produced a
    # tangled, open route on real streets.
    vertices: Path = [
        (0.0, 1.0),
        (-0.18, 0.74),
        (-0.48, 0.84),
        (-0.42, 0.56),
        (-0.76, 0.58),
        (-0.58, 0.30),
        (-0.90, 0.16),
        (-0.55, -0.02),
        (-0.68, -0.30),
        (-0.22, -0.28),
        (-0.18, -0.92),
        (0.18, -0.92),
        (0.22, -0.28),
        (0.68, -0.30),
        (0.55, -0.02),
        (0.90, 0.16),
        (0.58, 0.30),
        (0.76, 0.58),
        (0.42, 0.56),
        (0.48, 0.84),
        (0.18, 0.74),
        (0.0, 1.0),
    ]
    points: Path = []
    for start, end in zip(vertices, vertices[1:], strict=False):
        points.extend(_lerp(start, end, 3)[:-1])
    points.append(vertices[-1])
    return ("tree", [points], True)


def bird() -> ShapeGen:
    # Flying bird silhouette: spread wings + body.
    t = _samples(200)
    body: Path = [(0.5 * math.cos(a), 0.15 * math.sin(a) + 0.02 * math.sin(2 * a)) for a in t]
    # Left wing (spread up).
    lw: Path = []
    for i in range(51):
        f = i / 50
        x = 0.0 - 1.0 * f
        y = 0.05 + 0.45 * math.sin(math.pi * f) * (1 - 0.3 * f)
        lw.append((x, y))
    # Right wing (spread up).
    rw: Path = []
    for i in range(51):
        f = i / 50
        x = 0.0 + 1.0 * f
        y = 0.05 + 0.45 * math.sin(math.pi * f) * (1 - 0.3 * f)
        rw.append((x, y))
    # Tail.
    tail: Path = _lerp((-0.5, 0.0), (-0.85, 0.2), 10) + _lerp((-0.85, 0.2), (-0.85, -0.15), 8) + _lerp((-0.85, -0.15), (-0.5, 0.0), 10)
    return ("bird", [body, lw, rw, tail], False)


def anchor() -> ShapeGen:
    # Detailed anchor: ring + shank + stock + curved flukes.
    ring: Path = [(0.05 + 0.15 * math.cos(a), 0.85 + 0.15 * math.sin(a)) for a in _samples(100)]
    shank: Path = _lerp((0.05, 0.7), (0.05, -0.5), 30)
    stock: Path = _lerp((-0.25, 0.55), (0.35, 0.55), 20)
    # Curved flukes (bottom arc).
    flukes: Path = []
    t = [math.pi + 0.3 + (math.pi - 0.6) * i / 80 for i in range(81)]
    for a in t:
        r = 0.6
        x = r * math.cos(a)
        y = -0.5 + r * 0.35 * math.sin(a)
        flukes.append((x, y))
    flukes += _lerp((flukes[-1][0], flukes[-1][1]), (0.05, -0.5), 15)
    return ("anchor", [ring, shank, stock, flukes], False)


def cross() -> ShapeGen:
    # Plus-sign cross with rounded corners.
    pts: Path = [
        (-0.2, 0.6), (0.2, 0.6), (0.2, 0.2), (0.6, 0.2),
        (0.6, -0.2), (0.2, -0.2), (0.2, -0.6), (-0.2, -0.6),
        (-0.2, -0.2), (-0.6, -0.2), (-0.6, 0.2), (-0.2, 0.2),
        (-0.2, 0.6),
    ]
    return ("cross", [pts], True)


def infinity() -> ShapeGen:
    # Lemniscate (figure-eight / infinity symbol) — high detail.
    t = _samples(300)
    pts: Path = []
    for a in t:
        s = math.sin(a)
        c = math.cos(a)
        denom = 1 + s * s
        pts.append((c / denom, s * c / denom))
    return ("infinity", [pts], True)


# --------------------------------------------------------------------------- #
# New shapes — anatomically detailed
# --------------------------------------------------------------------------- #
def rabbit() -> ShapeGen:
    # Rabbit: round body + head + two long ears + tail.
    t = _samples(200)
    body: Path = [(0.55 * math.cos(a), 0.35 * math.sin(a) - 0.1) for a in t]
    head: Path = [(0.35 * math.cos(a) + 0.45, 0.28 * math.sin(a) + 0.35) for a in _samples(150)]
    # Left ear (long, curved).
    left_ear: Path = []
    for i in range(41):
        f = i / 40
        x = 0.35 + 0.12 * f + 0.05 * math.sin(math.pi * f)
        y = 0.55 + 0.55 * f
        left_ear.append((x, y))
    left_ear += [(0.35 + 0.12 + 0.05, 0.55 + 0.55), (0.35, 0.55)]
    # Right ear.
    right_ear: Path = []
    for i in range(41):
        f = i / 40
        x = 0.55 + 0.12 * f - 0.05 * math.sin(math.pi * f)
        y = 0.55 + 0.55 * f
        right_ear.append((x, y))
    right_ear += [(0.55 + 0.12 - 0.05, 0.55 + 0.55), (0.55, 0.55)]
    # Tail (small circle).
    tail: Path = [(-0.5 + 0.1 * math.cos(a), -0.1 + 0.1 * math.sin(a)) for a in _samples(60)]
    return ("rabbit", [body, head, left_ear, right_ear, tail], False)


def horse() -> ShapeGen:
    # Horse head silhouette with mane.
    # Main head outline (side view, facing right).
    head: Path = []
    t = _samples(200)
    for a in t:
        # Elongated snout + rounded jaw.
        x = 0.8 * math.cos(a) + 0.1 * math.cos(2 * a)
        y = 0.5 * math.sin(a) + 0.08 * math.sin(3 * a)
        head.append((x, y))
    # Mane (curved spikes along the top).
    mane: Path = []
    for i in range(41):
        f = i / 40
        x = -0.6 + 0.5 * f
        y = 0.45 + 0.25 * math.sin(math.pi * f) + 0.05 * math.sin(4 * math.pi * f)
        mane.append((x, y))
    mane += _lerp(mane[-1], (-0.6, 0.45), 15)
    # Ear.
    ear: Path = _lerp((-0.2, 0.45), (-0.35, 0.75), 10) + _lerp((-0.35, 0.75), (0.0, 0.5), 10)
    return ("horse", [head, mane, ear], False)


def dolphin() -> ShapeGen:
    # Dolphin: curved body + dorsal fin + tail flukes.
    t = _samples(300)
    body: Path = []
    for a in t:
        # Streamlined body curve.
        x = 0.9 * math.cos(a)
        y = 0.25 * math.sin(a) + 0.05 * math.sin(2 * a) * math.cos(a)
        body.append((x, y))
    # Dorsal fin.
    dorsal: Path = []
    for i in range(31):
        f = i / 30
        x = -0.1 + 0.3 * f
        y = 0.22 + 0.3 * math.sin(math.pi * f)
        dorsal.append((x, y))
    dorsal += _lerp(dorsal[-1], (-0.1, 0.22), 15)
    # Tail flukes.
    tail: Path = _lerp((-0.9, 0.0), (-1.15, 0.25), 12) + _lerp((-1.15, 0.25), (-1.1, 0.0), 8)
    tail += _lerp((-1.1, 0.0), (-1.15, -0.25), 8) + _lerp((-1.15, -0.25), (-0.9, 0.0), 12)
    # Beak/nose hint.
    beak: Path = _lerp((0.9, 0.05), (1.05, 0.02), 10) + _lerp((1.05, 0.02), (0.9, -0.05), 10)
    return ("dolphin", [body, dorsal, tail, beak], False)


def dragon() -> ShapeGen:
    # Stylised dragon: serpentine body + wings + head.
    t = _samples(300)
    body: Path = []
    for a in t:
        # Wavy serpentine curve.
        x = 0.7 * math.cos(a)
        y = 0.3 * math.sin(a) + 0.1 * math.sin(3 * a)
        body.append((x, y))
    # Left wing.
    lw: Path = []
    for i in range(51):
        f = i / 50
        x = -0.2 - 0.7 * f
        y = 0.1 + 0.6 * math.sin(math.pi * f) * (1 - 0.2 * f)
        lw.append((x, y))
    lw += _lerp(lw[-1], (-0.2, 0.1), 20)
    # Right wing.
    rw: Path = []
    for i in range(51):
        f = i / 50
        x = 0.2 + 0.7 * f
        y = 0.1 + 0.6 * math.sin(math.pi * f) * (1 - 0.2 * f)
        rw.append((x, y))
    rw += _lerp(rw[-1], (0.2, 0.1), 20)
    # Head (small circle at top).
    head: Path = [(0.1 * math.cos(a), 0.55 + 0.12 * math.sin(a)) for a in _samples(80)]
    # Tail.
    tail: Path = _lerp((-0.7, 0.0), (-1.0, 0.3), 15) + _lerp((-1.0, 0.3), (-1.1, -0.1), 10) + _lerp((-1.1, -0.1), (-0.7, 0.0), 15)
    return ("dragon", [body, lw, rw, head, tail], False)


def crown() -> ShapeGen:
    # Crown with 5 points and a base band.
    pts: Path = []
    # Base line left to right.
    pts += _lerp((-0.8, -0.3), (-0.8, 0.1), 10)
    # 5 spikes with rounded tops.
    spike_pts = [(-0.8, 0.1), (-0.6, 0.7), (-0.4, 0.2), (-0.2, 0.8), (0.0, 0.2),
                 (0.2, 0.8), (0.4, 0.2), (0.6, 0.7), (0.8, 0.1)]
    for i in range(len(spike_pts) - 1):
        a, b = spike_pts[i], spike_pts[i + 1]
        n = 25 if i % 2 == 0 else 15  # more points on the spike up
        pts += _lerp(a, b, n)[:-1]
    pts.append(spike_pts[-1])
    # Down and close the base.
    pts += _lerp((0.8, 0.1), (0.8, -0.3), 10)
    pts += _lerp((0.8, -0.3), (-0.8, -0.3), 20)
    return ("crown", [pts], True)


def key() -> ShapeGen:
    # Key: decorative bow (ring) + shank + teeth.
    bow: Path = [(-0.55 + 0.25 * math.cos(a), 0.0 + 0.25 * math.sin(a)) for a in _samples(100)]
    shank: Path = _lerp((-0.3, 0.0), (0.8, 0.0), 30)
    # Teeth (bitting).
    teeth: Path = _lerp((0.8, 0.0), (0.8, 0.15), 5) + _lerp((0.8, 0.15), (0.7, 0.15), 8)
    teeth += _lerp((0.7, 0.15), (0.7, 0.0), 5) + _lerp((0.7, 0.0), (0.6, 0.0), 8)
    teeth += _lerp((0.6, 0.0), (0.6, 0.2), 5) + _lerp((0.6, 0.2), (0.45, 0.2), 10)
    teeth += _lerp((0.45, 0.2), (0.45, 0.0), 5) + _lerp((0.45, 0.0), (0.8, 0.0), 20)
    return ("key", [bow, shank, teeth], False)


def mug() -> ShapeGen:
    # Coffee mug: rounded body + handle.
    t = _samples(200)
    body: Path = []
    for a in t:
        x = 0.5 * math.cos(a)
        y = 0.55 * math.sin(a) - 0.1
        body.append((x, y))
    # Handle (C-shape on the right).
    handle: Path = []
    for i in range(61):
        a = -math.pi / 2 + math.pi * i / 60
        x = 0.5 + 0.2 + 0.15 * math.cos(a)
        y = 0.1 + 0.2 * math.sin(a)
        handle.append((x, y))
    return ("mug", [body, handle], False)


def skull() -> ShapeGen:
    # Skull: cranium + jaw + eye sockets.
    t = _samples(250)
    cranium: Path = []
    for a in t:
        r = 0.6 + 0.02 * math.cos(6 * a)
        x = r * math.cos(a)
        y = r * math.sin(a) + 0.15
        cranium.append((x, y))
    # Jaw (smaller rounded triangle at the bottom).
    jaw: Path = []
    for i in range(81):
        f = i / 80
        a = math.pi + math.pi * f
        x = 0.3 * math.cos(a)
        y = -0.35 + 0.2 * math.sin(a) * (1 - 0.3 * f)
        jaw.append((x, y))
    # Left eye socket.
    left_eye: Path = [(-0.2 + 0.12 * math.cos(a), 0.15 + 0.12 * math.sin(a)) for a in _samples(60)]
    # Right eye socket.
    right_eye: Path = [(0.2 + 0.12 * math.cos(a), 0.15 + 0.12 * math.sin(a)) for a in _samples(60)]
    return ("skull", [cranium, jaw, left_eye, right_eye], False)


def note() -> ShapeGen:
    # Musical note (eighth note): note head + stem + flag.
    # Note head (oval, tilted).
    head: Path = []
    t = _samples(80)
    for a in t:
        x = -0.4 + 0.2 * math.cos(a) * math.cos(0.3) - 0.12 * math.sin(a) * math.sin(0.3)
        y = -0.4 + 0.2 * math.cos(a) * math.sin(0.3) + 0.12 * math.sin(a) * math.cos(0.3)
        head.append((x, y))
    # Stem.
    stem: Path = _lerp((-0.22, -0.32), (-0.22, 0.6), 25)
    # Flag.
    flag: Path = []
    for i in range(41):
        f = i / 40
        x = -0.22 + 0.35 * f
        y = 0.6 - 0.3 * f * f
        flag.append((x, y))
    flag += _lerp(flag[-1], (-0.22, 0.35), 15)
    return ("note", [head, stem, flag], False)


def lightning() -> ShapeGen:
    # Lightning bolt — zigzag with thick stroke feel.
    pts: Path = [
        (0.2, 1.0), (0.0, 1.0), (0.3, 0.1), (-0.1, 0.1),
        (0.3, -1.0), (0.1, -0.1), (0.5, -0.1), (0.2, 1.0),
    ]
    return ("lightning", [pts], True)


def helix() -> ShapeGen:
    # DNA helix — two intertwined sinusoidal curves.
    t = [2 * math.pi * i / 200 for i in range(201)]
    strand1: Path = [(0.4 * math.sin(a), 2 * a / (2 * math.pi) - 1.0) for a in t]
    strand2: Path = [(-0.4 * math.sin(a), 2 * a / (2 * math.pi) - 1.0) for a in t]
    # Rungs connecting them.
    rungs: list[Path] = []
    for i in range(0, 201, 20):
        rungs.append([strand1[i], strand2[i]])
    return ("helix", [strand1, strand2] + rungs, False)


def sailboat() -> ShapeGen:
    # Sailboat: hull + two sails + mast.
    hull: Path = _lerp((-0.8, -0.1), (0.8, -0.1), 25)
    hull += _lerp((0.8, -0.1), (0.5, -0.35), 12)
    hull += _lerp((0.5, -0.35), (-0.5, -0.35), 15)
    hull += _lerp((-0.5, -0.35), (-0.8, -0.1), 12)
    # Mast.
    mast: Path = _lerp((0.0, -0.1), (0.0, 0.8), 15)
    # Main sail (right triangle).
    main_sail: Path = _lerp((0.0, 0.8), (0.0, 0.0), 15) + _lerp((0.0, 0.0), (0.65, 0.0), 15) + _lerp((0.65, 0.0), (0.0, 0.8), 20)
    # Jib (front sail, left triangle).
    jib: Path = _lerp((0.0, 0.8), (0.0, 0.0), 15) + _lerp((0.0, 0.0), (-0.5, 0.0), 15) + _lerp((-0.5, 0.0), (0.0, 0.8), 20)
    return ("sailboat", [hull, mast, main_sail, jib], False)


def mountain() -> ShapeGen:
    # Mountain range: two peaks with snow caps.
    pts: Path = []
    # Left peak.
    pts += _lerp((-1.0, -0.3), (-0.4, 0.7), 30)
    # Snow cap (zigzag).
    pts += [(-0.4, 0.7), (-0.35, 0.6), (-0.3, 0.65), (-0.25, 0.55), (-0.2, 0.6)]
    # Valley.
    pts += _lerp((-0.2, 0.6), (0.1, 0.2), 15)
    # Right peak.
    pts += _lerp((0.1, 0.2), (0.6, 0.85), 25)
    # Snow cap.
    pts += [(0.6, 0.85), (0.65, 0.75), (0.7, 0.8), (0.75, 0.7), (0.8, 0.75)]
    # Down to base.
    pts += _lerp((0.8, 0.75), (1.0, -0.3), 20)
    # Base line.
    pts += _lerp((1.0, -0.3), (-1.0, -0.3), 30)
    return ("mountain", [pts], True)


def sun() -> ShapeGen:
    # Sun: central disc + 8 triangular rays.
    t = _samples(200)
    disc: Path = [(0.35 * math.cos(a), 0.35 * math.sin(a)) for a in t]
    # 8 rays as separate sub-paths.
    rays: list[Path] = []
    for i in range(8):
        a = 2 * math.pi * i / 8
        inner = 0.4
        outer = 0.85
        spread = 0.12
        ray: Path = [
            (inner * math.cos(a - spread), inner * math.sin(a - spread)),
            (outer * math.cos(a), outer * math.sin(a)),
            (inner * math.cos(a + spread), inner * math.sin(a + spread)),
        ]
        rays.append(ray)
    return ("sun", [disc] + rays, False)


def wave() -> ShapeGen:
    # A single continuous swell. The former three parallel strokes required
    # long transfer routes between disconnected lines and became unreadable on
    # streets. Amplitude tapers at both ends to retain a clear wave silhouette.
    samples = [i / 160 for i in range(161)]
    points: Path = []
    for fraction in samples:
        envelope = math.sin(math.pi * fraction) ** 0.7
        x = -1.0 + 2.0 * fraction
        y = 0.42 * envelope * math.sin(2.5 * math.pi * fraction)
        points.append((x, y))
    return ("wave", [points], False)


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
SHAPES: dict[str, Callable[[], ShapeGen]] = {g()[0]: g for g in [
    heart, star, circle, butterfly, fish, arrow, triangle, square, cat, dog, diamond,
    moon, flower, tree, bird, anchor, cross, infinity,
    rabbit, horse, dolphin, dragon, crown, key, mug, skull, note, lightning,
    helix, sailboat, mountain, sun, wave,
]}

# Friendly keyword -> canonical name lookup (used by IntentAgent fallback).
KEYWORDS: dict[str, str] = {
    "heart": "heart", "love": "heart", "valentine": "heart",
    "star": "star", "stars": "star",
    "circle": "circle", "ring": "circle", "o": "circle",
    "butterfly": "butterfly",
    "fish": "fish",
    "arrow": "arrow",
    "triangle": "triangle",
    "square": "square", "box": "square",
    "cat": "cat", "kitten": "cat",
    "dog": "dog", "puppy": "dog", "hound": "dog",
    "diamond": "diamond",
    "moon": "moon", "crescent": "moon",
    "flower": "flower", "petal": "flower",
    "tree": "tree",
    "bird": "bird", "dove": "bird",
    "anchor": "anchor", "ship": "anchor",
    "cross": "cross", "plus": "cross",
    "infinity": "infinity", "eight": "infinity", "figure8": "infinity",
    "rabbit": "rabbit", "bunny": "rabbit", "hare": "rabbit",
    "horse": "horse", "pony": "horse", "equine": "horse",
    "dolphin": "dolphin", "porpoise": "dolphin",
    "dragon": "dragon",
    "crown": "crown", "king": "crown",
    "key": "key",
    "mug": "mug", "cup": "mug", "coffee": "mug",
    "skull": "skull", "death": "skull",
    "note": "note", "music": "note", "musical": "note",
    "lightning": "lightning", "bolt": "lightning", "thunder": "lightning",
    "helix": "helix", "dna": "helix",
    "sailboat": "sailboat", "boat": "sailboat", "sailing": "sailboat",
    "mountain": "mountain", "peak": "mountain", "mountains": "mountain",
    "sun": "sun", "sunshine": "sun",
    "wave": "wave", "ocean": "wave", "sea": "wave",
}


def get_shape(name: str) -> ShapeGen | None:
    """Return ``(name, paths, closed)`` for a known shape, else None."""
    name = name.lower().strip()
    gen = SHAPES.get(name)
    if gen is None:
        return None
    return gen()


def find_by_keyword(text: str) -> ShapeGen | None:
    """Match whole keywords in ``text`` against the friendly-name map.

    Whole-token matching is essential for short aliases: the former substring
    search interpreted the ``"o"`` alias as a circle in prompts such as
    ``"cat in London"`` before it ever reached the requested ``"cat"``.
    """
    low = text.lower()
    for keyword in sorted(KEYWORDS, key=len, reverse=True):
        pattern = rf"(?<!\w){re.escape(keyword)}(?!\w)"
        if re.search(pattern, low):
            name = KEYWORDS[keyword]
            return get_shape(name)
    return None
