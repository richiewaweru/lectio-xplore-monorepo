"""LearnDocument v2 contract, assembly, and document-realizer production."""

from __future__ import annotations

import inspect
from typing import Any

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringProviderCall
from learn.contracts.lesson_document import (
    LearnDocumentValidationError,
    assert_valid_learn_document,
    validate_learn_document,
)
from learn.generation.assemble import assemble_learn_document
from learn.generation.native_production import produce_learn_document_from_teaching


class _OfflineDocProvider:
    """Deterministic offline provider for compose/write unit tests."""

    async def invoke(self, call: AuthoringProviderCall) -> dict[str, Any]:
        kind = str(call.capability_id or "paragraph")
        if kind in {"sequence", "order-items"} or "sequence" in kind:
            return {
                "prompt": "Order the stages.",
                "config": {
                    "items": [
                        {"id": "a", "label": "A"},
                        {"id": "b", "label": "B"},
                        {"id": "c", "label": "C"},
                    ],
                    "order": ["a", "b", "c"],
                },
                "feedback": {"correct": "Correct.", "incorrect": "Try again."},
            }
        if kind in {"choice", "select-one", "interaction"} or "choice" in kind:
            return {
                "prompt": "Choose one.",
                "config": {
                    "options": [
                        {"id": "yes", "text": "Yes"},
                        {"id": "no", "text": "No"},
                    ],
                    "correct_option_id": "yes",
                },
                "feedback": {"correct": "Correct.", "incorrect": "Try again."},
            }
        if "heading" in kind:
            return {"kind": "heading", "text": "Evaporation", "level": 2}
        if "list" in kind:
            return {"kind": "list", "ordered": False, "items": ["Heat", "Escape"]}
        if "callout" in kind:
            return {
                "kind": "callout",
                "tone": "tip",
                "title": "Tip",
                "body": "Warm surfaces dry faster.",
            }
        if "table" in kind:
            return {
                "kind": "table",
                "headers": ["Stage", "State"],
                "rows": [["Evaporation", "Liquid to vapour"]],
                "caption": "States of water.",
            }
        if "figure" in kind:
            return {
                "kind": "figure",
                "caption": "Water cycle diagram",
                "alt": "Diagram of evaporation",
            }
        return {
            "kind": "paragraph",
            "text": "Water molecules at a free surface can leave the liquid and become vapour when they gain enough energy.",
        }


def test_passive_mixed_nodes_validate() -> None:
    document = assemble_learn_document(
        [
            {
                "id": "h1",
                "kind": "heading",
                "text": "Evaporation",
                "level": 1,
                "teaching_block_id": "b1",
            },
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Liquid water becomes vapour.",
                "teaching_block_id": "b1",
            },
            {
                "id": "l1",
                "kind": "list",
                "ordered": True,
                "items": ["Heat the surface.", "Molecules escape."],
                "teaching_block_id": "b2",
            },
            {
                "id": "c1",
                "kind": "callout",
                "tone": "tip",
                "body": "Watch puddles on warm days.",
                "teaching_block_id": "b2",
            },
        ],
        {
            "id": "lesson-passive",
            "title": "Evaporation",
            "subject": "science",
            "source": "generated",
            "source_generation_id": "gen-1",
            "teaching_plan_id": "tp-1",
            "teaching_plan_revision": 1,
        },
    )
    assert document["version"] == 2
    assert validate_learn_document(document) == []
    parsed = assert_valid_learn_document(document)
    assert [n.kind for n in parsed.nodes] == ["heading", "paragraph", "list", "callout"]
    assert [getattr(n, "teaching_block_id", None) for n in parsed.nodes] == [
        "b1",
        "b1",
        "b2",
        "b2",
    ]


