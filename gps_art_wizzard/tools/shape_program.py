"""Compile and preview bounded, route-native AI drawing programs.

The model describes meaningful strokes and cubic curves instead of emitting an
unchecked cloud of points.  Compilation is deterministic, deliberately small,
and has no image-library dependency so it also works in the production image.
"""

from __future__ import annotations

import base64
import binascii
import math
import struct
import zlib
from dataclasses import dataclass, field

from . import geo


@dataclass
class CompiledShapeProgram:
    paths: list[geo.Path]
    closed: bool
    feature_coverage: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def compile_shape_program(
    value: object,
    *,
    required_feature_ids: set[str] | None = None,
) -> CompiledShapeProgram:
    """Validate and compile one untrusted model drawing program."""

    if not isinstance(value, dict):
        raise ValueError("shape program must be an object")
    raw_strokes = value.get("strokes")
    if not isinstance(raw_strokes, list) or not 1 <= len(raw_strokes) <= 8:
        raise ValueError("shape program needs one to eight strokes")
    closed = value.get("closed")
    if not isinstance(closed, bool):
        raise ValueError("shape program closed flag must be boolean")

    paths: list[geo.Path] = []
    feature_lengths: dict[str, float] = {}
    total_commands = 0
    for stroke_index, raw_stroke in enumerate(raw_strokes):
        if not isinstance(raw_stroke, dict) or not isinstance(raw_stroke.get("commands"), list):
            raise ValueError(f"stroke {stroke_index + 1} needs a commands array")
        commands = raw_stroke["commands"]
        total_commands += len(commands)
        path: geo.Path = []
        start: tuple[float, float] | None = None
        for command_index, raw_command in enumerate(commands):
            if not isinstance(raw_command, dict):
                raise ValueError("every drawing command must be an object")
            op = raw_command.get("op")
            points = raw_command.get("points")
            feature_id = raw_command.get("feature_id")
            if feature_id is not None and not isinstance(feature_id, str):
                raise ValueError("command feature_id must be text or null")
            expected_points = {"move": 1, "line": 1, "curve": 3, "close": 0}
            if op not in expected_points:
                raise ValueError(f"unsupported drawing command {op!r}")
            if not isinstance(points, list) or len(points) != expected_points[op]:
                raise ValueError(f"{op} command needs {expected_points[op]} point(s)")
            parsed = [_bounded_point(point) for point in points]
            if op == "move":
                if path:
                    raise ValueError("move is allowed only at the start of a stroke")
                start = parsed[0]
                path.append(start)
                continue
            if not path or start is None:
                raise ValueError("each stroke must begin with move")
            previous = path[-1]
            segment: geo.Path
            if op == "line":
                segment = [previous, parsed[0]]
            elif op == "curve":
                segment = _sample_cubic(previous, parsed[0], parsed[1], parsed[2])
            else:
                if command_index != len(commands) - 1:
                    raise ValueError("close must be the final command of a stroke")
                segment = [previous, start]
            for point in segment[1:]:
                if point != path[-1]:
                    path.append(point)
            if feature_id:
                feature_lengths[feature_id] = feature_lengths.get(feature_id, 0.0) + _path_length(segment)
        if len(path) < 3:
            raise ValueError("each stroke needs at least three compiled points")
        if closed and path[0] != path[-1]:
            path.append(path[0])
        paths.append(path)

    if not 6 <= total_commands <= 96:
        raise ValueError("shape program needs 6 to 96 meaningful commands")
    total_length = sum(_path_length(path) for path in paths)
    if total_length <= 1e-9:
        raise ValueError("shape program has no drawable length")
    coverage = {
        feature_id: length / total_length
        for feature_id, length in feature_lengths.items()
    }
    warnings: list[str] = []
    missing = sorted((required_feature_ids or set()) - set(feature_lengths))
    if missing:
        warnings.append("missing feature spans: " + ", ".join(missing))
    tiny = sorted(
        feature_id
        for feature_id in (required_feature_ids or set())
        if 0 < coverage.get(feature_id, 0.0) < 0.025
    )
    if tiny:
        warnings.append("features too small for routing: " + ", ".join(tiny))
    return CompiledShapeProgram(paths, closed, coverage, warnings)


