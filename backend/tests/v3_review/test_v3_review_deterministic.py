from __future__ import annotations

import json
from pathlib import Path

from contracts.lectio import get_section_field_for_component

from v3_blueprint.models import ProductionBlueprint
from v3_execution.component_aliases import canonical_component_id
from v3_execution.models import DraftPack, GeneratedAnswerKeyBlock, GeneratedVisualBlock
from v3_review import coherence_report_to_generation_summary
from v3_review.deterministic_checks import (
    check_duplicate_questions,
    check_expected_answers_preserved,
    check_internal_artifact_leaks,
    check_manual_only_components,
    check_no_extra_questions,
    check_planned_components_exist,
    check_planned_sections_exist,
    check_visual_failures,
    check_planned_visuals_exist,
    check_visual_text_references,
)
from v3_review.models import CoherenceReport


def _load_example(filename: str) -> ProductionBlueprint:
    raw = Path(__file__).resolve().parents[2] / "src" / "v3_blueprint" / "examples" / filename
    return ProductionBlueprint.model_validate(json.loads(raw.read_text(encoding="utf-8")))


def _concept_field() -> str:
    return get_section_field_for_component("explanation-block") or "explanation"


def _minimal_draft_pack(
    *,
    sections: list[dict],
    answer_key: GeneratedAnswerKeyBlock | None,
    visual_blocks: list[GeneratedVisualBlock] | None = None,
) -> DraftPack:
    return DraftPack(
        generation_id="g1",
        blueprint_id="b1",
        template_id="guided-concept-path",
        subject="Mathematics",
        status="draft_ready",
        sections=sections,
        visual_blocks=visual_blocks or [],
        answer_key=answer_key,
        warnings=[],
    )


def test_missing_planned_section_emits_blocking() -> None:
    bp = _load_example("amara_compound_area.json")
    partial_sections = [
        {
            "section_id": bp.sections[0].section_id,
            "template_id": "guided-concept-path",
            _concept_field(): {"body": "ok", "emphasis": []},
            "diagram": {"image_url": "https://example.com/a.png", "caption": "c", "alt_text": "c"},
        }
    ]
    dp = _minimal_draft_pack(
        sections=partial_sections,
        answer_key=GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[
                {"question_id": q.question_id, "student_answer": q.expected_answer}
                for q in bp.question_plan[:1]
            ],
            source_work_order_id="ak",
        ),
    )
    issues = check_planned_sections_exist(bp, dp)
    assert issues
    assert any(i.severity == "blocking" for i in issues)


def test_internal_leak_pattern_blocks() -> None:
    bp = _load_example("amara_compound_area.json")
    leak_body = "Look at wo_visual_01 for help."
    sections = []
    for sec_plan in bp.sections[:1]:
        sections.append(
            {
                "section_id": sec_plan.section_id,
                "template_id": "guided-concept-path",
                _concept_field(): {"body": leak_body, "emphasis": []},
                "diagram": {"image_url": "https://example.com/a.png", "caption": "c", "alt_text": "c"},
            }
        )
    dp = _minimal_draft_pack(
        sections=sections,
        answer_key=GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[
                {"question_id": q.question_id, "student_answer": q.expected_answer}
                for q in bp.question_plan[:1]
            ],
            source_work_order_id="ak",
        ),
    )
    issues = check_internal_artifact_leaks(dp)
    assert issues and issues[0].category == "internal_artifact_leak"


def test_manual_only_component_emits_major_issue() -> None:
    bp = _load_example("amara_compound_area.json")
    bp.sections[0].components[0].component = "image-block"
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": bp.sections[0].section_id,
                "components": [{"component_id": "image-block"}],
            }
        ],
        answer_key=None,
    )

    issues = check_manual_only_components(bp, dp)

    assert issues
    assert all(issue.severity == "major" for issue in issues)
    assert any("manual-only" in issue.message for issue in issues)


