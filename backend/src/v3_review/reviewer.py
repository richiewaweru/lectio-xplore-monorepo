from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from v3_blueprint.models import ProductionBlueprint
from v3_execution.models import DraftPack
from v3_execution.runtime import events as v3_events
from v3_review.deterministic_checks import (
    check_anchor_facts,
    check_answer_key_entries,
    check_component_ids_in_lectio_contract,
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
    check_visuals_attach_to_valid_targets,
)
from v3_review.models import CoherenceReport, ReviewIssue, derive_coherence_status, refresh_issue_counts

EmitFn = Callable[[str, dict[str, Any]], Awaitable[None]]


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