def local_program_score(program: CompiledShapeProgram, required_feature_ids: set[str]) -> float:
    """Cheap route/readability prior used when no independent vision model exists."""

    present = sum(program.feature_coverage.get(feature_id, 0.0) >= 0.025 for feature_id in required_feature_ids)
    cue_score = present / max(1, len(required_feature_ids))
    stroke_score = max(0.0, 1.0 - max(0, len(program.paths) - 2) * 0.18)
    point_count = sum(len(path) for path in program.paths)
    density_score = 1.0 if 18 <= point_count <= 180 else 0.75
    return 0.65 * cue_score + 0.2 * stroke_score + 0.15 * density_score


def render_paths_png_data_url(
    paths: list[geo.Path],
    *,
    size: int = 256,
    padding: int = 22,
) -> str:
    """Render a black route thumbnail to an inline PNG for semantic review."""

    if not paths or not any(paths):
        raise ValueError("cannot render an empty shape")
    size = max(96, min(512, int(size)))
    pixels = bytearray([255]) * (size * size)
    normalised = geo.normalize_shape(paths)
    points = [point for path in normalised for point in path]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min((size - 2 * padding) / span_x, (size - 2 * padding) / span_y)
    offset_x = (size - span_x * scale) / 2
    offset_y = (size - span_y * scale) / 2

    def project(point: tuple[float, float]) -> tuple[int, int]:
        x = round(offset_x + (point[0] - min_x) * scale)
        y = round(size - 1 - (offset_y + (point[1] - min_y) * scale))
        return x, y

    for path in normalised:
        for start, end in zip(path, path[1:], strict=False):
            _draw_thick_line(pixels, size, project(start), project(end), radius=2)
    encoded = base64.b64encode(_encode_grayscale_png(pixels, size, size)).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _bounded_point(value: object) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError("drawing point must contain exactly x and y")
    if isinstance(value[0], bool) or isinstance(value[1], bool):
        raise ValueError("drawing coordinates must be numbers")
    try:
        point = float(value[0]), float(value[1])
    except (TypeError, ValueError) as exc:
        raise ValueError("drawing coordinates must be numbers") from exc
    if not all(math.isfinite(coordinate) and abs(coordinate) <= 10 for coordinate in point):
        raise ValueError("drawing coordinates must stay between -10 and 10")
    return point


def _sample_cubic(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
) -> geo.Path:
    control_length = math.dist(p0, p1) + math.dist(p1, p2) + math.dist(p2, p3)
    chord = math.dist(p0, p3)
    subdivisions = max(4, min(10, math.ceil(3 + max(0.0, control_length - chord))))
    points: geo.Path = []
    for index in range(subdivisions + 1):
        t = index / subdivisions
        u = 1.0 - t
        points.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return points


def _path_length(path: geo.Path) -> float:
    return sum(math.dist(start, end) for start, end in zip(path, path[1:], strict=False))


def _draw_thick_line(
    pixels: bytearray,
    size: int,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    radius: int,
) -> None:
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    while True:
        for oy in range(-radius, radius + 1):
            for ox in range(-radius, radius + 1):
                if ox * ox + oy * oy > radius * radius:
                    continue
                x, y = x0 + ox, y0 + oy
                if 0 <= x < size and 0 <= y < size:
                    pixels[y * size + x] = 20
        if x0 == x1 and y0 == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x0 += sx
        if twice <= dx:
            error += dx
            y0 += sy


def _encode_grayscale_png(pixels: bytearray, width: int, height: int) -> bytes:
    rows = b"".join(
        b"\x00" + bytes(pixels[row * width : (row + 1) * width])
        for row in range(height)
    )

    def chunk(kind: bytes, data: bytes) -> bytes:
        checksum = binascii.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, level=6))
        + chunk(b"IEND", b"")
    )
