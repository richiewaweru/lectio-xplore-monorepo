"""Render exact planner prompts with resource identity substitution."""

from __future__ import annotations

import json
from typing import Any

from contracts.lectio_page import PAGE_OBJECT_IDS
from planning.catalogue_projections import (
    TeachingGuidanceProjection,
    build_form_candidate_map,
)
from planning.prompts import form_planner_prompt, lesson_approach_planner_prompt
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.teaching_plan import TeachingPlan
from resource_specs.loader import get_spec
from resource_specs.renderer import render_resource_identity


class PromptObjectLeakError(ValueError):
    pass


def assert_no_page_object_ids(text: str, *, where: str) -> None:
    """Fail when page-object catalogue forms leak into the teaching prompt.

    Hyphenated object ids and explicit object-catalogue markers are hard fails.
    Bare English tokens (list/table/figure) are allowed in pedagogical prose.
    """
    leaks: list[str] = []
    markers = (
        "available_objects",
        "valid_objects",
        "content_schema",
        "worked-example",
        "answer-key",
    )
    for marker in markers:
        if marker in text:
            leaks.append(marker)
    for object_id in PAGE_OBJECT_IDS:
        if "-" in object_id and object_id in text:
            leaks.append(object_id)
    if leaks:
        raise PromptObjectLeakError(
            f"{where} contains page-object markers: {sorted(set(leaks))}"
        )


def render_teaching_prompt(
    packet: ImmutableLessonPacket,
    teaching_guidance: TeachingGuidanceProjection,
    *,
    resource_id: str = "lesson",
) -> str:
    spec = get_spec(resource_id)
    identity = render_resource_identity(spec)
    system = lesson_approach_planner_prompt().replace("{resource_identity}", identity)
    payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
    }
    user = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    rendered = f"{system}\n\n## USER INPUT\n\n{user}"
    assert_no_page_object_ids(rendered, where="lesson-approach prompt")
    return rendered


def build_form_planner_payload(
    packet: ImmutableLessonPacket,
    teaching_plan: TeachingPlan,
    form_guidance: dict[str, Any],
    *,
    candidate_map: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Rich form-planner input envelope (narrow owned output elsewhere)."""
    candidates = candidate_map or build_form_candidate_map(teaching_plan)
    return {
        "arc": teaching_plan.arc,
        "sections": [
            {
                "slot_id": section.slot_id,
                "blocks": [
                    {
                        "id": block.id,
                        "position": block.position,
                        "intent": block.intent,
                        "brief": block.brief,
                        "legal_object_candidates": list(
                            candidates.get(block.id, ())
                        ),
                    }
                    for block in section.blocks
                ],
            }
            for section in teaching_plan.sections
        ],
        "available_objects": form_guidance,
        "lesson": {
            "objective": packet.lesson.objective,
            "grade_level": packet.lesson.grade_level,
            "subject": packet.lesson.subject,
        },
    }


def render_form_prompt(
    packet: ImmutableLessonPacket,
    teaching_plan: TeachingPlan,
    form_guidance: dict[str, Any],
    *,
    resource_id: str = "lesson",
    candidate_map: dict[str, tuple[str, ...]] | None = None,
) -> str:
    spec = get_spec(resource_id)
    identity = render_resource_identity(spec)
    system = form_planner_prompt().replace("{resource_identity}", identity)
    payload = build_form_planner_payload(
        packet,
        teaching_plan,
        form_guidance,
        candidate_map=candidate_map,
    )
    user = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{system}\n\n## USER INPUT\n\n{user}"
