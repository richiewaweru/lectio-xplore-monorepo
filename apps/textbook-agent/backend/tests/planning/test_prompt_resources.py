from __future__ import annotations

import hashlib

from curriculum.prompts import (
    ACTIVE_LESSON_APPROACH_PROMPT,
    LESSON_APPROACH_PROMPT_V1,
    LESSON_APPROACH_PROMPT_V1_SHA256,
    LESSON_APPROACH_PROMPT_V2,
    LESSON_APPROACH_PROMPT_V2_SHA256,
    VISUAL_REQUIRED_INTENTS,
    lesson_approach_planner_prompt,
    lesson_approach_planner_v1_prompt,
    prompt_text,
)
from print.generation.whole_lesson.validation import SPATIAL_PROCESS_REPRESENTATION_INTENTS

V1_SHA256 = "475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd"
V2_SHA256 = "87eee1cf4f272474657538fab2b80d34a47acca584c1801f556fd85de8650c26"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_native_accessor_uses_v2_and_v1_remains_registered() -> None:
    assert ACTIVE_LESSON_APPROACH_PROMPT == LESSON_APPROACH_PROMPT_V2
    assert lesson_approach_planner_prompt() == prompt_text(LESSON_APPROACH_PROMPT_V2)
    assert lesson_approach_planner_v1_prompt() == prompt_text(LESSON_APPROACH_PROMPT_V1)
    assert "assessment_source_policy" in lesson_approach_planner_prompt()
    assert "assessment_source_policy" not in lesson_approach_planner_v1_prompt()


def test_lesson_approach_prompt_checksums_are_authoritative() -> None:
    assert _sha256(lesson_approach_planner_v1_prompt()) == V1_SHA256
    assert _sha256(lesson_approach_planner_prompt()) == V2_SHA256
    assert LESSON_APPROACH_PROMPT_V1_SHA256 == V1_SHA256
    assert LESSON_APPROACH_PROMPT_V2_SHA256 == V2_SHA256


def test_active_v2_prompt_requires_visual_teaching_jobs_without_object_ids() -> None:
    prompt = lesson_approach_planner_prompt()
    assert VISUAL_REQUIRED_INTENTS == SPATIAL_PROCESS_REPRESENTATION_INTENTS
    for intent in VISUAL_REQUIRED_INTENTS:
        assert intent in prompt
    assert "visual_required: true" in prompt
    assert "visual_requirement" not in prompt
    assert "required_visual_slots" in prompt
    assert "object ID, component, layout, renderer" in prompt
    assert "or `compare`" not in prompt
    for object_id in ("diagram-block", "figure-block", "section-writer"):
        assert object_id not in prompt


def test_active_v2_prompt_requires_enriched_continuity_without_format_leaks() -> None:
    prompt = lesson_approach_planner_prompt()
    for field in (
        "learner_title",
        "starting_state",
        "target_state",
        "display_title",
        "entry_state",
        "must_establish",
        "avoid_repeating",
        "bridge_from_previous",
        "exit_state",
    ):
        assert f'"{field}"' in prompt
    assert '"contract_version": 2' in prompt
    output_schema = prompt.split("## OUTPUT", 1)[1].split("## SELF-CHECK", 1)[0]
    for primitive in (
        '"prose"',
        '"table"',
        '"list"',
        '"figure"',
        '"worked-example"',
        '"questions"',
    ):
        assert primitive not in output_schema


def test_active_v2_prompt_states_new_plan_quality_rules() -> None:
    prompt = lesson_approach_planner_prompt()
    normalized = " ".join(prompt.split())
    assert (
        "Never reuse an approved item's stem, numbers, or scenario in a worked"
        in normalized
    )
    assert (
        "Never leave a misconception-surfacing block without stating the correct"
        in normalized
    )
    assert (
        "Never write a rule, criterion, or scenario that is scientifically or"
        in normalized
    )
    assert "never page content" in normalized


def test_active_v2_prompt_binds_sourcebook_needs_to_stable_refs() -> None:
    prompt = lesson_approach_planner_prompt()
    output_schema = prompt.split("## OUTPUT", 1)[1].split("## SELF-CHECK", 1)[0]
    normalized = " ".join(prompt.split())

    assert '"sourcebook_needs": [str]' in output_schema
    assert '"sourcebook_refs": [str]' in output_schema
    assert "Whenever a block has one or more `sourcebook_needs`" in normalized
    assert "give it one or more explicit `sourcebook_refs`" in normalized
    assert "These exact refs become the approved sourcebook entry IDs" in normalized
    assert "When a block has no sourcebook needs, set `sourcebook_refs` to `[]`" in normalized
    assert "do not substitute evidence/provenance citations" in normalized


def test_active_v2_prompt_reserves_approved_assessment_scenarios() -> None:
    prompt = lesson_approach_planner_prompt()
    assert "`reserved_assessment_scenarios`" in prompt
    assert "do NOT appear in that list" in prompt
