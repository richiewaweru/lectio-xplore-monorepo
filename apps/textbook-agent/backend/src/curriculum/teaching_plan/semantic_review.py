from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.agents import _run_structured
from curriculum.prompts import teaching_plan_semantic_reviewer_prompt
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanDraftV2
from infra.authoring.model_policy import TEACHING_PLAN_SEMANTIC_REVIEWER

SemanticFindingCode = Literal[
    "progression_gap",
    "adjacent_exit_entry",
    "target_coverage_gap",
    "duplicate_section_responsibility",
    "task_evidence_gap",
    "assessment_item_reused",
    "misconception_unresolved",
    "factual_inaccuracy",
    "visual_missing_for_figure_objective",
]

# Reviewer codes that are warnings only: they are flagged, never block or repair.
ADVISORY_ONLY_SEMANTIC_CODES: frozenset[str] = frozenset({"visual_missing_for_figure_objective"})

# Codes that must cite exactly one section and exactly one block.
_SINGLE_SECTION_SINGLE_BLOCK_CODES = frozenset(
    {"task_evidence_gap", "assessment_item_reused", "misconception_unresolved"}
)


class TeachingPlanSemanticFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: SemanticFindingCode
    section_ids: list[str] = Field(min_length=1)
    block_ids: list[str]
    message: str = Field(min_length=1)
    repair_instruction: str = Field(min_length=1)

    @model_validator(mode="after")
    def _require_actionable_text_and_unique_ids(self) -> TeachingPlanSemanticFinding:
        if not self.message.strip() or not self.repair_instruction.strip():
            raise ValueError("semantic finding message and repair instruction are required")
        if len(self.section_ids) != len(set(self.section_ids)):
            raise ValueError("semantic finding section_ids must be unique")
        if len(self.block_ids) != len(set(self.block_ids)):
            raise ValueError("semantic finding block_ids must be unique")
        return self


class TeachingPlanSemanticReviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reviewed: Literal[True]
    findings: list[TeachingPlanSemanticFinding]


