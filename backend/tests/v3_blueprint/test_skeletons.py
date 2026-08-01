from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient

from app import create_app
from generation.skeleton_routes import preview_skeletons
from v3_blueprint.knowledge_classifier import (
    KnowledgeTypeClassification,
    classify_knowledge_type,
    classifier_prompt,
)
from v3_blueprint.skeletons import (
    DeviationRequest,
    SkeletonCatalog,
    SkeletonCatalogError,
    SkeletonPreviewRequest,
    classify_for_preview,
    load_skeleton_catalog,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_versioned_catalog_loads_and_all_eleven_skeletons_preview() -> None:
    catalog = load_skeleton_catalog()

    assert catalog.version == 1
    assert catalog.max_slots == 6
    assert len(catalog.skeleton_ids()) == 11
    for skeleton_id in catalog.skeleton_ids():
        preview = catalog.preview_skeleton_by_id(
            skeleton_id,
            profile="extension",
            misconception_count=2,
        )
        assert len(preview.slots) <= 6
        check_slots = [slot for slot in preview.slots if slot.slot_id == "check"]
        assert len(check_slots) == 1
        assert check_slots[0].locked is True


def test_catalog_rejects_unknown_slot_component() -> None:
    catalog = load_skeleton_catalog()
    raw = deepcopy(catalog.data)
    raw["slots"]["orient"]["allowed"].append("not-a-lectio-component")

    with pytest.raises(SkeletonCatalogError, match="unknown component"):
        SkeletonCatalog(raw)


def test_variant_overflow_is_reported_without_exceeding_six_slots() -> None:
    preview = load_skeleton_catalog().preview_skeleton_by_id(
        "conceptual.first_exposure",
        profile="extension",
        misconception_count=2,
    )

    assert len(preview.slots) <= 6
    assert any("variant_slot_overflow" in warning for warning in preview.warnings)
    assert preview.blocking_issues[0].code == "variant_slot_overflow"


def test_structural_diff_explains_declared_profile_changes() -> None:
    preview = load_skeleton_catalog().preview_skeleton_by_id(
        "conceptual.first_exposure",
        profile="support",
        misconception_count=1,
    )

    extra = next(
        item
        for item in preview.structural_diff
        if item.toggle_id == "support.high.extra_contrast"
    )
    assert extra.operation == "repeat"
    assert extra.slot_id == "contrast"
    assert "confusion" in extra.explanation


def test_approved_deviation_is_explicit_and_preserves_locked_check() -> None:
    deviation = DeviationRequest(
        id="deviation-1",
        skeleton_id="conceptual.first_exposure",
        operation="remove",
        target_slot="orient",
        reason="The class already completed the orientation activity.",
        requested_by="teacher",
        status="approved",
    )
    preview = load_skeleton_catalog().preview_skeleton_by_id(
        "conceptual.first_exposure",
        profile="extension",
        misconception_count=2,
        approved_deviations=[deviation],
    )

    assert not preview.blocking_issues
    assert [slot.slot_id for slot in preview.slots].count("check") == 1
    applied = next(item for item in preview.structural_diff if item.toggle_id == "deviation:deviation-1")
    assert applied.operation == "remove"
    assert "Teacher-approved deviation" in applied.explanation


def test_preview_endpoint_performs_zero_model_calls(monkeypatch) -> None:
    def _model_call_is_forbidden(*args, **kwargs):
        raise AssertionError("preview must not call a model")

    monkeypatch.setattr(
        "v3_blueprint.knowledge_classifier.classify_knowledge_type",
        _model_call_is_forbidden,
    )
    response = preview_skeletons(
        SkeletonPreviewRequest(
            objective="Explain why the mean can mislead for skewed data.",
            lesson_mode="first_exposure",
            misconception_count=1,
            group_profiles=["support", "core", "extension"],
        )
    )

    assert response.skeleton_id == "conceptual.first_exposure"
    assert len(response.variants) == 3


def test_preview_http_endpoint_returns_expanded_slot_lists() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/skeletons:preview",
        json={
            "objective": "Identify the inputs to photosynthesis.",
            "lesson_mode": "first_exposure",
            "misconception_count": 0,
            "group_profiles": ["core"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["skeleton_id"] == "factual.first_exposure"
    assert payload["variants"][0]["slots"][-1]["slot_id"] == "check"


def test_classifier_prompt_is_verbatim_prompt_pack_section_two() -> None:
    prompt_pack = (_REPO_ROOT / "handoff" / "20_PROMPT_PACK.md").read_text(encoding="utf-8")
    section = prompt_pack.split("## 2. Knowledge-Type Classifier", 1)[1]
    expected = section.split("### System prompt", 1)[1].split("```", 2)[1]

    assert classifier_prompt().strip() == expected.strip()


def test_preview_classifier_returns_valid_enum_for_all_three_path_fixtures() -> None:
    valid = {"procedural", "conceptual", "factual", "evaluative"}
    fixture_dir = _REPO_ROOT / "handoff" / "fixtures"
    for filename in (
        "grade4-photosynthesis-path.json",
        "grade12-photosynthesis-path.json",
        "grade8-unreachable-destination-path.json",
    ):
        fixture = json.loads((fixture_dir / filename).read_text(encoding="utf-8"))
        for module in fixture["modules"]:
            for lesson in module["lessons"]:
                assert classify_for_preview(lesson["objective"]) in valid
                result = KnowledgeTypeClassification(
                    primary_knowledge_type=lesson["primary_knowledge_type"],
                    secondary_demand=lesson.get("secondary_demand"),
                    confidence="high",
                    success_test="Fixture classification contract",
                    note=None,
                )
                assert result.primary_knowledge_type in valid


@pytest.mark.asyncio
async def test_live_classifier_uses_strict_result_and_routes_low_confidence_to_review() -> None:
    output = KnowledgeTypeClassification(
        primary_knowledge_type="conceptual",
        secondary_demand=None,
        confidence="low",
        success_test="The learner judges an unseen case.",
        note="The objective may bundle two capabilities.",
    )
    with patch(
        "v3_blueprint.knowledge_classifier.run_llm",
        new=AsyncMock(return_value=type("Result", (), {"output": output})()),
    ) as mock_run:
        result = await classify_knowledge_type(
            "Explain and calculate the effect for a new case.",
            trace_id="classifier-test",
        )

    assert result.primary_knowledge_type == "conceptual"
    assert result.requires_teacher_review is True
    assert mock_run.await_args.kwargs["node"] == "v3_knowledge_type_classifier"


def test_deviation_schema_cannot_remove_locked_check() -> None:
    with pytest.raises(ValidationError, match="locked check"):
        DeviationRequest(
            skeleton_id="conceptual.first_exposure",
            operation="remove",
            target_slot="check",
            reason="Try to remove the diagnostic.",
            requested_by="model",
        )
