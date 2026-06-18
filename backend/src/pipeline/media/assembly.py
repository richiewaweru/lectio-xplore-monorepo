from __future__ import annotations

from collections.abc import Iterable

from pipeline.media.types import (
    MediaPlan,
    SlotType,
    VisualFrame,
    VisualFrameResult,
    VisualFrameResultStatus,
    VisualRender,
    VisualSlot,
    VisualSlotResult,
    VisualSlotResultStatus,
)
from pipeline.types.section_content import (
    DiagramCompareContent,
    DiagramContent,
    DiagramSeriesContent,
    DiagramSeriesStep,
    SectionContent,
    SimulationContent,
)


def frame_result_key(frame: VisualFrame | int) -> str:
    if isinstance(frame, VisualFrame):
        return str(frame.index)
    return str(frame)


def ordered_frame_results(
    frame_results: dict[str, VisualFrameResult] | None,
    frames: Iterable[VisualFrame],
) -> list[VisualFrameResult]:
    results = frame_results or {}
    ordered: list[VisualFrameResult] = []
    for frame in frames:
        result = results.get(frame_result_key(frame))
        if result is not None:
            ordered.append(result)
    return ordered


def frame_has_required_artifact(slot: VisualSlot, frame_result: VisualFrameResult | None) -> bool:
    if frame_result is None or frame_result.status != VisualFrameResultStatus.GENERATED:
        return False
    if slot.slot_type == SlotType.SIMULATION:
        return bool(frame_result.html_content and frame_result.interaction_spec)
    if slot.preferred_render == VisualRender.IMAGE:
        return bool(frame_result.image_url)
    if slot.preferred_render == VisualRender.SVG:
        return bool(frame_result.svg_content or frame_result.image_url)
    return bool(frame_result.image_url or frame_result.svg_content or frame_result.html_content)


def slot_is_ready(slot: VisualSlot, frame_results: dict[str, VisualFrameResult] | None) -> bool:
    if not slot.frames:
        return False
    results = frame_results or {}
    return all(frame_has_required_artifact(slot, results.get(frame_result_key(frame))) for frame in slot.frames)


def build_slot_result(
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
    *,
    error_message: str | None = None,
) -> VisualSlotResult:
    ordered = ordered_frame_results(frame_results, slot.frames)
    ready = slot_is_ready(slot, frame_results)
    completed_frames = sum(1 for frame_result in ordered if frame_has_required_artifact(slot, frame_result))
    if error_message:
        status = VisualSlotResultStatus.FAILED
    elif ready:
        status = VisualSlotResultStatus.GENERATED
    elif completed_frames:
        status = VisualSlotResultStatus.PARTIAL
    else:
        status = VisualSlotResultStatus.PENDING
    return VisualSlotResult(
        slot_id=slot.slot_id,
        slot_type=slot.slot_type,
        required=slot.required,
        render=slot.preferred_render,
        caption=slot.caption,
        status=status,
        ready=ready,
        completed_frames=completed_frames,
        total_frames=len(slot.frames),
        error_message=error_message,
    )


def _practice_problem_diagram(section: SectionContent, problem_index: int | None) -> DiagramContent | None:
    if problem_index is None:
        return None
    if problem_index < 0 or problem_index >= len(section.practice.problems):
        return None
    return getattr(section.practice.problems[problem_index], "diagram", None)


def _worked_example_diagram(section: SectionContent) -> DiagramContent | None:
    if section.worked_example is not None:
        return getattr(section.worked_example, "diagram", None)
    worked_examples = getattr(section, "worked_examples", None) or []
    if not worked_examples:
        return None
    return getattr(worked_examples[0], "diagram", None)


