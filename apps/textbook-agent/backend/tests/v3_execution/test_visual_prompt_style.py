from __future__ import annotations

from v3_execution.models import VisualGeneratorWorkOrder, VisualPlanItem
from media.generation.prompt import NO_CAPTION_TEXT_CONSTRAINT, build_visual_prompt


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


def _order(mode: str, labels: list[str]) -> VisualGeneratorWorkOrder:
    return VisualGeneratorWorkOrder(
        work_order_id="vis-gem",
        visual=VisualPlanItem(
            id="vis-gem",
            attaches_to="model",
            mode=mode,
            purpose="show the water cycle",
            must_show=["a sea", "a cloud"],
            labels_required=labels,
        ),
    )


def test_gemini_prompt_with_labels_has_closed_text_set() -> None:
    prompt = build_visual_prompt(
        _order("diagram", ["evaporation", "condensation"]),
        provider_renders_labels=True,
    )

    assert '"evaporation"' in prompt
    assert '"condensation"' in prompt
    assert "closed set" in prompt
    assert "no paraphrases" in prompt
    assert "educational diagram" in prompt
    assert "LABELS REQUIRED" not in prompt


def test_gemini_prompt_without_labels_renders_no_words() -> None:
    prompt = build_visual_prompt(_order("diagram", []), provider_renders_labels=True)

    assert "Render no words" in prompt
    assert "LABELS REQUIRED" not in prompt


def test_gemini_image_mode_is_illustration() -> None:
    prompt = build_visual_prompt(_order("image", []), provider_renders_labels=True)

    assert "educational illustration" in prompt
    assert "educational diagram" not in prompt


def test_non_gemini_prompt_keeps_labels_required_and_caption_constraint() -> None:
    prompt = build_visual_prompt(_order("image", ["sea", "cloud"]))

    assert "LABELS REQUIRED" in prompt
    assert NO_CAPTION_TEXT_CONSTRAINT in prompt


def test_gemini_diagram_prompt_has_representation_block_and_row_placement() -> None:
    prompt = build_visual_prompt(
        _order("diagram", ["evaporation", "condensation"]),
        provider_renders_labels=True,
    )

    assert "HOW TO REPRESENT IT" in prompt
    assert "in its row or column" in prompt


def test_numbered_diagram_prompt_has_representation_block() -> None:
    prompt = build_visual_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-num",
            visual=VisualPlanItem(
                id="vis-num",
                attaches_to="model",
                mode="diagram",
                visual_style="diagram_numbered",
                purpose="show the parts of a flower",
                must_show=["petal", "stem"],
                labels_required=["petal", "stem"],
            ),
        )
    )

    assert "HOW TO REPRESENT IT" in prompt


def test_image_mode_prompt_has_no_representation_block() -> None:
    gemini_prompt = build_visual_prompt(_order("image", []), provider_renders_labels=True)
    plain_prompt = build_visual_prompt(_order("image", ["sea", "cloud"]))

    assert "HOW TO REPRESENT IT" not in gemini_prompt
    assert "HOW TO REPRESENT IT" not in plain_prompt
