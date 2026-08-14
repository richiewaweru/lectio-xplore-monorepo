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


def test_diagram_precision_qc_prompt_enforces_closed_label_set_and_metadata_separation() -> None:
    prompt = _criteria_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="vis-closed",
            visual=VisualPlanItem(
                id="vis-closed",
                attaches_to="explain",
                mode="diagram",
                visual_style="diagram_precision",
                purpose="show sequence",
                must_show=["Connect stages with arrows."],
                labels_required=["Evaporation", "Condensation"],
            ),
            qc_correction_hint="Fix the label spelling.",
        )
    )
    assert "CLOSED" in prompt or "Closed-label" in prompt
    assert "misspelled" in prompt
    assert "duplicated" in prompt
    assert "extra visible text" in prompt
    assert "QC corrections" in prompt
    assert "semantic structure" in prompt


def test_topology_raster_qc_prompt_preserves_labels_semantics_and_unwanted_text() -> None:
    from media.qc.visual_qc import _criteria_prompt

    prompt = _criteria_prompt(
        VisualGeneratorWorkOrder(
            work_order_id="topo-qc",
            visual=VisualPlanItem(
                id="topo-qc",
                attaches_to="explain",
                mode="diagram",
                visual_style="diagram_precision",
                purpose="show the water cycle",
                must_show=["Show evaporation feeding condensation."],
                labels_required=["Evaporation", "Condensation"],
            ),
        ),
        topology_raster=True,
    )
    assert "Topology raster criteria" in prompt
    assert "Exact labels" in prompt
    assert "Topology semantics" in prompt
    assert "unwanted text" in prompt
    assert "entities, relationships" in prompt
