from __future__ import annotations

from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem
from v3_execution.prompts.visual_executor import build_visual_prompt


def test_visual_prompt_includes_diagram_precision_style_requirements() -> None:
    prompt = build_visual_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-1",
            visual=VisualPlanItem(
                id="vis-1",
                attaches_to="model",
                mode="diagram",
                visual_style="diagram_precision",
                purpose="show a labeled fraction model",
                must_show=["numerator label", "denominator label"],
                must_not_show=["photorealistic pizza", "tiny text"],
            ),
        )
    )

    assert "VISUAL STYLE: diagram_precision" in prompt
    assert "clean vector-style raster diagram, not SVG" in prompt
    assert "NO visible text" in prompt
    assert "large legible labels" not in prompt
    assert "Short labels" not in prompt
    assert "LABELS REQUIRED" not in prompt
    assert "- numerator label" in prompt
    assert "- photorealistic pizza" in prompt


def test_visual_prompt_defaults_missing_style_to_illustration() -> None:
    prompt = build_visual_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-2",
            visual=VisualPlanItem(
                id="vis-2",
                attaches_to="intro",
                mode="image",
                purpose="show a friendly everyday scene",
            ),
        )
    )

    assert "VISUAL STYLE: illustration" in prompt
    assert "educational raster illustration" in prompt


def test_diagram_precision_provider_prompt_has_no_label_or_qc_text_permission() -> None:
    prompt = build_visual_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-closed",
            visual=VisualPlanItem(
                id="vis-closed",
                attaches_to="model",
                mode="diagram",
                visual_style="diagram_precision",
                purpose="show sequence",
                labels_required=["A", "B"],
                print_requirements=["large legible labels", "put labels in image"],
            ),
            qc_correction_hint="Fix label spelling",
        )
    )
    assert "NO visible text" in prompt
    assert "large legible labels" not in prompt
    assert "Short labels" not in prompt
    assert "LABELS REQUIRED" not in prompt
    assert "Fix label spelling" not in prompt
