from __future__ import annotations

from media.qc.visual_qc import _criteria_prompt
from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem


def test_visual_qc_prompt_rejects_full_sentence_caption_text() -> None:
    prompt = _criteria_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-1",
            visual=VisualPlanItem(
                id="vis-1",
                attaches_to="build",
                mode="diagram",
                purpose="show area decomposition",
            ),
        )
    )

    assert "full-sentence caption/title text inside the image" in prompt
    assert "remove all sentence text from the image" in prompt
