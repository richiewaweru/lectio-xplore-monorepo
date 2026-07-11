from __future__ import annotations

from collections import defaultdict
from typing import Any

from contracts.lectio import _EXTERNAL_FIELDS, get_section_field_for_component
from v3_blueprint.models import ProductionBlueprint
from v3_execution.component_aliases import canonical_component_id
from v3_execution.models import (
    GeneratedAnswerKeyBlock,
    GeneratedComponentBlock,
    GeneratedQuestionBlock,
    GeneratedVisualBlock,
    SectionAssemblyDiagnostic,
)
from v3_execution.runtime.lectio_validation import validate_section_content


# Question-writer blocks become a Lectio practice bucket only when the plan
# explicitly asks for the component that owns that bucket.
PRACTICE_BUCKET_COMPONENTS = {"practice-stack"}


def _visual_has_payload(block: GeneratedVisualBlock) -> bool:
    return bool(block.image_url or block.html_content)


def _visual_status_for_section(
    visual_blocks: list[GeneratedVisualBlock],
) -> str | None:
    for block in visual_blocks:
        if block.status in {"failed", "omitted_quality"}:
            return block.status
    return None


class V3SectionBuilder:
    def build_sections(
        self,
        blueprint: ProductionBlueprint,
        component_blocks: list[GeneratedComponentBlock],
        question_blocks: list[GeneratedQuestionBlock],
        visual_blocks: list[GeneratedVisualBlock],
        *,
        template_id: str,
        answer_key: GeneratedAnswerKeyBlock | None = None,
    ) -> tuple[list[dict[str, Any]], list[str], list[SectionAssemblyDiagnostic]]:
        warnings: list[str] = []
        diagnostics: list[SectionAssemblyDiagnostic] = []

        comps_by_section: dict[str, list[GeneratedComponentBlock]] = defaultdict(list)
        for block in sorted(component_blocks, key=lambda b: (b.section_id, b.position)):
            comps_by_section[block.section_id].append(block)

        questions_by_section: dict[str, list[GeneratedQuestionBlock]] = defaultdict(list)
        for block in question_blocks:
            questions_by_section[block.section_id].append(block)

        visuals_by_attachment: dict[str, list[GeneratedVisualBlock]] = defaultdict(list)
        for vis in visual_blocks:
            visuals_by_attachment[vis.attaches_to].append(vis)

        sections_out: list[dict[str, Any]] = []

        order_lookup = {
            sec.section_id: idx for idx, sec in enumerate(blueprint.sections)
        }

        for section_plan in sorted(
            blueprint.sections,
            key=lambda s: order_lookup.get(s.section_id, 0),
        ):
            section_id = section_plan.section_id
            bucket: dict[str, Any] = {
                "section_id": section_id,
                "template_id": template_id,
            }
            section_warnings: list[str] = []
            missing_components: list[str] = []
            missing_visuals: list[str] = []

            planned_components = section_plan.components
            if not planned_components:
                section_warnings.append(f"Section {section_id} has no planned components.")

            emitted_fields: set[str] = set()
            emitted_order: list[str] = []

            for comp in planned_components:
                planned_id = canonical_component_id(comp.component)
                planned_field = get_section_field_for_component(planned_id)
                block = next(
                    (
                        b
                        for b in comps_by_section[section_id]
                        if b.component_id == planned_id
                    ),
                    None,
                )
                if block is None:
                    visual_status: str | None = None
                    if planned_field in _EXTERNAL_FIELDS:
                        visual_status = _visual_status_for_section(
                            visuals_by_attachment.get(section_id, [])
                        )
                        if any(
                            _visual_has_payload(v)
                            for v in visuals_by_attachment.get(section_id, [])
                        ):
                            continue
                    if visual_status:
                        missing_visuals.append(planned_id)
                        roles = f"{planned_id}@{section_id}"
                        if section_plan.visual_required:
                            roles += f" and required_visual@{section_id}"
                        section_warnings.append(
                            f"Planned visual for {roles} was not delivered (status: {visual_status})."
                        )
                        continue
                    missing_components.append(planned_id)
                    section_warnings.append(
                        f"Missing component output for {planned_id}@{section_id}; section rendered without it."
                    )
                    continue
                field = block.section_field
                if field in emitted_fields:
                    section_warnings.append(
                        f"Duplicate mapping for section_field {field} in {section_id}; keeping first value."
                    )
                    continue
                emitted_fields.add(field)
                bucket[field] = block.data
                emitted_order.append(field)

            questions = sorted(
                questions_by_section.get(section_id, []),
                key=lambda qb: qb.question_id,
            )
            planned_component_ids = {
                canonical_component_id(component.component)
                for component in planned_components
            }
            if questions and planned_component_ids & PRACTICE_BUCKET_COMPONENTS:
                problems = []
                for qb in questions:
                    problems.append(
                        {
                            "difficulty": qb.difficulty,
                            "question": qb.data.get("question", ""),
                            "hints": qb.data.get("hints", []),
                            "problem_type": qb.data.get("problem_type", "open"),
                            **({"diagram": qb.data["diagram"]} if "diagram" in qb.data else {}),
                        }
                    )
                    if qb.diagram_required and not any(
                        v.attaches_to in (section_id, qb.question_id) for v in visual_blocks
                    ):
                        warnings.append(
                            f"diagram_required flagged for {qb.question_id} but no visual attached."
                        )

                bucket["practice"] = {
                    "problems": problems,
                    "label": "Practice Questions",
                    "hints_visible_default": False,
                    "solutions_available": bool(answer_key),
                }
            elif questions:
                for qb in questions:
                    warnings.append(
                        f"question {qb.question_id} planned for section {section_id} was not consumed"
                    )

            visuals_for_section = visuals_by_attachment.get(section_id, [])
            ready_visuals_for_section = [
                visual for visual in visuals_for_section if _visual_has_payload(visual)
            ]
            if section_plan.visual_required and not ready_visuals_for_section:
                failed_status = _visual_status_for_section(visuals_for_section)
                if failed_status and missing_visuals:
                    # A planned visual component and the required-visual slot may
                    # point at the same omitted block; report that failure once.
                    pass
                elif failed_status:
                    missing_visuals.append("required_visual")
                    section_warnings.append(
                        f"Planned visual for required_visual@{section_id} was not delivered (status: {failed_status})."
                    )
                else:
                    missing_visuals.append("required_visual")
                    section_warnings.append(
                        f"Missing visuals for section {section_id}; section rendered without required visual."
                    )

            diagrams = [v for v in visuals_for_section if v.image_url]

            series_frames = sorted(
                [v for v in diagrams if v.mode == "diagram_series"],
                key=lambda v: (v.parent_visual_id or v.visual_id, v.frame_index or 0),
            )
            compare_visuals = [v for v in diagrams if v.mode == "diagram_compare"]
            singletons = [
                v
                for v in diagrams
                if v.mode not in {"diagram_series", "diagram_compare"}
            ]

            if series_frames:
                steps = []
                for frame in series_frames:
                    caption = frame.caption or frame.alt_text or f"Step {frame.frame_index}"
                    steps.append(
                        {
                            "step_label": f"Frame {(frame.frame_index or 0) + 1}",
                            "caption": caption,
                            "image_url": frame.image_url,
                        }
                    )
                bucket["diagram_series"] = {
                    "title": section_plan.title,
                    "diagrams": steps,
                }
            elif compare_visuals:
                # Compare-mode visuals currently render as one composite image, so they
                # flow through the singleton diagram field until the executor emits a
                # distinct before/after asset pair.
                vis_block = compare_visuals[0]
                bucket["diagram"] = {
                    "image_url": vis_block.image_url,
                    "caption": vis_block.caption or section_plan.title,
                    "alt_text": vis_block.alt_text or section_plan.title,
                }
            elif singletons:
                vis_block = singletons[0]
                bucket["diagram"] = {
                    "image_url": vis_block.image_url,
                    "caption": vis_block.caption or section_plan.title,
                    "alt_text": vis_block.alt_text or section_plan.title,
                }

            bucket["_component_order"] = emitted_order
            bucket["_component_positions"] = {
                field: idx for idx, field in enumerate(emitted_order)
            }

            simulations = [v for v in visuals_for_section if v.mode == "simulation"]
            if simulations:
                sim = simulations[0]
                bucket["simulation"] = {"html_fragment": sim.html_content or "", "caption": sim.caption or ""}

            renderable = any(
                key not in {"section_id", "template_id"} and not key.startswith("_")
                for key in bucket
            )
            if not renderable:
                section_warnings.append(
                    f"Section {section_id} has no renderable content after assembly."
                )

            if not renderable:
                status = "failed"
            elif missing_components or missing_visuals:
                status = "incomplete"
            else:
                status = "complete"

            diagnostic = SectionAssemblyDiagnostic(
                section_id=section_id,
                status=status,
                renderable=renderable,
                missing_components=missing_components,
                missing_visuals=missing_visuals,
                warnings=section_warnings,
            )
            diagnostics.append(diagnostic)
            warnings.extend(section_warnings)

            if renderable:
                _validated_bucket, _schema_errors = validate_section_content(bucket)
                if _schema_errors:
                    bucket["_schema_warnings"] = _schema_errors
                elif _validated_bucket is not None:
                    bucket = _validated_bucket
                sections_out.append(bucket)

        return sections_out, warnings, diagnostics


__all__ = ["V3SectionBuilder"]
