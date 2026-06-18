"""
Deterministic. No LLM.

Validates assembled section content against the template contract
(Layer 3a: contract compliance, Layer 3b: capacity limits).

STATE CONTRACT
    Reads:  current_section_id, generated_sections, contract
    Writes: partial_sections/current_section_id or assembled_sections[current_section_id],
            qc_reports (capacity warnings), completed_nodes, errors
    Model:  none
    Skips:  never
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from pipeline.contracts import validate_section_for_template
from pipeline.console_diagnostics import force_console_log
from pipeline.media.assembly import apply_media_results_to_section
from pipeline.media.slot_state import pending_required_slot_ids, required_visual_fields, visual_mode
from pipeline.media.qc.simulation_qc import validate_simulation_content
from pipeline.state import (
    PartialSectionRecord,
    PipelineError,
    QCReport,
    TextbookPipelineState,
)


def diag(tag: str, **fields) -> None:
    sys.stderr.write(f"DIAG::{tag}::{json.dumps(fields, default=str)}\n")
    sys.stderr.flush()


diag("BUILD_MARKER", file="section_assembler", version="diag_v1")


def _check_capacity(section_dict: dict) -> list[str]:
    # TODO: Replace with capacity warnings derived from Lectio component-registry.json.
    warnings = []

    def words(text: str | None) -> int:
        if not text:
            return 0
        return len(str(text).strip().split())

    hook = section_dict.get("hook", {})
    if words(hook.get("headline")) > 12:
        warnings.append("hook.headline exceeds 12 words")
    if words(hook.get("body")) > 80:
        warnings.append("hook.body exceeds 80 words")

    explanation = section_dict.get("explanation", {})
    if words(explanation.get("body")) > 350:
        warnings.append("explanation.body exceeds 350 words")
    emphasis = explanation.get("emphasis", [])
    if len(emphasis) > 3:
        warnings.append(f"explanation.emphasis has {len(emphasis)} items -- max 3")

    practice = section_dict.get("practice", {})
    problems = practice.get("problems", [])
    if len(problems) < 2:
        warnings.append(f"practice has {len(problems)} problems -- minimum 2")
    if len(problems) > 5:
        warnings.append(f"practice has {len(problems)} problems -- maximum 5")
    for index, problem in enumerate(problems):
        hints = problem.get("hints", [])
        if len(hints) > 3:
            warnings.append(
                f"practice problem {index + 1} has {len(hints)} hints -- max 3"
            )

    glossary = section_dict.get("glossary")
    if glossary:
        terms = glossary.get("terms", [])
        if len(terms) > 8:
            warnings.append(f"glossary has {len(terms)} terms -- max 8")

    worked = section_dict.get("worked_example")
    if worked:
        steps = worked.get("steps", [])
        if len(steps) > 6:
            warnings.append(f"worked_example has {len(steps)} steps -- max 6")

    what_next = section_dict.get("what_next", {})
    if words(what_next.get("body")) > 50:
        warnings.append("what_next.body exceeds 50 words")

    definition = section_dict.get("definition")
    if definition:
        if words(definition.get("formal")) > 80:
            warnings.append("definition.formal exceeds 80 words")
        if words(definition.get("plain")) > 60:
            warnings.append("definition.plain exceeds 60 words")

    return warnings


async def section_assembler(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    return await _assemble_section(state, model_overrides=model_overrides)


async def _assemble_section(
    state: TextbookPipelineState | dict,
    *,
    model_overrides: dict | None = None,
) -> dict:
    _ = model_overrides
    typed = TextbookPipelineState.parse(state)
    section_id = typed.current_section_id
    node_name = "section_assembler"
    force_console_log(
        "FINALIZE",
        "START",
        section_id=section_id,
        mode="final",
    )

    section = typed.generated_sections.get(section_id)
    if not section:
        force_console_log(
            "FINALIZE",
            "MISSING_SECTION",
            section_id=section_id,
            mode="final",
        )
        return {
            "errors": [
                PipelineError(
                    node=node_name,
                    section_id=section_id,
                    message=(
                        f"No generated content found for section {section_id}. "
                        "content_generator may have failed."
                    ),
                    recoverable=False,
                )
            ],
            "completed_nodes": [node_name],
        }

    media_plan = typed.media_plans.get(section_id) if section_id is not None else None
    section = apply_media_results_to_section(
        base_section=section,
        media_plan=media_plan,
        media_frame_results=typed.media_frame_results.get(section_id, {}) if section_id is not None else {},
    )
    simulation_slot = None
    if media_plan is not None:
        simulation_slot = next(
            (slot for slot in media_plan.slots if slot.slot_type.value == "simulation"),
            None,
        )
    section_dict = section.model_dump(exclude_none=True)
    pending_assets = pending_required_slot_ids(typed)
    if simulation_slot is not None and simulation_slot.required:
        simulation_issues = validate_simulation_content(
            slot=simulation_slot,
            simulation=section.simulation,
            fallback_diagram=section.simulation.fallback_diagram if section.simulation is not None else None,
        )
        if simulation_issues:
            pending_assets = [*pending_assets, simulation_slot.slot_id]
    pending_assets = list(dict.fromkeys(pending_assets))
    if pending_assets:
        force_console_log(
            "FINALIZE",
            "AWAITING_ASSETS",
            section_id=section_id,
            mode="final",
            pending_assets=pending_assets,
        )
        partials = dict(typed.partial_sections)
        partials[section_id] = PartialSectionRecord(
            section_id=section.section_id,
            template_id=section.template_id,
            content=section,
            status="awaiting_assets",
            visual_mode=visual_mode(media_plan),
            pending_assets=pending_assets,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        lifecycle = dict(typed.section_lifecycle)
        lifecycle[section_id] = "awaiting_assets"
        return {
            "partial_sections": partials,
            "section_pending_assets": {section_id: pending_assets},
            "section_lifecycle": lifecycle,
            "completed_nodes": [node_name],
        }

    is_valid, violations = validate_section_for_template(
        section_dict,
        typed.contract.id,
        mode="final",
        allow_missing_fields=set(pending_assets),
        additional_required_fields=set(required_visual_fields(media_plan)),
        required_components_override=list(
            getattr(typed.current_section_plan, "required_components", []) or []
        )
        or None,
    )
    if not is_valid:
        payload = {
            "section_id": section_id,
            "violations": violations,
            "required_components": getattr(typed.contract, "required_components", None),
            "always_present": getattr(typed.contract, "always_present", None),
            "available_components": getattr(typed.contract, "available_components", None),
            "section_has_diagram": getattr(section, "diagram", None) is not None,
        }
        diag("ASSEMBLER_CONTRACT_VIOLATION", **payload)
        if any("diagram" in violation.lower() for violation in violations):
            diag("ASSEMBLER_MISSING_DIAGRAM", **payload)
        force_console_log(
            "FINALIZE",
            "CONTRACT_VIOLATION",
            section_id=section_id,
            mode="final",
            violations=violations,
        )
        return {
            "errors": [
                PipelineError(
                    node=node_name,
                    section_id=section_id,
                    message=f"Contract violation: {'; '.join(violations)}",
                    recoverable=True,
                )
            ],
            "completed_nodes": [node_name],
        }

    qc_report = QCReport(
        section_id=section_id,
        passed=True,
        issues=[],
        warnings=_check_capacity(section_dict),
    )
    reports = dict(typed.qc_reports)
    reports[section_id] = qc_report

    assembled = dict(typed.assembled_sections)
    assembled[section_id] = section
    lifecycle = dict(typed.section_lifecycle)
    lifecycle[section_id] = "final"
    force_console_log(
        "FINALIZE",
        "ASSEMBLED",
        section_id=section_id,
        mode="final",
    )
    return {
        "assembled_sections": assembled,
        "section_pending_assets": {section_id: []},
        "section_lifecycle": lifecycle,
        "qc_reports": reports,
        "completed_nodes": [node_name],
    }