class TeachingPlanSemanticReviewError(RuntimeError):
    """The draft reviewer failed or returned a result that cannot be trusted."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class TeachingPlanSemanticReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_hash: str = Field(min_length=64, max_length=64)
    findings: list[TeachingPlanSemanticFinding]

    @property
    def clean(self) -> bool:
        return not self.findings


class TeachingPlanSemanticReviewProtocolError(ValueError):
    pass


def _validate_finding_bindings(
    review: TeachingPlanSemanticReviewDraft,
    *,
    section_to_blocks: dict[str, set[str]],
) -> None:
    section_ids = list(section_to_blocks)
    section_positions = {section_id: index for index, section_id in enumerate(section_ids)}
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for finding in review.findings:
        if any(section_id not in section_to_blocks for section_id in finding.section_ids):
            raise TeachingPlanSemanticReviewProtocolError(
                f"{finding.code} cited an unknown section_id"
            )
        available_blocks = set().union(
            *(section_to_blocks[section_id] for section_id in finding.section_ids)
        )
        if any(block_id not in available_blocks for block_id in finding.block_ids):
            raise TeachingPlanSemanticReviewProtocolError(
                f"{finding.code} cited a block outside its section_ids"
            )

        if finding.code == "adjacent_exit_entry":
            if len(finding.section_ids) != 2:
                raise TeachingPlanSemanticReviewProtocolError(
                    "adjacent_exit_entry must cite exactly two sections"
                )
            first, second = finding.section_ids
            if section_positions[second] != section_positions[first] + 1:
                raise TeachingPlanSemanticReviewProtocolError(
                    "adjacent_exit_entry must cite consecutive sections in lesson order"
                )
            if finding.block_ids:
                raise TeachingPlanSemanticReviewProtocolError(
                    "adjacent_exit_entry cannot cite block_ids"
                )
        elif finding.code == "duplicate_section_responsibility":
            if len(finding.section_ids) < 2 or finding.block_ids:
                raise TeachingPlanSemanticReviewProtocolError(
                    "duplicate_section_responsibility must cite multiple sections only"
                )
        elif finding.code in _SINGLE_SECTION_SINGLE_BLOCK_CODES:
            if len(finding.section_ids) != 1 or len(finding.block_ids) != 1:
                raise TeachingPlanSemanticReviewProtocolError(
                    f"{finding.code} must cite exactly one section and one block"
                )
        elif finding.code == "factual_inaccuracy":
            if len(finding.section_ids) != 1 or len(finding.block_ids) not in (0, 1):
                raise TeachingPlanSemanticReviewProtocolError(
                    "factual_inaccuracy must cite exactly one section and at most one block"
                )
        elif finding.code == "visual_missing_for_figure_objective":
            # Lesson-level: cite the section(s) that should carry the figure; no block.
            if finding.block_ids:
                raise TeachingPlanSemanticReviewProtocolError(
                    "visual_missing_for_figure_objective must use an empty block_ids list"
                )
        elif finding.block_ids:
            raise TeachingPlanSemanticReviewProtocolError(
                f"{finding.code} must use an empty block_ids list"
            )

        signature = (
            finding.code,
            tuple(finding.section_ids),
            tuple(finding.block_ids),
        )
        if signature in seen:
            raise TeachingPlanSemanticReviewProtocolError("duplicate semantic finding")
        seen.add(signature)


async def _review_candidate(
    *,
    draft: TeachingPlanDraftV2,
    plan: TeachingPlan,
    lesson_context: dict[str, Any],
    trace_id: str | None,
    generation_id: str | None,
    system_prompt: str,
    extra_payload: dict[str, Any] | None = None,
    allowed_codes: frozenset[str] | None = None,
    caller: str = "teaching_plan_semantic_reviewer",
) -> list[TeachingPlanSemanticFinding]:
    """Shared reviewer loop: payload, bounded binding re-ask, error mapping.

    Findings whose code is outside ``allowed_codes`` are dropped before binding
    validation (out of scope is not a reviewer defect).
    """
    section_to_blocks = {
        section.slot_id: {block.id for block in section.blocks}
        for section in plan.sections
    }
    if not section_to_blocks or len(section_to_blocks) != len(plan.sections):
        raise TeachingPlanSemanticReviewError(
            "TEACHING_SEMANTIC_REVIEW_INVALID",
            "candidate section identities are missing or duplicated",
        )

    base_payload = {
        "lesson_context": lesson_context,
        "teaching_plan_draft": draft.model_dump(mode="json"),
        "materialized_candidate": plan.model_dump(mode="json"),
        "section_block_identity_map": [
            {"section_id": section_id, "block_ids": sorted(block_ids)}
            for section_id, block_ids in section_to_blocks.items()
        ],
        **(extra_payload or {}),
    }
    binding_error: str | None = None
    # One bounded re-ask: a finding bound to a non-existent section/block is a
    # reviewer output defect, so the exact binding error is fed back once.
    for attempt in range(2):
        payload = dict(base_payload)
        if binding_error is not None:
            payload["previous_attempt_binding_error"] = (
                "Your previous review cited sections or blocks that do not exist or used the "
                "wrong number of sections/blocks for a finding code: "
                f"{binding_error}. Cite only ids from section_block_identity_map, exactly as "
                "the finding code requires."
            )
        try:
            raw_review = await _run_structured(
                node=TEACHING_PLAN_SEMANTIC_REVIEWER,
                caller=caller,
                output_type=TeachingPlanSemanticReviewDraft,
                system_prompt=system_prompt,
                user_payload=payload,
                trace_id=trace_id,
                generation_id=generation_id,
            )
            review = TeachingPlanSemanticReviewDraft.model_validate(
                raw_review.model_dump(mode="json")
                if hasattr(raw_review, "model_dump")
                else raw_review
            )
        except ValidationError as exc:
            raise TeachingPlanSemanticReviewError(
                "TEACHING_SEMANTIC_REVIEW_INVALID",
                "Teaching Plan semantic reviewer returned a malformed review",
            ) from exc
        except Exception as exc:
            raise TeachingPlanSemanticReviewError(
                "TEACHING_SEMANTIC_REVIEW_FAILED",
                "Teaching Plan semantic reviewer failed; candidate is not approval-ready",
            ) from exc

        if allowed_codes is not None:
            review = TeachingPlanSemanticReviewDraft(
                reviewed=True,
                findings=[f for f in review.findings if f.code in allowed_codes],
            )
        try:
            _validate_finding_bindings(review, section_to_blocks=section_to_blocks)
        except (TypeError, ValueError) as exc:
            if attempt == 0:
                binding_error = str(exc)[:500]
                continue
            raise TeachingPlanSemanticReviewError(
                "TEACHING_SEMANTIC_REVIEW_INVALID",
                "Teaching Plan semantic reviewer returned an invalid or unbound finding",
            ) from exc
        break

    return review.findings


async def review_teaching_plan_draft(
    *,
    draft: TeachingPlanDraftV2,
    plan: TeachingPlan,
    lesson_context: dict[str, Any],
    trace_id: str | None = None,
    generation_id: str | None = None,
) -> TeachingPlanSemanticReviewResult:
    """Review one structurally valid V2 candidate once and bind to its content hash."""
    findings = await _review_candidate(
        draft=draft,
        plan=plan,
        lesson_context=lesson_context,
        trace_id=trace_id,
        generation_id=generation_id,
        system_prompt=teaching_plan_semantic_reviewer_prompt(),
    )
    return TeachingPlanSemanticReviewResult(
        content_hash=teaching_plan_content_hash(plan),
        findings=findings,
    )


__all__ = [
    "ADVISORY_ONLY_SEMANTIC_CODES",
    "SemanticFindingCode",
    "TeachingPlanSemanticFinding",
    "TeachingPlanSemanticReviewDraft",
    "TeachingPlanSemanticReviewError",
    "TeachingPlanSemanticReviewResult",
    "review_teaching_plan_draft",
]
