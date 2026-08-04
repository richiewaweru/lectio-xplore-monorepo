from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from v3_blueprint.models import ProductionBlueprint
from v3_execution.models import DraftPack
from v3_execution.runtime import events as v3_events
from v3_review.deterministic_checks import (
    check_anchor_facts,
    check_answer_key_entries,
    check_component_ids_in_lectio_contract,
    check_duplicate_questions,
    check_expected_answers_preserved,
    check_internal_artifact_leaks,
    check_lectio_schema_validity,
    check_manual_only_components,
    check_no_extra_questions,
    check_no_extra_sections,
    check_planned_components_exist,
    check_planned_questions_exist,
    check_planned_sections_exist,
    check_planned_visuals_exist,
    check_visual_failures,
    check_visual_text_references,
    check_visuals_attach_to_valid_targets,
)
from v3_review.models import CoherenceReport, ReviewIssue, derive_coherence_status, refresh_issue_counts
from v3_review.card_reviewer import CardQCResult, review_card_content

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def _card_qc_issues(result: CardQCResult) -> list[ReviewIssue]:
    issues: list[ReviewIssue] = []
    for check in result.checks:
        if check.result == "PASS":
            continue
        if check.check == "objective":
            category = "card_objective_unmet"
        elif check.check == "scope":
            category = "card_scope_breach"
        elif check.check == "notation":
            category = "card_notation_breach"
        else:
            category = "card_misconception_unconfronted"
        hint = check.correction_hint or check.reason
        issues.append(
            ReviewIssue(
                severity="major",
                category=category,
                message=(
                    f"Card '{result.card_id}' failed {check.check}: {check.reason}"
                ),
                blueprint_ref=f"card_rubrics[{result.card_id}].{check.check}",
                generated_ref=f"{result.variant_label}:{result.card_id}",
                suggested_repair_executor="section_writer",
                repair_target_id=result.card_id,
                qc_correction_hint=hint,
            )
        )
    return issues


async def _run_card_rubrics(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
) -> list[ReviewIssue]:
    async def review(card):
        sections = [
            section
            for section in draft_pack.sections
            if isinstance(section, dict) and section.get("card_id") == card.card_id
        ]
        if not sections:
            return []
        try:
            result = await review_card_content(
                card=card,
                variant_label=blueprint.voice.variant_label,
                notation=blueprint.voice.notation,
                avoid=(
                    list(blueprint.repair_focus.what_not_to_teach)
                    if blueprint.repair_focus is not None
                    else []
                ),
                generated_sections=sections,
                generation_id=draft_pack.generation_id,
            )
        except Exception as exc:  # noqa: BLE001
            return [
                ReviewIssue(
                    severity="minor",
                    category="card_qc_unavailable",
                    message=(
                        f"Card '{card.card_id}' QC could not complete: "
                        f"{type(exc).__name__}: {str(exc)[:240]}"
                    ),
                    blueprint_ref=f"card_rubrics[{card.card_id}]",
                    generated_ref=f"{blueprint.voice.variant_label}:{card.card_id}",
                    suggested_repair_executor="section_writer",
                    repair_target_id=card.card_id,
                )
            ]
        return _card_qc_issues(result)

    batches = await asyncio.gather(
        *(review(card) for card in blueprint.card_rubrics)
    )
    return [issue for batch in batches for issue in batch]


async def run_coherence_review(
    blueprint: ProductionBlueprint,
    draft_pack: DraftPack,
    emit_event: EmitFn,
    *,
    trace_id: str | None = None,
    generation_id: str | None = None,
    model_overrides: dict | None = None,
) -> CoherenceReport:
    _ = trace_id, model_overrides
    gid = generation_id or draft_pack.generation_id

    await emit_event(v3_events.COHERENCE_REVIEW_STARTED, {"generation_id": gid})
    await emit_event(v3_events.DETERMINISTIC_REVIEW_STARTED, {"generation_id": gid})

    det_issues: list[ReviewIssue] = []
    det_issues += check_planned_sections_exist(blueprint, draft_pack)
    det_issues += check_no_extra_sections(blueprint, draft_pack)
    det_issues += check_planned_components_exist(blueprint, draft_pack)
    det_issues += check_planned_questions_exist(blueprint, draft_pack)
    det_issues += check_no_extra_questions(blueprint, draft_pack)
    det_issues += check_duplicate_questions(draft_pack)
    det_issues += check_visual_text_references(blueprint, draft_pack)
    det_issues += check_planned_visuals_exist(blueprint, draft_pack)
    det_issues += check_visuals_attach_to_valid_targets(blueprint, draft_pack)
    det_issues += check_visual_failures(draft_pack)
    det_issues += check_answer_key_entries(blueprint, draft_pack)
    det_issues += check_expected_answers_preserved(blueprint, draft_pack)
    det_issues += check_anchor_facts(blueprint, draft_pack)
    det_issues += check_internal_artifact_leaks(draft_pack)
    det_issues += check_lectio_schema_validity(draft_pack)
    det_issues += check_component_ids_in_lectio_contract(blueprint, draft_pack)
    det_issues += check_manual_only_components(blueprint, draft_pack)
    det_issues += await _run_card_rubrics(blueprint, draft_pack)

    await emit_event(
        v3_events.DETERMINISTIC_REVIEW_COMPLETE,
        {
            "generation_id": gid,
            "issue_count": len(det_issues),
            "blocking": sum(1 for issue in det_issues if issue.severity == "blocking"),
        },
    )

    status = derive_coherence_status(det_issues)
    report = CoherenceReport(
        blueprint_id=draft_pack.blueprint_id,
        generation_id=draft_pack.generation_id,
        status=status,
        deterministic_passed=not any(issue.severity == "blocking" for issue in det_issues),
        issues=det_issues,
    )
    refresh_issue_counts(report)

    await emit_event(
        v3_events.COHERENCE_REPORT_READY,
        {
            "generation_id": gid,
            "status": status,
            "blocking_count": report.blocking_count,
        },
    )

    return report


__all__ = ["run_coherence_review"]