def test_interaction_node_validates() -> None:
    document = assemble_learn_document(
        [
            {
                "id": "p1",
                "kind": "paragraph",
                "text": "Choose the best description.",
                "teaching_block_id": "b1",
            },
            {
                "id": "ix1",
                "kind": "interaction",
                "interaction_type": "choice",
                "teaching_block_id": "b1",
                "prompt": "What is evaporation?",
                "config": {
                    "options": [
                        {"id": "a", "text": "Liquid to solid"},
                        {"id": "b", "text": "Liquid to vapour"},
                    ],
                    "correct_option_id": "b",
                },
                "feedback": {"correct": "Yes.", "incorrect": "Try again."},
            },
        ],
        {"title": "Check", "subject": "science", "source": "manual"},
    )
    assert validate_learn_document(document) == []
    kinds = [n["kind"] for n in document["nodes"]]
    assert kinds == ["paragraph", "interaction"]
    assert document["nodes"][1]["interaction_type"] == "choice"
    assert "component_id" not in document["nodes"][1]
    assert "template_id" not in document["nodes"][1]


def test_rejects_component_id_on_document_primitives() -> None:
    errors = validate_learn_document(
        {
            "version": 2,
            "id": "bad",
            "title": "Bad",
            "subject": "science",
            "source": "generated",
            "source_generation_id": None,
            "nodes": [
                {
                    "id": "p1",
                    "kind": "paragraph",
                    "text": "x",
                    "component_id": "explanation-block",
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "teaching_plan_id": None,
            "teaching_plan_revision": None,
        }
    )
    assert errors
    assert any("forbidden" in err for err in errors)
    try:
        assert_valid_learn_document(
            {
                "version": 2,
                "id": "bad2",
                "title": "Bad",
                "subject": "science",
                "source": "generated",
                "nodes": [
                    {
                        "id": "p1",
                        "kind": "paragraph",
                        "text": "x",
                        "template_id": "open-canvas",
                    }
                ],
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        )
        raise AssertionError("expected LearnDocumentValidationError")
    except LearnDocumentValidationError as exc:
        assert any("forbidden" in err for err in exc.errors)


def test_produce_learn_document_from_teaching_is_v2_without_component_ids() -> None:
    plan = TeachingPlan(
        arc="Evaporation basics",
        teaching_plan_id="tp-doc-v2",
        revision=3,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="b-passive",
                        position=0,
                        intent="explain",
                        brief="Evaporation turns liquid water into vapour at the surface.",
                        evidence="Learner can restate the idea.",
                    ),
                    TeachingPlanBlock(
                        id="b-active",
                        position=1,
                        intent="practice",
                        brief="Order the stages of the water cycle.",
                        evidence="Correct sequence submitted.",
                        learner_action=LearnerActionBrief(
                            action="order-items",
                            target="water cycle stages",
                            purpose="Check sequencing",
                            expected_evidence="Correct order",
                            difficulty="guided",
                        ),
                    ),
                ],
            )
        ],
    )

    result = produce_learn_document_from_teaching(
        teaching_plan=plan,
        title="Evaporation",
        subject="science",
        source_generation_id="gen-doc-v2",
        provider=_OfflineDocProvider(),
        allow_heuristic_composition_fallback=True,
    )
    document = result["document"]
    assert document["version"] == 2
    assert validate_learn_document(document) == []
    assert document["teaching_plan_id"] == "tp-doc-v2"
    assert document["teaching_plan_revision"] == 3

    for node in document["nodes"]:
        assert "component_id" not in node
        assert "template_id" not in node

    kinds = [n["kind"] for n in document["nodes"]]
    assert "paragraph" in kinds or "heading" in kinds or "list" in kinds
    assert "interaction" in kinds
    interaction = next(n for n in document["nodes"] if n["kind"] == "interaction")
    assert interaction["interaction_type"] == "sequence"
    assert interaction["teaching_block_id"] == "b-active"

    # New production helper must not import the legacy component lane.
    module = inspect.getmodule(produce_learn_document_from_teaching)
    assert module is not None
    module_src = inspect.getsource(module)
    assert "learn.generation.component_lectio" not in module_src
    assert "from learn.generation import component_lectio" not in module_src
    production_src = inspect.getsource(produce_learn_document_from_teaching)
    assert "assemble_ordered_learn_document" not in production_src
    assert "author_learn_work_orders" not in production_src
