from __future__ import annotations

import hashlib

from curriculum.prompts import (
    ACTIVE_LESSON_APPROACH_PROMPT,
    LESSON_APPROACH_PROMPT_V1,
    LESSON_APPROACH_PROMPT_V1_SHA256,
    LESSON_APPROACH_PROMPT_V2,
    LESSON_APPROACH_PROMPT_V2_SHA256,
    lesson_approach_planner_prompt,
    lesson_approach_planner_v1_prompt,
    prompt_text,
)

V1_SHA256 = "475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd"
V2_SHA256 = "8824f2063933dd9e09c554024e2ae305a4faf9ff52e8b329f014f27da64654eb"


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


def test_active_v2_prompt_makes_plan_visual_the_sole_figure_authority() -> None:
    prompt = lesson_approach_planner_prompt()
    assert "visual_required" not in prompt
    assert "required_visual_slots" not in prompt
    assert "## VISUALS" in prompt
    for field in ("mode", "purpose", "must_show", "labels_required", "must_not_show", "required"):
        assert field in prompt
    normalized = " ".join(prompt.split())
    assert "You decide whether the lesson needs a visual" in normalized
    assert "At most one visual per block" in normalized
    assert "The default is no visual" in normalized
    assert "never invented" in normalized
    output_schema = prompt.split("## OUTPUT", 1)[1].split("## SELF-CHECK", 1)[0]
    assert '"visual": {' in output_schema
    assert '"labels_required": [str]' in output_schema
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
