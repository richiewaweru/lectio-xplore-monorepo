"""Turn a figure request into a typed render spec with one small LLM call.

Prompts are pure functions so they can be tested without a model. The model
only picks a family and fills its spec; it never writes SVG, HTML or code.
"""

from __future__ import annotations

from typing import Protocol

from core.llm.runner import RetryPolicy, run_llm
from pydantic_ai import Agent

from infra.authoring.model_policy import V3_FIGURE_SPEC, get_v3_model_settings, get_v3_slot
from infra.authoring.structured_provider import NO_OUTPUT_RETRY, prepare_structured_agent
from media.generation.contracts import VisualGeneratorWorkOrder
from media.render.contracts import RenderSpecError, RenderSpecResult

_FAMILY_MENU = """\
Families (pick exactly one, or "none"):
- polygon_area: any flat shape drawn from corner points (rectangle, L-shape, triangle, \
trapezium, composite room). Use for area, perimeter and length problems.
  fields: points [[x,y],...] (3-20, in order around the shape, in the problem's units); \
unit (e.g. "m"); edge_labels [{edge: i, kind: "computed"|"symbol"|"hidden", text}] \
(edge i runs from point i to point i+1, wrapping); segments [{start, end, \
style: "solid"|"dashed", label, right_angle_at: "start"|"end"}] (split or height lines); \
regions [{points, label, shade}]; mark_right_angles (bool); grid (bool: draw on square \ngrid paper, one square per unit, whole-number points only, at most 30 squares across).
- number_line: a line with ticks, points, jumps or shaded intervals (integers, decimals, \
fractions, inequalities, addition/subtraction jumps).
  fields: start, end, step (>0); tick_format "integer"|"decimal"|"fraction"; denominator \
(2-24, required for fraction); points [{value, label, style: "closed"|"open"}]; \
jumps [{start, end, label}]; intervals [{start, end, start_closed, end_closed, label}] \
(null start/end means it runs off the line; at most 3).
- bar_chart: compare quantities across categories.
  fields: categories [text] (1-12); series [{name, values}] (1-3, one value per category); \
x_label; y_label; y_max; y_step; orientation "vertical"|"horizontal".
- function_graph: axes with lines, parabolas or plotted points.
  fields: x_range [min,max]; y_range [min,max]; x_step; y_step; grid; x_label; y_label; \
curves [linear {form:"linear", m, c, label} | quadratic {form:"quadratic", a, b, c, label} \
| polyline {form:"polyline", points}] (up to 4); points [{x, y, label}].
- flow: a process, steps or decision chain.
  fields: nodes [{id, text, kind: "step"|"decision"|"terminal"}] (2-8, short text); \
edges [{start: id, end: id, label}]; direction "vertical"|"horizontal".
- cycle: a repeating loop of stages.
  fields: nodes [text] (3-8, short); center_label; clockwise (bool).
"""

_EXAMPLE = """\
Example. Request: "L-shaped room, 9 m wide, 7 m deep, with a 3 m by 2 m notch cut from \
one corner. Show every side length." Answer:
{"family": "polygon_area", "reason": "composite polygon with measured sides",
 "spec": {"family": "polygon_area",
  "points": [[0,0],[9,0],[9,5],[6,5],[6,7],[0,7]], "unit": "m",
  "edge_labels": [{"edge":0},{"edge":1},{"edge":2},{"edge":3},{"edge":4},{"edge":5}],
  "mark_right_angles": true}}
A symbol for an unknown side: {"edge": 3, "kind": "symbol", "text": "x"}.
"""

_RULES = """\
Rules:
- Return family "none" (and no spec) for anything realistic, organic or scenic, anything \
with named parts (cells, organs, apparatus, maps), or anything no family fits.
- Numbers come ONLY from the request and the texts below. Never invent values.
- polygon_area: list points in order around the shape, in the problem's units. The \
renderer measures each edge, so the points must match the stated lengths exactly. \
edge_labels choose which edges show their measured length (kind "computed"); an unknown \
is kind "symbol" with text like "x". If the text mentions grid paper or counting squares, \nset grid true and use whole-number points (1 unit = 1 square). If the text states no \nmeasurements, draw a plausible shape but label no edges with computed lengths.
- flow and cycle: at most 8 nodes, with short node text.
- function_graph: only linear, quadratic or polyline curves.
- Never output SVG, HTML or code. Output only the structured result.
"""


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- (none)"


