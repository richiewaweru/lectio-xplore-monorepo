from __future__ import annotations

import re
from typing import Iterable

from pipeline.media.types import (
    MediaPlan,
    ReferenceStyle,
    SlotType,
    VisualFrame,
    VisualRender,
    VisualSlot,
)
from pipeline.state import StyleContext
from pipeline.types.requests import BlockVisualPlacement, SectionPlan
from pipeline.types.section_content import SectionContent, WorkedExampleContent
from pipeline.types.template_contract import TemplateContractSummary

_DIAGRAM_COMPONENTS: dict[str, SlotType] = {
    "diagram-block": SlotType.DIAGRAM,
    "diagram-series": SlotType.DIAGRAM_SERIES,
    "diagram-compare": SlotType.DIAGRAM_COMPARE,
}

_VISUAL_CONCRETE_HINTS = (
    "angle",
    "angles",
    "arrow",
    "axis",
    "axes",
    "before",
    "compare",
    "comparison",
    "coordinate",
    "coordinates",
    "curve",
    "diagram",
    "distance",
    "graph",
    "grid",
    "label",
    "labeled",
    "line",
    "point",
    "points",
    "process",
    "rectangle",
    "run",
    "sequence",
    "shape",
    "slope",
    "step",
    "table",
    "triangle",
    "vector",
    "vertex",
)


def _all_contract_components(contract: TemplateContractSummary) -> set[str]:
    return (
        set(getattr(contract, "required_components", []) or [])
        | set(getattr(contract, "optional_components", []) or [])
        | set(getattr(contract, "always_present", []) or [])
        | set(getattr(contract, "available_components", []) or [])
        | set(getattr(contract, "contextually_present", []) or [])
    )


def _slot_id(
    slot_type: SlotType,
    *,
    block_target: str | None = None,
    problem_index: int | None = None,
) -> str:
    if block_target in {None, "explanation"} and problem_index is None:
        return slot_type.value
    if block_target == "practice" and problem_index is not None:
        return f"practice-{problem_index}-{slot_type.value}"
    if block_target == "worked_example":
        return f"worked-example-{slot_type.value}"
    return f"{block_target or 'slot'}-{slot_type.value}"


def _visual_policy(plan: SectionPlan):
    return getattr(plan, "visual_policy", None)

def _simulation_allowed(plan: SectionPlan, contract: TemplateContractSummary) -> bool:
    if plan.interaction_policy == "disabled":
        return False
    return "simulation-block" in _all_contract_components(contract)


def _preferred_render_for_slot(
    plan: SectionPlan,
    slot_type: SlotType,
) -> VisualRender:
    visual_policy = _visual_policy(plan)
    if slot_type == SlotType.SIMULATION:
        return VisualRender.HTML_SIMULATION
    if slot_type in {SlotType.DIAGRAM_COMPARE, SlotType.DIAGRAM_SERIES}:
        return VisualRender.IMAGE
    explicit_mode = getattr(visual_policy, "mode", None)
    if explicit_mode is not None:
        return VisualRender(explicit_mode)
    return VisualRender.SVG


def _fallback_render_for_slot(slot_type: SlotType, preferred_render: VisualRender) -> VisualRender | None:
    if preferred_render == VisualRender.IMAGE:
        return VisualRender.SVG
    if preferred_render == VisualRender.HTML_SIMULATION:
        return VisualRender.SVG
    if preferred_render == VisualRender.SVG and slot_type == SlotType.SIMULATION:
        return VisualRender.HTML_SIMULATION
    return None


def _reference_style(slot_type: SlotType) -> ReferenceStyle:
    if slot_type == SlotType.DIAGRAM_COMPARE:
        return ReferenceStyle.LOCKED_COMPARISON
    if slot_type == SlotType.DIAGRAM_SERIES:
        return ReferenceStyle.CONSISTENT_SEQUENCE
    if slot_type == SlotType.SIMULATION:
        return ReferenceStyle.INTERACTIVE
    return ReferenceStyle.STANDARD


def _key_concepts(section: SectionContent) -> list[str]:
    concepts: list[str] = []
    if section.definition is not None:
        concepts.append(section.definition.term)
    concepts.extend(section.explanation.emphasis[:3])
    if section.process is not None:
        concepts.extend(step.action for step in section.process.steps[:3])
    return [concept for concept in concepts if concept]


def _pedagogical_intent(plan: SectionPlan) -> str:
    visual_policy = _visual_policy(plan)
    return (
        getattr(visual_policy, "goal", None)
        or plan.focus
        or "Make the core concept visually clear."
    )


