"""Small exact-enough plane geometry helpers (no shapely dependency)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from media.render.contracts import Point

EPS = 1e-9


def signed_area(points: Sequence[Point]) -> float:
    """Shoelace area; positive when the points run counter-clockwise."""
    total = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def area(points: Sequence[Point]) -> float:
    return abs(signed_area(points))


def ccw(points: Sequence[Point]) -> list[Point]:
    """The same polygon, ordered counter-clockwise."""
    pts = [(float(x), float(y)) for x, y in points]
    return pts if signed_area(pts) > 0 else list(reversed(pts))


def edges(points: Sequence[Point]) -> list[tuple[Point, Point]]:
    n = len(points)
    return [(points[i], points[(i + 1) % n]) for i in range(n)]


def length(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def on_segment(p: Point, a: Point, b: Point, tol: float = 1e-7) -> bool:
    if abs(_cross(a, b, p)) > tol * max(1.0, length(a, b)):
        return False
    return (
        min(a[0], b[0]) - tol <= p[0] <= max(a[0], b[0]) + tol
        and min(a[1], b[1]) - tol <= p[1] <= max(a[1], b[1]) + tol
    )


def segments_intersect(a: Point, b: Point, c: Point, d: Point) -> bool:
    """True when closed segments ab and cd share any point."""
    d1 = _cross(c, d, a)
    d2 = _cross(c, d, b)
    d3 = _cross(a, b, c)
    d4 = _cross(a, b, d)
    if ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and (
        (d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS)
    ):
        return True
    return (
        on_segment(a, c, d)
        or on_segment(b, c, d)
        or on_segment(c, a, b)
        or on_segment(d, a, b)
    )


def is_simple(points: Sequence[Point]) -> bool:
    """No two non-adjacent edges touch, and adjacent edges meet only at their shared corner."""
    es = edges(points)
    n = len(es)
    for i in range(n):
        for j in range(i + 1, n):
            adjacent = j == i + 1 or (i == 0 and j == n - 1)
            a, b = es[i]
            c, d = es[j]
            if adjacent:
                # Adjacent edges share one corner; they must not fold back
                # over each other (the far end of one lying on the other).
                far_i, far_j = (a, d) if j == i + 1 else (b, c)
                if on_segment(far_i, c, d) or on_segment(far_j, a, b):
                    return False
                continue
            if segments_intersect(a, b, c, d):
                return False
    return True


def on_boundary(p: Point, points: Sequence[Point]) -> bool:
    return any(on_segment(p, a, b) for a, b in edges(points))


def inside_or_on(p: Point, points: Sequence[Point]) -> bool:
    if on_boundary(p, points):
        return True
    x, y = p
    inside = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def segment_inside(a: Point, b: Point, points: Sequence[Point], samples: int = 16) -> bool:
    return all(
        inside_or_on((a[0] + (b[0] - a[0]) * t / samples, a[1] + (b[1] - a[1]) * t / samples), points)
        for t in range(samples + 1)
    )


def centroid(points: Sequence[Point]) -> Point:
    a = signed_area(points)
    if abs(a) < EPS:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cy = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        f = x1 * y2 - x2 * y1
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    return (cx / (6 * a), cy / (6 * a))


def distance_to_segment(p: Point, a: Point, b: Point) -> float:
    seg = length(a, b)
    if seg < EPS:
        return length(p, a)
    t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (seg * seg)
    t = max(0.0, min(1.0, t))
    return length(p, (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))


def distance_to_boundary(p: Point, points: Sequence[Point]) -> float:
    return min(distance_to_segment(p, a, b) for a, b in edges(points))


def collinear(points: Sequence[Point]) -> bool:
    a = points[0]
    b = next((p for p in points[1:] if length(a, p) > EPS), None)
    if b is None:
        return True
    return all(abs(_cross(a, b, p)) <= 1e-9 * max(1.0, length(a, b)) for p in points)


def unit(a: Point, b: Point) -> Point:
    d = length(a, b)
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def is_nice(value: float) -> bool:
    """Whole numbers or one decimal place: what a textbook label shows."""
    return abs(value - round(value, 1)) < 1e-6


def format_number(value: float) -> str:
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 1e-9:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


__all__ = [
    "area",
    "ccw",
    "centroid",
    "collinear",
    "edges",
    "format_number",
    "inside_or_on",
    "is_nice",
    "is_simple",
    "length",
    "on_boundary",
    "on_segment",
    "segment_inside",
    "segments_intersect",
    "signed_area",
    "unit",
]