def _request_block(order: VisualGeneratorWorkOrder) -> str:
    visual = order.visual
    sources = "\n".join(f"[{entry.key}] {entry.text}" for entry in order.source_of_truth)
    return (
        "Figure request\n"
        f"Purpose: {visual.purpose}\n"
        f"Must show:\n{_bullets(visual.must_show)}\n"
        f"Labels required:\n{_bullets(visual.labels_required)}\n"
        f"Must not show:\n{_bullets(visual.must_not_show)}\n\n"
        f"Source texts:\n{sources or '(none)'}\n"
    )


def build_prompt(order: VisualGeneratorWorkOrder) -> str:
    return (
        "Choose a drawing family for this lesson figure and fill its spec.\n\n"
        f"{_FAMILY_MENU}\n{_EXAMPLE}\n{_RULES}\n{_request_block(order)}"
    )


def repair_prompt(
    order: VisualGeneratorWorkOrder,
    previous: RenderSpecResult,
    errors: list[RenderSpecError],
) -> str:
    error_lines = "\n".join(f"- {e.code} at {e.path}: {e.message}" for e in errors)
    return (
        "Your previous figure spec failed validation. Fix the structure only; keep the "
        "numbers from the text; keep the same family "
        f"({previous.family}).\n\n"
        f"Previous result:\n{previous.model_dump_json(indent=1)}\n\n"
        f"Errors:\n{error_lines}\n\n"
        f"{_RULES}\n{_request_block(order)}"
    )


class SpecBuilder(Protocol):
    async def build(self, order: VisualGeneratorWorkOrder) -> RenderSpecResult: ...

    async def repair(
        self,
        order: VisualGeneratorWorkOrder,
        previous: RenderSpecResult,
        errors: list[RenderSpecError],
    ) -> RenderSpecResult: ...


_SYSTEM_PROMPT = (
    "You convert a teaching figure request into a typed JSON drawing spec. "
    "Be exact with numbers and return only the requested structure."
)


class LlmSpecBuilder:
    def __init__(self, *, trace_id: str | None = None, generation_id: str | None = None) -> None:
        self._trace_id = trace_id
        self._generation_id = generation_id

    async def build(self, order: VisualGeneratorWorkOrder) -> RenderSpecResult:
        return await self._call(build_prompt(order), caller="v3_figure_spec")

    async def repair(
        self,
        order: VisualGeneratorWorkOrder,
        previous: RenderSpecResult,
        errors: list[RenderSpecError],
    ) -> RenderSpecResult:
        return await self._call(
            repair_prompt(order, previous, errors), caller="v3_figure_spec_repair"
        )

    async def _call(self, prompt: str, *, caller: str) -> RenderSpecResult:
        model, provider_output, structured_context, spec, _source = prepare_structured_agent(
            node_name=V3_FIGURE_SPEC,
            output_type=RenderSpecResult,
        )
        slot = get_v3_slot(V3_FIGURE_SPEC)
        agent = Agent(
            model=model,
            output_type=provider_output,
            system_prompt=_SYSTEM_PROMPT,
            retries=NO_OUTPUT_RETRY,
        )
        result = await run_llm(
            trace_id=self._trace_id or self._generation_id or "figure-spec",
            caller=caller,
            generation_id=self._generation_id,
            agent=agent,
            user_prompt=prompt,
            model=model,
            slot=slot,
            spec=spec,
            retry_policy=RetryPolicy(max_attempts=1, call_timeout_seconds=60.0),
            node=V3_FIGURE_SPEC,
            model_settings=get_v3_model_settings(
                V3_FIGURE_SPEC, base_settings={"max_tokens": 1500}
            ),
            structured_context=structured_context,
        )
        raw = result.output
        if isinstance(raw, RenderSpecResult):
            return raw
        return RenderSpecResult.model_validate(raw)


__all__ = ["LlmSpecBuilder", "SpecBuilder", "build_prompt", "repair_prompt"]