def capture_static_slot_results(
    section: SectionContent,
    slot: VisualSlot,
) -> tuple[dict[str, VisualFrameResult], VisualSlotResult]:
    frame_results: dict[str, VisualFrameResult] = {}

    if slot.slot_type == SlotType.DIAGRAM:
        if slot.block_target == "practice":
            diagram = _practice_problem_diagram(section, slot.problem_index)
        elif slot.block_target == "worked_example":
            diagram = _worked_example_diagram(section)
        else:
            diagram = section.diagram
        if diagram is not None and (diagram.image_url or diagram.svg_content):
            frame = slot.frames[0]
            frame_results[frame_result_key(frame)] = VisualFrameResult(
                slot_id=slot.slot_id,
                frame_index=frame.index,
                label=frame.label,
                render=slot.preferred_render,
                status=VisualFrameResultStatus.GENERATED,
                svg_content=diagram.svg_content or None,
                image_url=diagram.image_url,
                alt_text=diagram.alt_text,
            )
        return frame_results, build_slot_result(slot, frame_results)

    if slot.slot_type == SlotType.DIAGRAM_COMPARE:
        compare = section.diagram_compare
        if compare is not None:
            frames = slot.frames[:2]
            if len(frames) >= 2 and (compare.before_image_url or compare.before_svg):
                frame_results[frame_result_key(frames[0])] = VisualFrameResult(
                    slot_id=slot.slot_id,
                    frame_index=frames[0].index,
                    label=compare.before_label,
                    render=slot.preferred_render,
                    status=VisualFrameResultStatus.GENERATED,
                    svg_content=compare.before_svg or None,
                    image_url=compare.before_image_url,
                    alt_text=compare.alt_text,
                )
            if len(frames) >= 2 and (compare.after_image_url or compare.after_svg):
                frame_results[frame_result_key(frames[1])] = VisualFrameResult(
                    slot_id=slot.slot_id,
                    frame_index=frames[1].index,
                    label=compare.after_label,
                    render=slot.preferred_render,
                    status=VisualFrameResultStatus.GENERATED,
                    svg_content=compare.after_svg or None,
                    image_url=compare.after_image_url,
                    alt_text=compare.alt_text,
                )
        return frame_results, build_slot_result(slot, frame_results)

    if slot.slot_type == SlotType.DIAGRAM_SERIES:
        series = section.diagram_series
        if series is not None:
            for frame, step in zip(slot.frames, series.diagrams, strict=False):
                if not (step.image_url or step.svg_content):
                    continue
                frame_results[frame_result_key(frame)] = VisualFrameResult(
                    slot_id=slot.slot_id,
                    frame_index=frame.index,
                    label=step.step_label,
                    render=slot.preferred_render,
                    status=VisualFrameResultStatus.GENERATED,
                    svg_content=step.svg_content or None,
                    image_url=step.image_url,
                    alt_text=f"{step.step_label} for {slot.caption}",
                )
        return frame_results, build_slot_result(slot, frame_results)

    return frame_results, build_slot_result(slot, frame_results)


def capture_simulation_slot_results(
    section: SectionContent,
    slot: VisualSlot,
) -> tuple[dict[str, VisualFrameResult], VisualSlotResult]:
    frame_results: dict[str, VisualFrameResult] = {}
    simulation = section.simulation
    if simulation is not None:
        frame = slot.frames[0]
        frame_results[frame_result_key(frame)] = VisualFrameResult(
            slot_id=slot.slot_id,
            frame_index=frame.index,
            label=frame.label,
            render=slot.preferred_render,
            status=VisualFrameResultStatus.GENERATED
            if simulation.spec and simulation.html_content
            else VisualFrameResultStatus.PENDING,
            html_content=simulation.html_content,
            interaction_spec=simulation.spec,
            explanation=simulation.explanation,
        )
    return frame_results, build_slot_result(slot, frame_results)


def diagram_content_from_results(
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
) -> DiagramContent | None:
    ordered = ordered_frame_results(frame_results, slot.frames)
    if not ordered:
        return None
    frame_result = ordered[0]
    if not frame_has_required_artifact(slot, frame_result):
        return None
    return DiagramContent(
        svg_content=frame_result.svg_content or "",
        image_url=frame_result.image_url,
        caption=slot.caption,
        alt_text=frame_result.alt_text or f"Diagram for {slot.caption}",
    )


def compare_content_from_results(
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
) -> DiagramCompareContent | None:
    ordered = ordered_frame_results(frame_results, slot.frames)
    if len(ordered) < 2:
        return None
    before_result, after_result = ordered[:2]
    if not (frame_has_required_artifact(slot, before_result) and frame_has_required_artifact(slot, after_result)):
        return None
    before_frame = slot.frames[0]
    after_frame = slot.frames[1]
    alt_parts = [
        before_result.alt_text or f"{before_frame.label or 'Before'} view",
        after_result.alt_text or f"{after_frame.label or 'After'} view",
    ]
    return DiagramCompareContent(
        before_svg=before_result.svg_content or "",
        after_svg=after_result.svg_content or "",
        before_image_url=before_result.image_url,
        after_image_url=after_result.image_url,
        before_label=before_result.label or before_frame.label or "Before",
        after_label=after_result.label or after_frame.label or "After",
        caption=slot.caption,
        alt_text="; ".join(alt_parts),
    )