def test_extra_questions_minor() -> None:
    bp = _load_example("amara_compound_area.json")
    practice_section_id = next(q.section_id for q in bp.question_plan)
    problems = [
        {"difficulty": "warm", "question": "a", "hints": [], "problem_type": "open"},
        {"difficulty": "warm", "question": "b", "hints": [], "problem_type": "open"},
        {"difficulty": "warm", "question": "c", "hints": [], "problem_type": "open"},
    ]
    sections = []

    def payload_for(field: str, intent: str) -> dict:
        if field == "explanation":
            return {"body": intent, "emphasis": []}
        if field == "worked_example":
            return {
                "title": intent,
                "solution": [{"step": "", "latex": "", "explain": "", "diagramRef": []}],
                "answer": "",
            }
        if field == "practice":
            return {"introduction": "", "items": [], "footnote": "", "diagram": None}
        if field == "summary":
            return {"paragraphs": [intent], "key_points": [], "cta": {}}
        return {"detail": intent}

    for sec_plan in bp.sections:
        bucket: dict = {
            "section_id": sec_plan.section_id,
            "template_id": "guided-concept-path",
        }
        for comp_planned in sec_plan.components:
            if (
                sec_plan.section_id == practice_section_id
                and comp_planned.component == "guided_questions"
            ):
                continue
            cid = canonical_component_id(comp_planned.component)
            field = get_section_field_for_component(cid) or "explanation"
            bucket[field] = payload_for(field, comp_planned.content_intent)

        if sec_plan.section_id == practice_section_id:
            bucket["practice"] = {
                "problems": problems,
                "label": "Practice Questions",
                "hints_visible_default": False,
                "solutions_available": True,
            }

        bucket["diagram"] = {"image_url": "https://example.com/a.png", "caption": "c", "alt_text": "c"}
        sections.append(bucket)

    dp = _minimal_draft_pack(
        sections=sections,
        answer_key=GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[
                {"question_id": q.question_id, "student_answer": q.expected_answer} for q in bp.question_plan
            ],
            source_work_order_id="ak",
        ),
    )
    issues = check_no_extra_questions(bp, dp)
    assert any(i.severity == "minor" for i in issues)


def test_duplicate_questions_emit_minor_repeated_content_issue() -> None:
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": "practice",
                "template_id": "guided-concept-path",
                "practice": {
                    "problems": [
                        {"difficulty": "warm", "question": "Find the area of the shape.", "hints": []},
                        {"difficulty": "warm", "question": "Find the area of the shape!", "hints": []},
                    ]
                },
            }
        ],
        answer_key=None,
    )

    issues = check_duplicate_questions(dp)

    assert len(issues) == 1
    assert issues[0].severity == "minor"
    assert issues[0].category == "repeated_content"
    assert "practice.problems[0]" in issues[0].message
    assert "practice.problems[1]" in issues[0].message


def test_visual_text_reference_without_planned_diagram_is_minor() -> None:
    bp = _load_example("amara_compound_area.json")
    q0 = bp.question_plan[0]
    q0.diagram_required = False
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": q0.section_id,
                "template_id": "guided-concept-path",
                "practice": {
                    "problems": [
                        {
                            "difficulty": "warm",
                            "question": "Look at this shape and find its area.",
                            "hints": [],
                        }
                    ]
                },
            }
        ],
        answer_key=None,
    )

    issues = check_visual_text_references(bp, dp)

    assert len(issues) == 1
    assert issues[0].severity == "minor"
    assert issues[0].category == "visual_mismatch"


def test_visual_text_reference_allowed_for_planned_diagram_question() -> None:
    bp = _load_example("amara_compound_area.json")
    q0 = bp.question_plan[0]
    q0.diagram_required = True
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": q0.section_id,
                "template_id": "guided-concept-path",
                "practice": {
                    "problems": [
                        {
                            "difficulty": "warm",
                            "question": "Look at this shape and find its area.",
                            "hints": [],
                        }
                    ]
                },
            }
        ],
        answer_key=None,
    )

    assert check_visual_text_references(bp, dp) == []


def test_visual_text_reference_ignores_shaped_mid_word() -> None:
    bp = _load_example("amara_compound_area.json")
    q0 = bp.question_plan[0]
    q0.diagram_required = False
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": q0.section_id,
                "template_id": "guided-concept-path",
                "practice": {
                    "problems": [
                        {
                            "difficulty": "warm",
                            "question": "A shaped garden has sides described in words.",
                            "hints": [],
                        }
                    ]
                },
            }
        ],
        answer_key=None,
    )

    assert check_visual_text_references(bp, dp) == []


def test_expected_answer_drift_in_answer_key() -> None:
    bp = _load_example("amara_compound_area.json")
    q0 = bp.question_plan[0]
    dp = _minimal_draft_pack(
        sections=[],
        answer_key=GeneratedAnswerKeyBlock(
            answer_key_id="ak",
            style="answers_only",
            entries=[{"question_id": q0.question_id, "student_answer": "wrong"}],
            source_work_order_id="ak",
        ),
    )
    issues = check_expected_answers_preserved(bp, dp)
    assert issues


