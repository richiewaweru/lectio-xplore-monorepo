from __future__ import annotations

import hashlib

from planning.prompts import (
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
from planning.whole_lesson.validation import SPATIAL_PROCESS_REPRESENTATION_INTENTS


V1_SHA256 = "475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd"
V2_SHA256 = "d94ba4db88aaff85a33f5ff96032fc5eea5e0ecbc08b3112b27639f38386d4d5"


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