def series_content_from_results(
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
) -> DiagramSeriesContent | None:
    ordered = ordered_frame_results(frame_results, slot.frames)
    if not ordered:
        return None
    diagrams: list[DiagramSeriesStep] = []
    for frame, frame_result in zip(slot.frames, ordered, strict=False):
        if not frame_has_required_artifact(slot, frame_result):
            return None
        label = frame_result.label or frame.label or f"Step {frame.index + 1}"
        diagrams.append(
            DiagramSeriesStep(
                step_label=label,
                caption=f"{slot.caption} ({label})",
                svg_content=frame_result.svg_content or "",
                image_url=frame_result.image_url,
            )
        )
    if not diagrams:
        return None
    return DiagramSeriesContent(
        title=slot.series_context or slot.caption,
        diagrams=diagrams,
    )


def simulation_content_from_results(
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
    *,
    fallback_diagram: DiagramContent | None = None,
) -> SimulationContent | None:
    ordered = ordered_frame_results(frame_results, slot.frames)
    if not ordered:
        return None
    frame_result = ordered[0]
    if frame_result.interaction_spec is None:
        return None
    return SimulationContent(
        spec=frame_result.interaction_spec,
        html_content=frame_result.html_content,
        fallback_diagram=fallback_diagram,
        explanation=frame_result.explanation,
    )


def fallback_diagram_from_section(section: SectionContent) -> DiagramContent | None:
    if section.diagram is not None:
        return section.diagram
    return None


def _write_practice_diagram(
    section: SectionContent,
    *,
    problem_index: int,
    diagram: DiagramContent | None,
) -> SectionContent:
    if diagram is None or problem_index < 0 or problem_index >= len(section.practice.problems):
        return section
    problems = list(section.practice.problems)
    problems[problem_index] = problems[problem_index].model_copy(update={"diagram": diagram})
    return section.model_copy(update={"practice": section.practice.model_copy(update={"problems": problems})})


def _write_worked_example_diagram(
    section: SectionContent,
    *,
    diagram: DiagramContent | None,
) -> SectionContent:
    if diagram is None:
        return section
    if section.worked_example is not None:
        return section.model_copy(
            update={"worked_example": section.worked_example.model_copy(update={"diagram": diagram})}
        )
    worked_examples = getattr(section, "worked_examples", None) or []
    if not worked_examples:
        return section
    updated_examples = list(worked_examples)
    updated_examples[0] = updated_examples[0].model_copy(update={"diagram": diagram})
    return section.model_copy(update={"worked_examples": updated_examples})


def apply_slot_results_to_section(
    section: SectionContent,
    slot: VisualSlot,
    frame_results: dict[str, VisualFrameResult] | None,
    *,
    fallback_diagram: DiagramContent | None = None,
) -> SectionContent:
    if slot.slot_type == SlotType.DIAGRAM:
        content = diagram_content_from_results(slot, frame_results)
        if slot.block_target == "practice" and slot.problem_index is not None:
            return _write_practice_diagram(section, problem_index=slot.problem_index, diagram=content)
        if slot.block_target == "worked_example":
            return _write_worked_example_diagram(section, diagram=content)
        return section.model_copy(update={"diagram": content or section.diagram})
    if slot.slot_type == SlotType.DIAGRAM_COMPARE:
        new_content = compare_content_from_results(slot, frame_results)
        if new_content is None:
            return section.model_copy(update={"diagram_compare": section.diagram_compare})
        if section.diagram_compare is not None:
            content = section.diagram_compare.model_copy(update={
                "before_svg": new_content.before_svg,
                "after_svg": new_content.after_svg,
                "before_image_url": new_content.before_image_url,
                "after_image_url": new_content.after_image_url,
                "before_label": new_content.before_label,
                "after_label": new_content.after_label,
            })
        else:
            content = new_content
        return section.model_copy(update={"diagram_compare": content})
    if slot.slot_type == SlotType.DIAGRAM_SERIES:
        content = series_content_from_results(slot, frame_results)
        return section.model_copy(update={"diagram_series": content or section.diagram_series})
    if slot.slot_type == SlotType.SIMULATION:
        content = simulation_content_from_results(
            slot,
            frame_results,
            fallback_diagram=fallback_diagram,
        )
        return section.model_copy(update={"simulation": content or section.simulation})
    return section


def apply_media_results_to_section(
    *,
    base_section: SectionContent,
    media_plan: MediaPlan | None,
    media_frame_results: dict[str, dict[str, VisualFrameResult]] | None,
) -> SectionContent:
    if media_plan is None:
        return base_section

    section = base_section
    slot_lookup = media_frame_results or {}
    for slot in media_plan.slots:
        static_fallback = fallback_diagram_from_section(section)
        section = apply_slot_results_to_section(
            section,
            slot,
            slot_lookup.get(slot.slot_id),
            fallback_diagram=static_fallback,
        )
    return section
