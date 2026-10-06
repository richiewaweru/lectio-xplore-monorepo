"""Lesson backbone: models/validator/hash, writer repair loop and stored-record loading."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from curriculum.backbone.errors import BackboneOutputInvalidError
from curriculum.backbone.inputs import BackboneInputs, build_backbone_inputs
from curriculum.backbone.models import (
    LessonBackbone,
    LessonBackboneDraft,
    backbone_hash,
    materialize_backbone,
)
from curriculum.backbone.persistence import _record_from_state
from curriculum.backbone.writer import build_backbone_message, generate_backbone
from curriculum.planning.models import AnchorSpec, LessonIntent, SectionPlan, StructuralPlan
from infra.authoring.model_policy import (
    V3_BACKBONE_WRITER,
    V3_NODE_REASONING,
    get_v3_slot,
)
from core.llm import ModelSlot


def _draft_payload(**overrides) -> dict:
    payload = {
        "anchor": {
            "story": "A bakery sells 3 trays of 12 rolls.",
            "data": {"trays": 3, "per_tray": 12},
            "answer": "36 rolls",
            "figure_ids": ["fig-1"],
        },
        "variants": [
            {"change": "5 trays of 10", "data": {"trays": 5, "per_tray": 10}, "answer": "50 rolls"}
        ],
        "figures": [
            {
                "id": "fig-1",
                "purpose": "Show the trays",
                "must_show": ["3 trays"],
                "labels_required": ["12 rolls"],
                "data": {"trays": 3},
            }
        ],
    }
    payload.update(overrides)
    return payload


def _inputs() -> BackboneInputs:
    return BackboneInputs(
        objective="Multiply to find a total",
        cards=[{"id": "c1", "title": "Multiplication", "objective": "x", "misconceptions": []}],
        seed_anchor="a bakery tray",
        subject="Maths",
        level="Grade 3",
    )


# ----------------------------------------------------------------------- models


def test_materialize_assigns_code_owned_ids_and_validates() -> None:
    backbone = materialize_backbone(LessonBackboneDraft.model_validate(_draft_payload()))
    assert backbone.anchor.id == "anchor-1"
    assert [v.id for v in backbone.variants] == ["v1"]
    assert backbone.anchor.figure_ids == ["fig-1"]


def test_draft_forbids_provider_supplied_identity_and_extras() -> None:
    bad = _draft_payload()
    bad["anchor"]["id"] = "mine"
    with pytest.raises(ValidationError):
        LessonBackboneDraft.model_validate(bad)


def test_validator_rejects_unknown_figure_reference() -> None:
    draft = LessonBackboneDraft.model_validate(
        _draft_payload(figures=[])  # anchor still references fig-1
    )
    with pytest.raises(ValidationError, match="unknown figures"):
        materialize_backbone(draft)


def test_validator_rejects_duplicate_ids_blank_story_bad_variant_id_and_too_many_variants() -> None:
    base = materialize_backbone(LessonBackboneDraft.model_validate(_draft_payload())).model_dump()
    dup = dict(base, figures=[{**base["figures"][0], "id": "anchor-1"}])
    dup["anchor"] = {**base["anchor"], "figure_ids": []}
    with pytest.raises(ValidationError, match="unique"):
        LessonBackbone.model_validate(dup)

    blank = dict(base, anchor={**base["anchor"], "story": "   "})
    with pytest.raises(ValidationError, match="story"):
        LessonBackbone.model_validate(blank)

    bad_variant = dict(base, variants=[{**base["variants"][0], "id": "second"}])
    with pytest.raises(ValidationError, match="v1, v2"):
        LessonBackbone.model_validate(bad_variant)

    three = [{**base["variants"][0], "id": f"v{i}"} for i in (1, 2, 3)]
    with pytest.raises(ValidationError):
        LessonBackbone.model_validate(dict(base, variants=three))


def test_hash_is_canonical_and_content_sensitive() -> None:
    one = materialize_backbone(LessonBackboneDraft.model_validate(_draft_payload()))
    reordered = LessonBackbone.model_validate(
        {
            "figures": [f.model_dump() for f in one.figures],
            "variants": [v.model_dump() for v in one.variants],
            "anchor": {k: one.anchor.model_dump()[k] for k in reversed(list(one.anchor.model_dump()))},
        }
    )
    assert backbone_hash(one) == backbone_hash(reordered)
    changed = one.model_copy(update={"anchor": one.anchor.model_copy(update={"answer": "35"})})
    assert backbone_hash(changed) != backbone_hash(one)
    assert len(backbone_hash(one)) == 64


def test_stored_record_round_trip_and_tamper_detection() -> None:
    backbone = materialize_backbone(LessonBackboneDraft.model_validate(_draft_payload()))
    digest = backbone_hash(backbone)
    state = {"backbone": {"backbone": backbone.model_dump(mode="json"), "hash": digest, "input_hash": "i"}}
    assert _record_from_state(state) == (backbone, digest, "i")
    state["backbone"]["hash"] = "0" * 64
    assert _record_from_state(state) is None
    assert _record_from_state({}) is None


def test_node_policy_is_standard_slot_with_low_reasoning() -> None:
    assert get_v3_slot(V3_BACKBONE_WRITER) == ModelSlot.STANDARD
    assert V3_NODE_REASONING[V3_BACKBONE_WRITER] == "low"


# ----------------------------------------------------------------------- inputs


def test_inputs_read_scope_and_misconception_risk_defensively() -> None:
    plan = StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(goal="Multiply.", structure_rationale="x"),
        anchor=AnchorSpec(example="bakery trays", reuse_scope="throughout"),
        prior_knowledge=[],
        sections=[
            SectionPlan(id="orient", title="Orient", role="orient", purpose="Hook with trays")
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )
    inputs = build_backbone_inputs(
        structural_plan=plan,
        context={
            "scope_contract": {
                "terminology": ["factor"],
                "must_not_introduce": ["division"],
                "notation": "x for times",
            }
        },
        card_rows=[
            {
                "id": "c1",
                "title": "T",
                "objective": "O",
                "misconceptions": [
                    {"id": "m1", "description": "adds instead", "risk": "high"},
                    {"id": "m2", "description": "no risk field"},
                ],
            }
        ],
        subject="Maths",
        level="Grade 3",
        notation=None,
    )
    payload = inputs.payload()
    assert payload["objective"] == "Multiply."
    assert payload["seed_anchor"]["description"] == "bakery trays"
    assert payload["sections"] == [
        {"id": "orient", "role": "orient", "title": "Orient", "purpose": "Hook with trays"}
    ]
    assert payload["exclusions"] == ["division"] and payload["terminology"] == ["factor"]
    assert payload["notation"] == "x for times"
    miscs = payload["concept_cards"][0]["misconceptions"]
    assert miscs[0]["risk"] == "high" and "risk" not in miscs[1]
    assert inputs.input_hash() == inputs.input_hash()


# ----------------------------------------------------------------------- writer


@pytest.mark.asyncio
async def test_writer_success_first_attempt_assigns_ids_and_journals() -> None:
    llm = AsyncMock(
        return_value=SimpleNamespace(output=LessonBackboneDraft.model_validate(_draft_payload()))
    )
    with patch("curriculum.backbone.writer.run_llm", new=llm):
        run = await generate_backbone(_inputs(), generation_id="gen-1")
    assert run.backbone.anchor.id == "anchor-1" and run.backbone.variants[0].id == "v1"
    assert [a["class"] for a in run.attempts] == ["OK"]
    assert run.attempts[0]["correlation_id"].startswith("backbone:")
    assert llm.await_args.kwargs["node"] == V3_BACKBONE_WRITER
    assert "validation_errors" not in llm.await_args.kwargs["user_prompt"]


@pytest.mark.asyncio
async def test_writer_repairs_on_second_attempt_with_validation_errors() -> None:
    broken = LessonBackboneDraft.model_validate(_draft_payload(figures=[]))
    good = LessonBackboneDraft.model_validate(_draft_payload())
    llm = AsyncMock(side_effect=[SimpleNamespace(output=broken), SimpleNamespace(output=good)])
    with patch("curriculum.backbone.writer.run_llm", new=llm):
        run = await generate_backbone(_inputs(), generation_id="gen-1")
    assert [a["class"] for a in run.attempts] == ["CONTRACT", "OK"]
    assert llm.await_count == 2
    second = llm.await_args_list[1].kwargs["user_prompt"]
    first = llm.await_args_list[0].kwargs["user_prompt"]
    assert "validation_errors" in second and "unknown figures" in second
    assert "previous_output" in second
    assert "validation_errors" not in first


@pytest.mark.asyncio
async def test_writer_exhaustion_raises_typed_error_with_journal() -> None:
    broken = LessonBackboneDraft.model_validate(_draft_payload(figures=[]))
    llm = AsyncMock(return_value=SimpleNamespace(output=broken))
    with patch("curriculum.backbone.writer.run_llm", new=llm), pytest.raises(
        BackboneOutputInvalidError
    ) as raised:
        await generate_backbone(_inputs(), generation_id="gen-1")
    assert llm.await_count == 2
    assert raised.value.attempt_count == 2
    assert [a["class"] for a in raised.value.backbone_attempts] == ["CONTRACT", "CONTRACT"]
    assert raised.value.backbone_correlation_id.startswith("backbone:")


@pytest.mark.asyncio
async def test_writer_transport_error_is_retried_then_reraised_unwrapped() -> None:
    llm = AsyncMock(side_effect=TimeoutError("provider timed out"))
    with patch("curriculum.backbone.writer.run_llm", new=llm), pytest.raises(TimeoutError) as raised:
        await generate_backbone(_inputs(), generation_id="gen-1")
    assert llm.await_count == 2
    assert [a["class"] for a in raised.value.backbone_attempts] == ["TIMEOUT", "TIMEOUT"]


def test_message_carries_repair_context_only_when_given() -> None:
    plain = build_backbone_message(_inputs())
    repaired = build_backbone_message(_inputs(), repair_errors=["bad"], previous_output={"a": 1})
    assert "validation_errors" not in plain
    assert "validation_errors" in repaired and "previous_output" in repaired