def _base_avoid_list(preferred_render: VisualRender) -> list[str]:
    avoid = ["text overlays"]
    if preferred_render == VisualRender.IMAGE:
        avoid.append("photoreal clutter")
    return avoid


def _single_caption(section: SectionContent, plan: SectionPlan) -> str:
    if section.diagram is not None:
        return section.diagram.caption
    return f"Visual explanation for {section.header.title}."


def _series_caption(section: SectionContent) -> str:
    if section.diagram_series is not None and section.diagram_series.diagrams:
        return section.diagram_series.diagrams[0].caption
    return f"Step-by-step sequence for {section.header.title}."


def _compare_caption(section: SectionContent) -> str:
    if section.diagram_compare is not None:
        return section.diagram_compare.caption
    return f"Before and after comparison for {section.header.title}."


def _series_labels(section: SectionContent, concepts: list[str]) -> list[str]:
    if section.diagram_series is not None and section.diagram_series.diagrams:
        return [step.step_label for step in section.diagram_series.diagrams]
    if section.process is not None and section.process.steps:
        return [step.action for step in section.process.steps[:4]]
    if concepts:
        return concepts[:4]
    return [section.header.title, "Key step 2", "Key step 3"]


def _dedupe_casefold(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def _compare_labels(section: SectionContent) -> tuple[str, str]:
    if section.comparison_grid is not None and len(section.comparison_grid.columns) >= 2:
        return (
            section.comparison_grid.columns[0].title.strip() or "Before",
            section.comparison_grid.columns[1].title.strip() or "After",
        )
    if section.diagram_compare is not None:
        return (
            section.diagram_compare.before_label.strip() or "Before",
            section.diagram_compare.after_label.strip() or "After",
        )
    return "Before", "After"


def _frame_output_placeholders(preferred_render: VisualRender, slot_type: SlotType) -> dict[str, str | None]:
    if slot_type == SlotType.SIMULATION:
        return {"html_content": None, "fallback_diagram": None}
    if preferred_render == VisualRender.IMAGE:
        return {"image_url": None}
    return {"svg_content": None}


def _simulation_print_translation(plan: SectionPlan, contract: TemplateContractSummary) -> str:
    if "diagram-block" in _all_contract_components(contract):
        return "static_diagram"
    return "hide"


def _target_dimensions(slot_type: SlotType, frame_count: int, *, sizing: str = "full") -> tuple[int, int]:
    if sizing == "compact":
        return 600, 400
    if slot_type == SlotType.DIAGRAM:
        return 1200, 675
    if slot_type == SlotType.DIAGRAM_COMPARE:
        return 800, 600
    if slot_type == SlotType.DIAGRAM_SERIES:
        if frame_count <= 2:
            return 800, 600
        return 800, 800
    return 1024, 1024


def _normalise_brief(*parts: str | None) -> str | None:
    cleaned = [" ".join((part or "").split()) for part in parts if part and str(part).strip()]
    if not cleaned:
        return None
    return " ".join(cleaned)[:500]


def _extract_explanation_brief(section: SectionContent) -> str | None:
    definition_bits: list[str] = []
    if section.definition is not None:
        definition_bits.append(section.definition.term)
        definition_bits.append(section.definition.plain)
    return _normalise_brief(
        section.explanation.body,
        "Key ideas: " + ", ".join(section.explanation.emphasis[:3]) if section.explanation.emphasis else None,
        "Definition context: " + " ".join(definition_bits) if definition_bits else None,
    )


def _practice_problem_text(section: SectionContent, problem_index: int) -> tuple[str | None, str | None, str | None]:
    if problem_index < 0 or problem_index >= len(section.practice.problems):
        return None, None, None
    problem = section.practice.problems[problem_index]
    first_hint = problem.hints[0].text if problem.hints else None
    return problem.context, problem.question, first_hint


def _extract_practice_brief(section: SectionContent, problem_index: int) -> str | None:
    context, question, first_hint = _practice_problem_text(section, problem_index)
    return _normalise_brief(context, question, first_hint)


def _primary_worked_example(section: SectionContent) -> WorkedExampleContent | None:
    if section.worked_example is not None:
        return section.worked_example
    worked_examples = getattr(section, "worked_examples", None) or []
    return worked_examples[0] if worked_examples else None


def _extract_worked_example_brief(section: SectionContent) -> str | None:
    example = _primary_worked_example(section)
    if example is None:
        return None
    step_text = " ".join(step.content for step in example.steps[:3])
    return _normalise_brief(example.setup, step_text, example.conclusion)


def _looks_visually_concrete(text: str) -> bool:
    lowered = text.lower()
    if re.search(r"\(\s*-?\d+\s*,\s*-?\d+\s*\)", lowered):
        return True
    if any(token in lowered for token in _VISUAL_CONCRETE_HINTS):
        return True
    return False


def _resolve_practice_problem_indices(
    placement: BlockVisualPlacement,
    section: SectionContent,
) -> list[int]:
    problems = section.practice.problems
    if placement.problem_indices is not None:
        seen: set[int] = set()
        ordered: list[int] = []
        for index in placement.problem_indices:
            if 0 <= index < len(problems) and index not in seen:
                seen.add(index)
                ordered.append(index)
        return ordered

    for index, problem in enumerate(problems):
        if (problem.context or "").strip():
            return [index]

    for index, problem in enumerate(problems):
        combined = " ".join(
            part
            for part in (
                problem.question,
                problem.hints[0].text if problem.hints else None,
            )
            if part
        )
        if _looks_visually_concrete(combined):
            return [index]
    return []


def _placement_caption(
    placement: BlockVisualPlacement,
    section: SectionContent,
    *,
    problem_index: int | None = None,
) -> str:
    if placement.block == "practice":
        label = f"practice problem {problem_index + 1}" if problem_index is not None else "practice problem"
        return placement.hint.strip() or f"Supporting diagram for {label} in {section.header.title}."
    if placement.block == "worked_example":
        return placement.hint.strip() or f"Supporting diagram for the worked example in {section.header.title}."
    if placement.slot_type == "diagram_series":
        return _series_caption(section)
    if placement.slot_type == "diagram_compare":
        return _compare_caption(section)
    return placement.hint.strip() or f"Supporting diagram for {section.header.title}."


def _build_single_slot(
    *,
    section: SectionContent,
    plan: SectionPlan,
    slot_type: SlotType,
    sizing: str = "full",
    block_target: str | None = None,
    problem_index: int | None = None,
    content_brief: str | None = None,
    caption: str | None = None,
    label: str | None = None,
) -> VisualSlot:
    preferred_render = _preferred_render_for_slot(plan, slot_type)
    concepts = _key_concepts(section)
    must_include = [label] if block_target in {"practice", "worked_example"} and label else concepts[:4]
    tw, th = _target_dimensions(slot_type, 1, sizing=sizing)
    slot_id = _slot_id(slot_type, block_target=block_target, problem_index=problem_index)
    frame = VisualFrame(
        slot_id=slot_id,
        index=0,
        label=label or section.header.title,
        generation_goal=content_brief or f"Show the core idea of {section.header.title} clearly for learners.",
        must_include=must_include,
        avoid=_base_avoid_list(preferred_render),
        output_placeholders=_frame_output_placeholders(preferred_render, slot_type),
        target_w=tw,
        target_h=th,
    )
    return VisualSlot(
        slot_id=slot_id,
        slot_type=slot_type,
        required=True,
        preferred_render=preferred_render,
        fallback_render=_fallback_render_for_slot(slot_type, preferred_render),
        sizing=sizing,
        block_target=block_target,
        problem_index=problem_index,
        content_brief=content_brief,
        pedagogical_intent=_pedagogical_intent(plan),
        caption=caption or _single_caption(section, plan),
        reference_style=_reference_style(slot_type),
        frames=[frame],
    )


def _build_series_slot(
    section: SectionContent,
    plan: SectionPlan,
    *,
    sizing: str = "full",
    block_target: str | None = "explanation",
    content_brief: str | None = None,
) -> VisualSlot:
    preferred_render = _preferred_render_for_slot(plan, SlotType.DIAGRAM_SERIES)
    concepts = _key_concepts(section)
    labels = _dedupe_casefold(_series_labels(section, concepts))
    frame_count = len(labels)
    tw, th = _target_dimensions(SlotType.DIAGRAM_SERIES, frame_count, sizing=sizing)
    slot_id = _slot_id(SlotType.DIAGRAM_SERIES, block_target=block_target)
    frames = [
        VisualFrame(
            slot_id=slot_id,
            index=index,
            label=label,
            generation_goal=f"Show sequence step {index + 1} for {section.header.title}: {label}.",
            must_include=[label] + ([concepts[index]] if index < len(concepts) else []),
            avoid=_base_avoid_list(preferred_render),
            output_placeholders=_frame_output_placeholders(preferred_render, SlotType.DIAGRAM_SERIES),
            target_w=tw,
            target_h=th,
        )
        for index, label in enumerate(labels)
    ]
    return VisualSlot(
        slot_id=slot_id,
        slot_type=SlotType.DIAGRAM_SERIES,
        required=True,
        preferred_render=preferred_render,
        fallback_render=_fallback_render_for_slot(SlotType.DIAGRAM_SERIES, preferred_render),
        sizing=sizing,
        block_target=block_target,
        content_brief=content_brief,
        pedagogical_intent=_pedagogical_intent(plan),
        caption=_series_caption(section),
        reference_style=_reference_style(SlotType.DIAGRAM_SERIES),
        frames=frames,
        series_context=section.header.title,
    )


def _build_compare_slot(
    section: SectionContent,
    plan: SectionPlan,
    *,
    sizing: str = "full",
    block_target: str | None = "explanation",
    content_brief: str | None = None,
) -> VisualSlot:
    preferred_render = _preferred_render_for_slot(plan, SlotType.DIAGRAM_COMPARE)
    before_label, after_label = _compare_labels(section)
    tw, th = _target_dimensions(SlotType.DIAGRAM_COMPARE, 2, sizing=sizing)
    slot_id = _slot_id(SlotType.DIAGRAM_COMPARE, block_target=block_target)
    frames = [
        VisualFrame(
            slot_id=slot_id,
            index=0,
            label=before_label,
            generation_goal=f"Render the before state for {section.header.title}.",
            must_include=[before_label],
            avoid=_base_avoid_list(preferred_render),
            output_placeholders=_frame_output_placeholders(preferred_render, SlotType.DIAGRAM_COMPARE),
            target_w=tw,
            target_h=th,
        ),
        VisualFrame(
            slot_id=slot_id,
            index=1,
            label=after_label,
            generation_goal=f"Render the after state for {section.header.title}.",
            must_include=[after_label],
            avoid=_base_avoid_list(preferred_render),
            output_placeholders=_frame_output_placeholders(preferred_render, SlotType.DIAGRAM_COMPARE),
            target_w=tw,
            target_h=th,
        ),
    ]
    return VisualSlot(
        slot_id=slot_id,
        slot_type=SlotType.DIAGRAM_COMPARE,
        required=True,
        preferred_render=preferred_render,
        fallback_render=_fallback_render_for_slot(SlotType.DIAGRAM_COMPARE, preferred_render),
        sizing=sizing,
        block_target=block_target,
        content_brief=content_brief,
        pedagogical_intent=_pedagogical_intent(plan),
        caption=_compare_caption(section),
        reference_style=_reference_style(SlotType.DIAGRAM_COMPARE),
        frames=frames,
    )


def _build_simulation_slot(section: SectionContent, plan: SectionPlan) -> VisualSlot:
    visual_policy = _visual_policy(plan)
    preferred_render = _preferred_render_for_slot(plan, SlotType.SIMULATION)
    simulation_intent = getattr(visual_policy, "simulation_intent", None) or plan.practice_target
    frame = VisualFrame(
        slot_id=_slot_id(SlotType.SIMULATION),
        index=0,
        label=section.header.title,
        generation_goal=f"Represent an interactive view for {section.header.title}.",
        must_include=_key_concepts(section)[:4],
        avoid=["unexplained controls"],
        output_placeholders=_frame_output_placeholders(preferred_render, SlotType.SIMULATION),
    )
    return VisualSlot(
        slot_id=_slot_id(SlotType.SIMULATION),
        slot_type=SlotType.SIMULATION,
        required=plan.interaction_policy == "required",
        preferred_render=preferred_render,
        fallback_render=_fallback_render_for_slot(SlotType.SIMULATION, preferred_render),
        pedagogical_intent=_pedagogical_intent(plan),
        caption=f"Interactive exploration for {section.header.title}.",
        reference_style=_reference_style(SlotType.SIMULATION),
        frames=[frame],
        simulation_intent=simulation_intent,
        simulation_type=None,
        simulation_goal=simulation_intent or _pedagogical_intent(plan),
        anchor_block="explanation",
        print_translation="static_diagram",
        expects_static_fallback=False,
    )


def _slots_from_visual_placements(
    *,
    section_plan: SectionPlan,
    section_content: SectionContent,
) -> list[VisualSlot]:
    slots: list[VisualSlot] = []
    seen_slot_ids: set[str] = set()

    for placement in section_plan.visual_placements:
        if placement.block == "explanation":
            content_brief = _extract_explanation_brief(section_content)
            if placement.slot_type == "diagram_series":
                slot = _build_series_slot(
                    section_content,
                    section_plan,
                    sizing=placement.sizing,
                    block_target="explanation",
                    content_brief=content_brief,
                )
            elif placement.slot_type == "diagram_compare":
                slot = _build_compare_slot(
                    section_content,
                    section_plan,
                    sizing=placement.sizing,
                    block_target="explanation",
                    content_brief=content_brief,
                )
            else:
                slot = _build_single_slot(
                    section=section_content,
                    plan=section_plan,
                    slot_type=SlotType.DIAGRAM,
                    sizing=placement.sizing,
                    block_target="explanation",
                    content_brief=content_brief,
                    caption=_single_caption(section_content, section_plan),
                )
            if slot.slot_id not in seen_slot_ids:
                slots.append(slot)
                seen_slot_ids.add(slot.slot_id)
            continue

        if placement.block == "practice":
            for problem_index in _resolve_practice_problem_indices(placement, section_content):
                slot = _build_single_slot(
                    section=section_content,
                    plan=section_plan,
                    slot_type=SlotType.DIAGRAM,
                    sizing=placement.sizing,
                    block_target="practice",
                    problem_index=problem_index,
                    content_brief=_normalise_brief(
                        placement.hint,
                        _extract_practice_brief(section_content, problem_index),
                    ),
                    caption=_placement_caption(
                        placement,
                        section_content,
                        problem_index=problem_index,
                    ),
                    label=f"Practice problem {problem_index + 1}",
                )
                if slot.slot_id not in seen_slot_ids:
                    slots.append(slot)
                    seen_slot_ids.add(slot.slot_id)
            continue

        if placement.block == "worked_example" and _primary_worked_example(section_content) is not None:
            slot = _build_single_slot(
                section=section_content,
                plan=section_plan,
                slot_type=SlotType.DIAGRAM,
                sizing=placement.sizing,
                block_target="worked_example",
                content_brief=_normalise_brief(
                    placement.hint,
                    _extract_worked_example_brief(section_content),
                ),
                caption=_placement_caption(placement, section_content),
                label="Worked example",
            )
            if slot.slot_id not in seen_slot_ids:
                slots.append(slot)
                seen_slot_ids.add(slot.slot_id)

    return slots


def media_planner(
    *,
    section_plan: SectionPlan,
    section_content: SectionContent,
    template_contract: TemplateContractSummary,
    style_context: StyleContext | None,
) -> MediaPlan:
    _ = style_context
    slots: list[VisualSlot] = []
    notes: list[str] = []

    if section_plan.visual_placements:
        slots.extend(
            _slots_from_visual_placements(
                section_plan=section_plan,
                section_content=section_content,
            )
        )
        if not slots:
            notes.append("Visual placements were present but no renderable slots were resolved.")
    else:
        notes.append("No media slots resolved - visual_placements is empty.")

    if _simulation_allowed(section_plan, template_contract):
        simulation_slot = _build_simulation_slot(section_content, section_plan)
        simulation_slot.print_translation = _simulation_print_translation(
            section_plan,
            template_contract,
        )
        simulation_slot.expects_static_fallback = simulation_slot.print_translation == "static_diagram"
        slots.append(simulation_slot)
        notes.append("Simulation slot planned for executor-backed HTML generation.")

    if not slots:
        notes.append("No media slots resolved for this section.")

    return MediaPlan(
        section_id=section_plan.section_id,
        slots=slots,
        planner_notes=notes,
    )


def find_slot(media_plan: MediaPlan | None, slot_type: SlotType) -> VisualSlot | None:
    if media_plan is None:
        return None
    return next(
        (
            slot
            for slot in media_plan.slots
            if slot.slot_type == slot_type and slot.block_target not in {"practice", "worked_example"}
        ),
        None,
    )


def visual_slots(media_plan: MediaPlan | None) -> Iterable[VisualSlot]:
    if media_plan is None:
        return ()
    return (
        slot
        for slot in media_plan.slots
        if slot.slot_type in {SlotType.DIAGRAM, SlotType.DIAGRAM_COMPARE, SlotType.DIAGRAM_SERIES}
        and slot.block_target not in {"practice", "worked_example"}
    )


def slot_targets(media_plan: MediaPlan | None) -> list[str]:
    if media_plan is None:
        return []
    ordered: list[str] = []
    for slot in visual_slots(media_plan):
        target = slot.slot_type.value
        if target not in ordered and slot.required:
            ordered.append(target)
    return ordered


def slot_render(media_plan: MediaPlan | None) -> str | None:
    if media_plan is None:
        return None
    for slot in visual_slots(media_plan):
        if slot.required:
            render = slot.preferred_render.value
            if render in {"svg", "image"}:
                return render
    return None
