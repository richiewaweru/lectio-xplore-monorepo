"""Render exact planner prompts with resource identity substitution."""

from __future__ import annotations

import json

from curriculum.planning.skeletons import load_skeleton_catalog
from print.contracts.lectio_page import PAGE_OBJECT_IDS
from print.generation.catalogue_projections import TeachingGuidanceProjection
from print.generation.prompts import lesson_approach_planner_prompt
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from resource_specs.loader import get_spec
from resource_specs.renderer import render_lesson_design_guidance, render_resource_identity


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


BACKBONE_TEACHING_GUIDANCE = """## Lesson backbone

This lesson has one fixed backbone: a single anchor scenario with exact data, and
the figures that go with it. The approved questions were already written against
the anchor and its variants (see the approved question ids and their backbone
references in the fixed input), so they use the same scenario and the same data.
Build the sections around the anchor and its figures. Reusing the anchor scenario
across sections is intended, not repetition to avoid, and it takes precedence over
any rule about avoiding an approved question's scenario or numbers: sharing the
anchor's scenario and data is expected, but never copy an approved question's
stem or its answer. Use the anchor's exact data
and figure facts; do not invent other scenarios, shapes or numbers."""


def render_teaching_prompt(
    packet: ImmutableLessonPacket,
    teaching_guidance: TeachingGuidanceProjection,
    *,
    resource_id: str = "lesson",
) -> str:
    spec = get_spec(resource_id)
    identity = render_resource_identity(spec)
    recipe_guidance = load_skeleton_catalog().knowledge_type_guidance(
        str(packet.lesson.knowledge_type)
    )
    if recipe_guidance is not None:
        identity = f"{identity.rstrip()}\n\n{render_lesson_design_guidance(recipe_guidance)}"
    if packet.backbone:
        identity = f"{identity.rstrip()}\n\n{BACKBONE_TEACHING_GUIDANCE}"
    system = lesson_approach_planner_prompt().replace("{resource_identity}", identity)
    from core.prompts.loader import effective_prompt_text

    learner_action_policy = effective_prompt_text("learner-action-policy")
    payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
    }
    user = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    rendered = (
        f"{system}\n\n## LEARNER ACTION POLICY\n\n{learner_action_policy}"
        f"\n\nThis policy supersedes any narrower reading that learner actions "
        f"are only formal assessment. Path-agnostic actions may appear before, "
        f"during, or after explanation when they improve the sequence.\n\n"
        f"## USER INPUT\n\n{user}"
    )
    assert_no_page_object_ids(rendered, where="lesson-approach prompt")
    return rendered

