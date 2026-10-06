"""Typed render specs for code-drawn figures.

A spec describes one figure as data (points, values, steps); a family renderer
turns it into SVG deterministically. Families are kinds of drawing, not named
shapes: an L-shaped room is a ``polygon_area`` with six corner points.

Size caps live in the schemas so "reliable when small" is enforced, not hoped.
Geometry and arithmetic checks live in ``media.render.validate``.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

Family = Literal[
    "polygon_area",
    "number_line",
    "bar_chart",
    "function_graph",
    "flow",
    "cycle",
]
FAMILIES: tuple[str, ...] = (
    "polygon_area",
    "number_line",
    "bar_chart",
    "function_graph",
    "flow",
    "cycle",
)

Point = tuple[float, float]
ShortText = Annotated[str, Field(min_length=1, max_length=40)]
NodeText = Annotated[str, Field(min_length=1, max_length=60)]


class RenderSpecError(ValueError):
    """One structural problem with a spec, phrased so a repair call can fix it."""

    def __init__(self, code: str, path: str, message: str) -> None:
        self.code = code
        self.path = path
        self.message = message
        super().__init__(f"{code} at {path}: {message}")

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


class RenderLayoutError(RuntimeError):
    """A valid spec that cannot be laid out legibly at print-safe sizes."""

    code = "render_layout_failed"


class _Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- polygon_area -----------------------------------------------------------


class EdgeLabel(_Spec):
    """Label for edge ``i`` (from point ``i`` to point ``i + 1``, wrapping)."""

    edge: int = Field(ge=0)
    # computed: the renderer measures the edge and writes the length.
    # symbol: show ``text`` instead (an unknown such as "x" or "?").
    # hidden: deliberately unlabelled.
    kind: Literal["computed", "symbol", "hidden"] = "computed"
    text: ShortText | None = None


class Segment(_Spec):
    """A split line or height line drawn inside the shape."""

    start: Point
    end: Point
    style: Literal["solid", "dashed"] = "dashed"
    label: ShortText | None = None
    # Draw a right-angle mark where this endpoint meets the polygon boundary.
    right_angle_at: Literal["start", "end"] | None = None


class Region(_Spec):
    points: list[Point] = Field(min_length=3, max_length=12)
    label: ShortText | None = None
    shade: bool = True


class PolygonAreaSpec(_Spec):
    family: Literal["polygon_area"] = "polygon_area"
    points: list[Point] = Field(min_length=3, max_length=20)
    unit: Annotated[str, Field(max_length=8)] = ""
    edge_labels: list[EdgeLabel] = Field(default_factory=list, max_length=20)
    segments: list[Segment] = Field(default_factory=list, max_length=8)
    regions: list[Region] = Field(default_factory=list, max_length=6)
    mark_right_angles: bool = False


# --- number_line --------------------------------------------------------------


class NumberLinePoint(_Spec):
    value: float
    label: ShortText | None = None
    style: Literal["closed", "open"] = "closed"


class NumberLineJump(_Spec):
    start: float
    end: float
    label: ShortText | None = None


class NumberLineInterval(_Spec):
    """A shaded stretch; ``None`` means it runs off that end of the line."""

    start: float | None = None
    end: float | None = None
    start_closed: bool = True
    end_closed: bool = True
    label: ShortText | None = None


class NumberLineSpec(_Spec):
    family: Literal["number_line"] = "number_line"
    start: float
    end: float
    step: float = Field(gt=0)
    tick_format: Literal["integer", "decimal", "fraction"] = "integer"
    # Required for fraction ticks: label ticks as n/denominator.
    denominator: int | None = Field(default=None, ge=2, le=24)
    points: list[NumberLinePoint] = Field(default_factory=list, max_length=8)
    jumps: list[NumberLineJump] = Field(default_factory=list, max_length=8)
    intervals: list[NumberLineInterval] = Field(default_factory=list, max_length=3)


# --- bar_chart ------------------------------------------------------------------


class BarSeries(_Spec):
    name: ShortText | None = None
    values: list[float] = Field(min_length=1, max_length=12)


class BarChartSpec(_Spec):
    family: Literal["bar_chart"] = "bar_chart"
    categories: list[ShortText] = Field(min_length=1, max_length=12)
    series: list[BarSeries] = Field(min_length=1, max_length=3)
    x_label: ShortText | None = None
    y_label: ShortText | None = None
    y_max: float | None = Field(default=None, gt=0)
    y_step: float | None = Field(default=None, gt=0)
    orientation: Literal["vertical", "horizontal"] = "vertical"


# --- function_graph ---------------------------------------------------------------


class LinearCurve(_Spec):
    form: Literal["linear"] = "linear"
    m: float
    c: float
    label: ShortText | None = None


class QuadraticCurve(_Spec):
    form: Literal["quadratic"] = "quadratic"
    a: float
    b: float
    c: float
    label: ShortText | None = None


class PolylineCurve(_Spec):
    form: Literal["polyline"] = "polyline"
    points: list[Point] = Field(min_length=2, max_length=24)
    label: ShortText | None = None


Curve = Annotated[
    Union[LinearCurve, QuadraticCurve, PolylineCurve],
    Field(discriminator="form"),
]


class GraphPoint(_Spec):
    x: float
    y: float
    label: ShortText | None = None


class FunctionGraphSpec(_Spec):
    family: Literal["function_graph"] = "function_graph"
    x_range: Point
    y_range: Point
    x_step: float | None = Field(default=None, gt=0)
    y_step: float | None = Field(default=None, gt=0)
    grid: bool = True
    x_label: ShortText = "x"
    y_label: ShortText = "y"
    curves: list[Curve] = Field(default_factory=list, max_length=4)
    points: list[GraphPoint] = Field(default_factory=list, max_length=10)


# --- flow / cycle -------------------------------------------------------------------


class FlowNode(_Spec):
    id: Annotated[str, Field(min_length=1, max_length=24, pattern=r"^[A-Za-z0-9_-]+$")]
    text: NodeText
    kind: Literal["step", "decision", "terminal"] = "step"


class FlowEdge(_Spec):
    start: str
    end: str
    label: ShortText | None = None


class FlowSpec(_Spec):
    family: Literal["flow"] = "flow"
    nodes: list[FlowNode] = Field(min_length=2, max_length=8)
    edges: list[FlowEdge] = Field(default_factory=list, max_length=12)
    direction: Literal["vertical", "horizontal"] = "vertical"


class CycleSpec(_Spec):
    family: Literal["cycle"] = "cycle"
    nodes: list[NodeText] = Field(min_length=3, max_length=8)
    center_label: ShortText | None = None
    clockwise: bool = True


# --- union and builder result ----------------------------------------------------------

RenderSpec = Annotated[
    Union[
        PolygonAreaSpec,
        NumberLineSpec,
        BarChartSpec,
        FunctionGraphSpec,
        FlowSpec,
        CycleSpec,
    ],
    Field(discriminator="family"),
]


class RenderSpecResult(_Spec):
    """What the spec builder returns: a family plus its spec, or ``none``."""

    family: Literal[
        "polygon_area",
        "number_line",
        "bar_chart",
        "function_graph",
        "flow",
        "cycle",
        "none",
    ]
    spec: RenderSpec | None = None
    reason: Annotated[str, Field(max_length=300)] = ""

    @model_validator(mode="after")
    def _family_matches_spec(self) -> RenderSpecResult:
        if self.family == "none":
            if self.spec is not None:
                raise ValueError("family 'none' must not carry a spec")
        elif self.spec is None:
            raise ValueError(f"family {self.family!r} requires a spec")
        elif self.spec.family != self.family:
            raise ValueError(
                f"family {self.family!r} does not match spec family {self.spec.family!r}"
            )
        return self


__all__ = [
    "FAMILIES",
    "BarChartSpec",
    "BarSeries",
    "CycleSpec",
    "EdgeLabel",
    "Family",
    "FlowEdge",
    "FlowNode",
    "FlowSpec",
    "FunctionGraphSpec",
    "GraphPoint",
    "LinearCurve",
    "NumberLineInterval",
    "NumberLineJump",
    "NumberLinePoint",
    "NumberLineSpec",
    "PolygonAreaSpec",
    "PolylineCurve",
    "QuadraticCurve",
    "Region",
    "RenderLayoutError",
    "RenderSpec",
    "RenderSpecError",
    "RenderSpecResult",
    "Segment",
]
