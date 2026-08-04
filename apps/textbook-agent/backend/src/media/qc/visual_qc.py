from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import BinaryContent

from core.llm.runner import RetryPolicy, run_llm
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V3_VISUAL_QC
from v3_execution.models import VisualGeneratorWorkOrder


class VisualQCVerdict(BaseModel):
    verdict: Literal["accept", "flag", "reject"]
    reasons: list[str] = Field(default_factory=list)
    correction_hint: str = ""


def visual_qc_enabled() -> bool:
    return os.getenv("V3_VISUAL_QC_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _criteria_prompt(order: VisualGeneratorWorkOrder) -> str:
    labels = ", ".join(order.visual.labels_required) or "none"
    must_show = "\n".join(f"- {item}" for item in order.visual.must_show) or "- follow purpose"
    must_not_show = "\n".join(f"- {item}" for item in order.visual.must_not_show) or "- none"
    style_check = ""
    visual_style = getattr(order.visual, "visual_style", None)
    if visual_style == "diagram_precision" or order.visual.mode.startswith("diagram"):
        style_check = "\nAlso flag if important labels are not legible in print."

    return f"""Review this generated raster image for classroom print use.

Return JSON with:
- verdict: "accept", "flag", or "reject"
- reasons: short concrete reasons
- correction_hint: one concise prompt correction if flagged or rejected

Accept if the image is usable even if imperfect. Reject ONLY for unsafe or
inappropriate content. Flag all ordinary quality or constraint problems, including
garbled or illegible labels, missing required content, must_not_show violations,
clearly low-quality output, or full-sentence caption/title text inside the image.
If flagging caption/title text, set correction_hint to
"remove all sentence text from the image".
Items in must_show are REQUIRED. Their presence is never grounds for rejection.
Flag must_not_show violations, illegibility, or caption/sentence text.
Dimension labels are allowed when required; area calculations or sums are not.

Purpose: {order.visual.purpose}
Mode: {order.visual.mode}
Labels required: {labels}

Must show:
{must_show}

Must not show:
{must_not_show}
{style_check}
"""


async def evaluate_visual_quality(
    *,
    image_bytes: bytes,
    mime_type: str,
    order: VisualGeneratorWorkOrder,
    trace_id: str | None,
    generation_id: str | None,
) -> VisualQCVerdict:
    model = get_v3_model(V3_VISUAL_QC)
    spec = get_v3_spec(V3_VISUAL_QC)
    slot = get_v3_slot(V3_VISUAL_QC)
    agent = Agent(
        model=model,
        output_type=VisualQCVerdict,
        system_prompt=(
            "You are a strict but practical image quality reviewer for educational materials. "
            "Return only the requested verdict."
        ),
    )
    result = await run_llm(
        trace_id=trace_id or generation_id or "visual-qc",
        caller="v3_visual_qc",
        generation_id=generation_id,
        agent=agent,
        user_prompt=[
            _criteria_prompt(order),
            BinaryContent(data=image_bytes, media_type=mime_type),
        ],
        model=model,
        slot=slot,
        spec=spec,
        retry_policy=RetryPolicy(max_attempts=1, call_timeout_seconds=60.0),
        node=V3_VISUAL_QC,
        model_settings=get_v3_model_settings(V3_VISUAL_QC, base_settings={"max_tokens": 512}),
    )
    raw = result.output
    if isinstance(raw, VisualQCVerdict):
        return raw
    if hasattr(raw, "model_validate"):
        return VisualQCVerdict.model_validate(raw)
    return VisualQCVerdict.model_validate(raw)