def test_coherence_report_summary_json_safe() -> None:
    report = CoherenceReport(
        blueprint_id="b",
        generation_id="g",
        status="passed",
        deterministic_passed=True,
        issues=[],
    )
    summary = coherence_report_to_generation_summary(report)
    assert summary["status"] == "passed"
    assert summary["blocking_count"] == 0


def test_planned_components_skip_diagram_series_but_visual_check_flags_missing() -> None:
    bp = _load_example("james_mitosis_booklet.json")

    sections = []
    for sec in bp.sections:
        sections.append(
            {
                "section_id": sec.section_id,
                "template_id": "guided-concept-path",
            }
        )
    dp = _minimal_draft_pack(sections=sections, answer_key=None)

    component_issues = check_planned_components_exist(bp, dp)
    visual_issues = check_planned_visuals_exist(bp, dp)

    assert all("diagram-series" not in issue.message for issue in component_issues)
    assert any(issue.repair_target_id == "visual:diagram_sequence" for issue in visual_issues)


def test_failed_visual_block_emits_minor_review_issue() -> None:
    dp = _minimal_draft_pack(
        sections=[],
        answer_key=None,
        visual_blocks=[
            GeneratedVisualBlock(
                visual_id="vis-practice-0",
                attaches_to="practice",
                mode="diagram",
                source_work_order_id="wo-v",
                status="failed",
                error_message="provider timeout",
            )
        ],
    )

    issues = check_visual_failures(dp)

    assert len(issues) == 1
    assert issues[0].severity == "minor"
    assert issues[0].category == "visual_generation_failed"


def test_quality_omitted_visual_block_emits_minor_review_issue() -> None:
    dp = _minimal_draft_pack(
        sections=[],
        answer_key=None,
        visual_blocks=[
            GeneratedVisualBlock(
                visual_id="vis-practice-0",
                attaches_to="practice",
                mode="diagram",
                source_work_order_id="wo-v",
                status="omitted_quality",
                error_message="labels were illegible",
            )
        ],
    )

    issues = check_visual_failures(dp)

    assert len(issues) == 1
    assert issues[0].severity == "minor"
    assert issues[0].category == "visual_generation_failed"
    assert issues[0].message.startswith("image omitted by quality gate: ")


def test_required_visual_omitted_by_quality_is_major_not_blocking() -> None:
    bp = _load_example("amara_compound_area.json")
    section_id = next(section.section_id for section in bp.sections if section.visual_required)
    dp = _minimal_draft_pack(
        sections=[{"section_id": section_id, "template_id": "guided-concept-path"}],
        answer_key=None,
        visual_blocks=[
            GeneratedVisualBlock(
                visual_id="vis-omitted",
                attaches_to=section_id,
                mode="diagram",
                source_work_order_id="wo-omitted",
                status="omitted_quality",
            )
        ],
    )

    issues = check_planned_visuals_exist(bp, dp)

    issue = next(issue for issue in issues if issue.generated_ref == section_id)
    assert issue.severity == "major"
    assert "omitted by the quality gate" in issue.message


def test_anaphora_is_not_visual_deixis() -> None:
    bp = _load_example("amara_compound_area.json")
    q0 = bp.question_plan[0]
    q0.diagram_required = False
    dp = _minimal_draft_pack(
        sections=[
            {
                "section_id": q0.section_id,
                "practice": {
                    "problems": [
                        {"question": "An L-shaped figure is made of rectangles. Find the area of the figure."}
                    ]
                },
            }
        ],
        answer_key=None,
    )

    assert check_visual_text_references(bp, dp) == []


def test_generation_5aed3804_replay_flags_known_nonblocking_drift() -> None:
    fixture_dir = Path(__file__).resolve().parents[1] / "fixtures"
    blueprint = ProductionBlueprint.model_validate_json(
        (fixture_dir / "gen_5aed3804_blueprint.json").read_text(encoding="utf-8")
    )
    pack_payload = json.loads(
        (fixture_dir / "gen_5aed3804_pack.json").read_text(encoding="utf-8")
    )
    pack_payload.pop("kind", None)
    draft_pack = DraftPack.model_validate(pack_payload)

    extra = check_no_extra_questions(blueprint, draft_pack)
    visual_refs = check_visual_text_references(blueprint, draft_pack)

    assert any(issue.category == "extra_unplanned_content" for issue in extra)
    assert all(issue.severity == "minor" for issue in extra)
    assert any("Look at" in issue.message for issue in visual_refs)
    assert all(issue.severity == "minor" for issue in visual_refs)

