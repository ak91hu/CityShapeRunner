"""Single-stroke ("simplex") vector font for drawing text as GPS art.

Each glyph is a list of *strokes*; each stroke is a list of ``(x, y)`` points in
a 6 x 10 local box. :func:`text_to_shape` lays glyphs out left-to-right and
returns a list of sub-paths (one per stroke), so an intent like ``"draw AKOS
in Berlin"`` produces drawable letter outlines.

Curved strokes (5+ points) are Catmull-Rom smoothed at output so letters like
O, C, S read smoothly on the map instead of looking polygonal. Straight strokes
are densified so ORS has enough waypoints to follow the intended roads.
"""

from __future__ import annotations

from .geo import Path, catmull_rom_smooth, densify_path

Glyph = list[list[tuple[float, float]]]  # list of strokes

GLYPH_W = 6.0
GLYPH_H = 10.0

_DENSIFY_STEP = 0.5  # local-box units; ~1 point per 0.5 units of stroke length
_CURVE_THRESHOLD = 5  # strokes with >= this many points are treated as curves

FONT: dict[str, Glyph] = {
    "A": [[(0, 0), (3, 10), (6, 0)], [(1.2, 4), (4.8, 4)]],
    "B": [[(0, 0), (0, 10)], [(0, 10), (4.5, 10), (5.5, 8.5), (4, 7), (0, 7)],
          [(0, 7), (4.5, 7), (5.5, 4), (4, 0), (0, 0)]],
    "C": [[(5.5, 8), (3, 10), (1, 10), (0, 7), (0, 3), (1, 0), (3, 0), (5.5, 2)]],
    "D": [[(0, 0), (0, 10)], [(0, 10), (4, 10), (5.5, 7), (5.5, 3), (4, 0), (0, 0)]],
    "E": [[(5.5, 10), (0, 10), (0, 0), (5.5, 0)], [(0, 5), (3.5, 5)]],
    "F": [[(5.5, 10), (0, 10), (0, 0)], [(0, 5), (3.5, 5)]],
    "G": [[(5.5, 8), (3, 10), (1, 10), (0, 7), (0, 3), (1, 0), (4, 0), (5.5, 1.5), (5.5, 4), (3, 4)]],
    "H": [[(0, 0), (0, 10)], [(6, 0), (6, 10)], [(0, 5), (6, 5)]],
    "I": [[(0, 10), (6, 10)], [(3, 10), (3, 0)], [(0, 0), (6, 0)]],
    "J": [[(4, 10), (4, 2), (3, 0), (1, 0), (0, 2), (0, 4)]],
    "K": [[(0, 0), (0, 10)], [(6, 10), (0, 5), (6, 0)]],
    "L": [[(0, 10), (0, 0), (6, 0)]],
    "M": [[(0, 0), (0, 10), (3, 5), (6, 10), (6, 0)]],
    "N": [[(0, 0), (0, 10), (6, 0), (6, 10)]],
    "O": [[(0, 3), (0, 7), (1, 10), (5, 10), (6, 7), (6, 3), (5, 0), (1, 0), (0, 3)]],
    "P": [[(0, 0), (0, 10), (4, 10), (5.5, 8), (4, 6), (0, 6)]],
    "Q": [[(0, 3), (0, 7), (1, 10), (5, 10), (6, 7), (6, 3), (5, 0), (1, 0), (0, 3)],
          [(3.5, 2.5), (6, -0.5)]],
    "R": [[(0, 0), (0, 10), (4, 10), (5.5, 8), (4, 6), (0, 6)], [(3, 6), (6, 0)]],
    "S": [[(5.5, 8.5), (4, 10), (1.5, 10), (0, 7.5), (4, 6), (5.5, 4), (4, 0), (1.5, 0), (0, 1.5)]],
    "T": [[(0, 10), (6, 10)], [(3, 10), (3, 0)]],
    "U": [[(0, 10), (0, 3), (1, 0), (5, 0), (6, 3), (6, 10)]],
    "V": [[(0, 10), (3, 0), (6, 10)]],
    "W": [[(0, 10), (1.5, 0), (3, 7), (4.5, 0), (6, 10)]],
    "X": [[(0, 0), (6, 10)], [(0, 10), (6, 0)]],
    "Y": [[(0, 10), (3, 5), (6, 10)], [(3, 5), (3, 0)]],
    "Z": [[(0, 10), (6, 10), (0, 0), (6, 0)]],
    "0": [[(0, 3), (0, 7), (1, 10), (5, 10), (6, 7), (6, 3), (5, 0), (1, 0), (0, 3)]],
    "1": [[(1, 8), (3, 10), (3, 0)], [(1, 0), (5, 0)]],
    "2": [[(0, 8), (1, 10), (5, 10), (6, 8), (0, 0), (6, 0)]],
    "3": [[(0, 10), (6, 10), (3, 5), (6, 0), (0, 0)]],
    "4": [[(5, 0), (5, 10), (0, 4), (6, 4)]],
    "5": [[(6, 10), (0, 10), (0, 5), (4, 5), (6, 3), (4, 0), (0, 0)]],
    "6": [[(5, 10), (1, 10), (0, 7), (0, 3), (3, 0), (6, 1), (5, 5), (0, 5)]],
    "7": [[(0, 10), (6, 10), (2, 0)]],
    "8": [[(3, 10), (0, 8), (3, 6), (6, 8), (3, 10)], [(3, 6), (0, 4), (3, 0), (6, 4), (3, 6)]],
    "9": [[(6, 5), (0, 5), (0, 8), (3, 10), (6, 8), (6, 3), (3, 0), (0, 1)]],
    " ": [],  # space = blank glyph with width
    "-": [[(1, 5), (5, 5)]],
    "!": [[(3, 10), (3, 2)], [(3, 0), (3, 0)]],
    "?": [[(0, 8), (1, 10), (5, 10), (6, 8), (3, 5), (3, 2)], [(3, 0), (3, 0)]],
}


def _refine_stroke(stroke: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Densify a stroke; smooth it if it has enough points to be a curve."""
    if len(stroke) < 2:
        return list(stroke)
    densified = densify_path(stroke, max_step=_DENSIFY_STEP)
    if len(stroke) >= _CURVE_THRESHOLD:
        return catmull_rom_smooth(densified, closed=False, subdivisions=4)
    return densified


def text_to_shape(
    text: str, *, spacing: float = 1.5, line_height: float = 12.0, max_cols: int = 12
) -> tuple[list[Path], bool]:
    """Render ``text`` into a list of sub-paths in unit space (un-normalised).

    Long text wraps at ``max_cols`` characters per line. Returns ``(paths,
    closed=False)``. Curved strokes are spline-smoothed; straight strokes are
    densified so the road-snapper has enough waypoints to follow.
    """
    paths: list[Path] = []
    cursor_x = 0.0
    cursor_y = 0.0
    col = 0

    for ch in text:
        if ch == "\n" or col >= max_cols:
            cursor_y -= line_height
            cursor_x = 0.0
            col = 0
            if ch == "\n":
                continue
        upper = ch.upper()
        glyph = FONT.get(upper, [])
        for stroke in glyph:
            moved = [(cursor_x + x, cursor_y + y) for x, y in stroke]
            paths.append(_refine_stroke(moved))
        cursor_x += GLYPH_W + spacing
        col += 1

    if not paths:
        paths = [[(0.0, 0.0), (1.0, 0.0)]]
    return paths, False
