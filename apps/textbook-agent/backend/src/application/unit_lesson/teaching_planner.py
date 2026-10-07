"""Application-owned teaching plan result types and shared plan checks.

The staged planner (``staged_teaching_planner``) is the only teaching planner. This
module keeps what it shares: the result dataclasses, the deterministic repairs
(sources outside structural slots, incompatible assessment sources, evidence refs,
anchor grounding, figure visuals) and the learner-action / task-source / frozen-reuse
validators, each in a whole-plan and a per-section form.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from curriculum.approved_items import approved_item_kind
from curriculum.backbone.models import BackboneFigure
from curriculum.teaching_plan.compatibility import (
    allowed_actions_for_source_item,
    response_bearing_action,
)
from curriculum.teaching_plan.models import (
    TeachingPlanSection,
    VisualSpec,
)
from curriculum.teaching_plan.semantic_review import TeachingPlanSemanticReviewResult
from print.generation.catalogue_projections import TeachingGuidanceProjection
from print.generation.whole_lesson.legality import LessonLegalitySnapshot
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from print.generation.whole_lesson.teaching_plan import TeachingPlan
from print.generation.whole_lesson.validation import (
    ValidationReport,
    allowed_teaching_evidence_refs,
    anchor_terms,
    plan_quality_flag,
)
from print.resources.selection import _form_cards


@dataclass
class TeachingPlanAttempt:
    prompt: str
    raw_response: str
    plan: TeachingPlan | None
    validation: ValidationReport
    qc: list[dict[str, Any]]
    attempt: int
    error: str | None = None
    semantic_review: TeachingPlanSemanticReviewResult | None = None


@dataclass
class TeachingPlanResult:
    plan: TeachingPlan
    validation: ValidationReport
    qc: list[dict[str, Any]]
    prompt: str
    raw_response: str
    teaching_guidance: TeachingGuidanceProjection
    attempts: list[TeachingPlanAttempt]
    typical_by_slot: dict[str, set[str]]
    permitted_intents: set[str]
    excluded_intents: set[str]
    legality: LessonLegalitySnapshot
    # None when the lesson review is off (the default) or could not run.
    semantic_review: TeachingPlanSemanticReviewResult | None
    # Advisory quality flags (advisory gate only). Never part of the hashed plan.
    flags: list[dict[str, Any]] = field(default_factory=list)
    # Per-stage latencies and attempt counts.
    stage_timings: dict[str, Any] = field(default_factory=dict)


def _assessment_forms_for_intent(intent: str) -> set[str]:
    """Return questions/choices forms that declare support for this intent."""
    cards = _form_cards()
    out: set[str] = set()
    for form_id in ("questions", "choices"):
        intents = set((cards.get(form_id) or {}).get("supported_intents") or ())
        if intent in intents:
            out.add(form_id)
    return out


def _objective_requires_order_reconstruction(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> bool:
    objective = f"{packet.lesson.objective} {plan.arc}".lower()
    return any(
        token in objective
        for token in ("order", "sequence", "stages", "cycle", "procedure", "steps")
    )


def _missing_order_learner_action_errors(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Legacy diagnostic retained for tests/tools.

    The production planner no longer forces a response action merely because an
    objective contains ordering language. A shared response task now requires an
    approved source so Learn and Print preserve the same task meaning.
    """
    if not _objective_requires_order_reconstruction(plan, packet):
        return []
    has_order_action = any(
        block.learner_action is not None
        and str(block.learner_action.action) in {"order-items", "reconstruct-order"}
        for section in plan.sections
        for block in section.blocks
    )
    if has_order_action:
        return []
    preferred = ("sequence", "practise-guided")
    preferred_blocks = [
        block
        for section in plan.sections
        for block in section.blocks
        if block.intent in preferred
    ]
    if not preferred_blocks:
        return [
            ("TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
            "ordered sequence, but no sequence/practise-guided block exists to own "
            "an order-items learner_action.")
        ]
    return [
        ("TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
        "ordered sequence, but no sequence/practise-guided block declares "
        "learner_action.action='order-items'. Do not leave Learn to invent Sequence.")
    ]


_CHECK_PRACTICE_INTENTS = frozenset(
    {
        "check-understanding",
        "check",
        "assess",
        "practise-guided",
        "practise-independent",
        "practice-guided",
        "practice-independent",
        "guided-practice",
        "independent-practice",
    }
)

_PASSIVE_EVIDENCE_MARKERS = (
    "observe",
    "read",
    "listen",
    "watch",
    "follow the worked",
    "no response",
)


def _missing_check_practice_action_errors(plan: TeachingPlan) -> list[str]:
    """Legacy diagnostic retained for tests/tools.

    Production uses ``_task_source_contract_errors`` instead: practice may be
    genuinely passive, while every response-bearing task must have exact source
    ownership that both Learn and Print can preserve.
    """
    errors: list[str] = []
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action is not None:
                continue
            intent = (block.intent or "").strip().lower().replace("_", "-")
            if intent not in _CHECK_PRACTICE_INTENTS:
                continue
            evidence = f"{block.evidence} {block.brief}".lower()
            if any(marker in evidence for marker in _PASSIVE_EVIDENCE_MARKERS):
                continue
            errors.append(
                "TEACHING_MISSING_LEARNER_ACTION: "
                f"block {block.id!r} intent={intent!r} is evidence-bearing "
                "check/practice but learner_action is null. Either declare a "
                "path-agnostic action or make the block genuinely passive."
            )
    return errors


def _task_source_contract_errors_for_section(section: TeachingPlanSection) -> list[str]:
    """Section-local variant of ``_task_source_contract_errors``."""
    errors: list[str] = []
    for block in section.blocks:
        action = (
            str(block.learner_action.action or "").strip()
            if block.learner_action is not None
            else None
        )
        has_sources = bool(block.source_question_ids)
        if has_sources and block.learner_action is None:
            errors.append(
                "TEACHING_SOURCE_MISSING_ACTION: "
                f"block {block.id!r} owns approved source_question_ids but "
                "learner_action is null. Choose an action allowed by the bound "
                "source record."
            )
            continue
        response_bearing = bool(action and response_bearing_action(action))
        if block.task_mode == "none" and response_bearing and not has_sources:
            errors.append(
                "TEACHING_UNBOUND_RESPONSE_ACTION: "
                f"block {block.id!r} has response-bearing action={action!r} "
                "without an explicit formative task or approved assessment source."
            )
        if block.task_mode == "formative" and not response_bearing:
            errors.append(
                f"TEACHING_FORMATIVE_ACTION_REQUIRED: block {block.id!r} must "
                "have a response-bearing learner_action."
            )
        if block.task_mode == "formative" and has_sources:
            errors.append(
                f"TEACHING_FORMATIVE_SOURCE_FORBIDDEN: block {block.id!r} "
                "cannot own approved assessment sources."
            )
        if block.task_mode == "assessment" and not has_sources:
            errors.append(
                f"TEACHING_ASSESSMENT_SOURCE_REQUIRED: block {block.id!r} "
                "must own an approved source_question_id."
            )
        if has_sources and block.task_mode not in {"none", "assessment"}:
            errors.append(
                f"TEACHING_SOURCE_REQUIRES_ASSESSMENT: block {block.id!r} "
                "approved sources require task_mode=assessment."
            )
    return errors


def _task_source_contract_errors(plan: TeachingPlan) -> list[str]:
    """Enforce shared task ownership while separating formative from assessment."""
    errors: list[str] = []
    for section in plan.sections:
        errors.extend(_task_source_contract_errors_for_section(section))
    return errors


def _action_source_compatibility_errors_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Section-local variant of ``_action_source_compatibility_errors``."""
    from curriculum.teaching_plan.compatibility import (
        ActionSourceIncompatibleError,
        assert_action_compatible_with_sources,
    )

    by_id = {item.id: item for item in packet.approved_items}
    errors: list[str] = []
    for block in section.blocks:
        if block.learner_action is None or not block.source_question_ids:
            continue
        action = str(block.learner_action.action or "").strip()
        items = [by_id[sid] for sid in block.source_question_ids if sid in by_id]
        if not items:
            continue
        try:
            assert_action_compatible_with_sources(action=action, source_items=items)
        except ActionSourceIncompatibleError as exc:
            allowed = sorted(
                {
                    candidate
                    for item in items
                    for candidate in allowed_actions_for_source_item(item)
                }
            )
            errors.append(
                f"{exc} Use only allowed_actions={allowed} for these exact sources."
            )
    return errors


def _action_source_compatibility_errors(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Fail closed when learner_action cannot express bound approved sources."""
    errors: list[str] = []
    for section in plan.sections:
        errors.extend(_action_source_compatibility_errors_for_section(section, packet))
    return errors


def _unknown_learner_action_errors_for_section(section: TeachingPlanSection) -> list[str]:
    """Section-local variant of ``_unknown_learner_action_errors``."""
    from core.policies.loader import is_known_learner_action, known_learner_actions

    legal = ", ".join(sorted(known_learner_actions()))
    errors: list[str] = []
    for block in section.blocks:
        if block.learner_action is None:
            continue
        action = str(block.learner_action.action or "").strip()
        if is_known_learner_action(action):
            continue
        errors.append(
            "TEACHING_UNKNOWN_LEARNER_ACTION: "
            f"block {block.id!r} learner_action.action={action!r} is not in "
            f"learner-actions.yaml. Legal actions: {legal}."
        )
    return errors


def _unknown_learner_action_errors(plan: TeachingPlan) -> list[str]:
    """Defensive check for legacy plans; new structured output uses a closed enum."""
    errors: list[str] = []
    for section in plan.sections:
        errors.extend(_unknown_learner_action_errors_for_section(section))
    return errors


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _frozen_assessment_reuse_findings_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> list[tuple[str, str, str]]:
    """Section-local variant of ``_frozen_assessment_reuse_findings``."""
    findings: list[tuple[str, str, str]] = []
    stems = [
        (item.id, _normalize_whitespace(item.stem))
        for item in packet.approved_items
        if item.stem.strip()
    ]
    if not stems:
        return findings
    for block in section.blocks:
        if block.task_mode == "assessment" and block.source_question_ids:
            continue
        brief_normalized = _normalize_whitespace(block.brief)
        if not brief_normalized:
            continue
        for item_id, stem_normalized in stems:
            if stem_normalized and stem_normalized in brief_normalized:
                findings.append((section.slot_id, block.id, item_id))
    return findings


def _frozen_assessment_reuse_findings(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[tuple[str, str, str]]:
    """Return (section_id, block_id, item_id) for each verbatim stem reuse."""
    findings: list[tuple[str, str, str]] = []
    for section in plan.sections:
        findings.extend(_frozen_assessment_reuse_findings_for_section(section, packet))
    return findings


_FROZEN_REUSE_MESSAGE = (
    "Use different values, numbers, or scenario for this non-assessment block."
)


def _frozen_reuse_flags_from_findings(
    findings: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    return [
        plan_quality_flag(
            code="TEACHING_FROZEN_ITEM_REUSED",
            source="validator",
            message=(
                f"block {block_id!r} brief reuses approved item {item_id!r}'s "
                "frozen stem text verbatim."
            ),
            section_ids=[section_id],
            block_ids=[block_id],
            repair_instruction=_FROZEN_REUSE_MESSAGE,
        )
        for section_id, block_id, item_id in findings
    ]


def _frozen_assessment_reuse_flags_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> list[dict[str, Any]]:
    return _frozen_reuse_flags_from_findings(
        _frozen_assessment_reuse_findings_for_section(section, packet)
    )


def _frozen_assessment_reuse_flags(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[dict[str, Any]]:
    return _frozen_reuse_flags_from_findings(
        _frozen_assessment_reuse_findings(plan, packet)
    )


def _frozen_assessment_reuse_errors_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Section-local variant of ``_frozen_assessment_reuse_errors``."""
    errors: list[str] = []
    stems = [
        (item.id, _normalize_whitespace(item.stem))
        for item in packet.approved_items
        if item.stem.strip()
    ]
    if not stems:
        return errors
    for block in section.blocks:
        if block.task_mode == "assessment" and block.source_question_ids:
            # This block IS the frozen check; its own stem is expected.
            continue
        brief_normalized = _normalize_whitespace(block.brief)
        if not brief_normalized:
            continue
        for item_id, stem_normalized in stems:
            if stem_normalized and stem_normalized in brief_normalized:
                errors.append(
                    "TEACHING_FROZEN_ITEM_REUSED: "
                    f"block {block.id!r} brief reuses approved item "
                    f"{item_id!r}'s frozen stem text verbatim. Use different "
                    "values, numbers, or scenario for this non-assessment block."
                )
    return errors


def _frozen_assessment_reuse_errors(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Deterministically flag a non-assessment block that restates a frozen
    approved assessment item's exact stem text.

    This is a cheap, low-risk textual check (whitespace-normalized substring
    match) that catches a worked example, model, or practice block leaking an
    approved check's stem, numbers, or scenario verbatim. It never judges
    paraphrase or meaning; the semantic reviewer's `assessment_item_reused`
    finding covers subtler reuse.
    """
    errors: list[str] = []
    for section in plan.sections:
        errors.extend(_frozen_assessment_reuse_errors_for_section(section, packet))
    return errors


_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "that",
        "with",
        "from",
        "this",
        "into",
        "about",
        "which",
        "their",
        "them",
        "then",
        "than",
        "when",
        "what",
        "where",
        "while",
        "have",
        "has",
        "are",
        "was",
        "were",
        "been",
        "being",
        "does",
        "did",
        "can",
        "could",
        "should",
        "would",
        "will",
        "not",
        "use",
        "using",
        "used",
        "each",
        "every",
        "also",
        "over",
        "under",
        "between",
        "check",
        "select",
        "selects",
        "learner",
        "learners",
        "explain",
        "explains",
    }
)


def _token_set(*texts: str) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
            if len(tok) > 3 and tok not in _STOPWORDS:
                tokens.add(tok)
    return tokens


def _assessment_item_compatible_with_block(
    *,
    block: Any,
    item: Any,
    packet: ImmutableLessonPacket,
) -> bool:
    """Require kind-legal forms plus non-empty concept/purpose overlap."""
    forms = _assessment_forms_for_intent(block.intent)
    kind = approved_item_kind(item)
    if kind == "multiple_choice" and "choices" not in forms:
        return False
    if kind == "open_response" and "questions" not in forms:
        return False
    stem = str(getattr(item, "stem", "") or "")
    item_tokens = _token_set(stem)
    scope_tokens = _token_set(
        block.brief,
        block.evidence,
        packet.lesson.objective,
        " ".join(packet.scope.terminology),
        " ".join(entry.statement for entry in packet.scope.must_establish),
        packet.anchor.description or "",
    )
    if not item_tokens or not scope_tokens:
        return False
    return bool(item_tokens & scope_tokens)


def _repair_briefs_missing_anchor_grounding_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> None:
    """Section-local variant of ``_repair_briefs_missing_anchor_grounding``."""
    terminology = {term.lower() for term in packet.scope.terminology}
    anchor_vocabulary = anchor_terms(packet.anchor.description or "")
    if not terminology and packet.scope.must_establish:
        terminology = set().union(
            *(anchor_terms(entry.statement) for entry in packet.scope.must_establish)
        )
    tokens = sorted(terminology | anchor_vocabulary, key=len, reverse=True)
    if not tokens:
        return
    ground = ", ".join(tokens[:4])
    for block in section.blocks:
        brief_l = block.brief.lower()
        grounded = (
            packet.anchor.id in block.brief
            or any(word in brief_l for word in anchor_vocabulary)
            or any(term and term in brief_l for term in terminology)
        )
        if grounded:
            continue
        block.brief = f"{block.brief.rstrip()} Use owned terms: {ground}."


def _repair_briefs_missing_anchor_grounding(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Append owned vocabulary when a brief fails BRIEF_NO_ANCHOR_OR_TERM."""
    for section in plan.sections:
        _repair_briefs_missing_anchor_grounding_for_section(section, packet)


def _repair_sources_outside_structural_slots_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> None:
    """Section-local variant of ``_repair_sources_outside_structural_slots``."""
    required = set(packet.required_assessment_slots)
    if not required or section.slot_id in required:
        return
    for block in section.blocks:
        # Structural question planning is authoritative. Optional teaching
        # blocks cannot steal a source reserved for the planned check/practice.
        block.source_question_ids = []


def _repair_sources_outside_structural_slots(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Keep assessment ownership in the slots selected by structural planning."""
    for section in plan.sections:
        _repair_sources_outside_structural_slots_for_section(section, packet)


def _repair_incompatible_assessment_sources_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> None:
    """Section-local variant of ``_repair_incompatible_assessment_sources``."""
    by_id = {item.id: item for item in packet.approved_items}
    for block in section.blocks:
        if not block.source_question_ids:
            continue
        missing = [sid for sid in block.source_question_ids if sid not in by_id]
        if missing:
            block.source_question_ids = []
            continue
        kinds = {approved_item_kind(by_id[sid]) for sid in block.source_question_ids}
        forms = _assessment_forms_for_intent(block.intent)
        incompatible_kind = (
            (kinds == {"multiple_choice"} and "choices" not in forms)
            or (kinds == {"open_response"} and "questions" not in forms)
            or len(kinds) > 1
        )
        if incompatible_kind:
            block.source_question_ids = []


def _repair_incompatible_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Drop source bindings that cannot survive closed Print selection.

    Action incompatibility is intentionally NOT silently repaired here: if a
    required source is MCQ and the model chose enter-text, the repair loop must
    change the action, not mutate approved assessment meaning.
    """
    for section in plan.sections:
        _repair_incompatible_assessment_sources_for_section(section, packet)


def _repair_missing_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    assessment_intents: set[str],
) -> list[str]:
    """Bind approved items without guessing or moving structural ownership.

    If structural planning named assessment slots, only those slots may consume
    approved items and each such slot must own one compatible source. Otherwise
    legacy check/diagnose intents remain required while other assessment-capable
    intents are optional.
    """
    bind_intents = {
        "check-understanding",
        "diagnose-misconception",
        "practise-independent",
        "practise-guided",
        "classify",
        "apply",
        "transfer",
        "evaluate",
    } & set(assessment_intents)
    required_intents = {"check-understanding", "diagnose-misconception"}

    used = {
        source_id
        for section in plan.sections
        for block in section.blocks
        for source_id in block.source_question_ids
    }
    available = [item for item in packet.approved_items if item.id not in used]

    priority = (
        "check-understanding",
        "diagnose-misconception",
        "practise-independent",
        "practise-guided",
        "classify",
        "apply",
        "transfer",
        "evaluate",
    )

    def _ordered_candidates(section: Any) -> list[Any]:
        out: list[Any] = []
        for intent_name in priority:
            for block in section.blocks:
                if block.intent == intent_name and block.intent in bind_intents:
                    out.append(block)
        for block in section.blocks:
            if block.intent in bind_intents and block not in out:
                out.append(block)
        return out

    ownership_errors: list[str] = []
    required_slots = list(dict.fromkeys(packet.required_assessment_slots))
    if required_slots:
        sections_by_id = {section.slot_id: section for section in plan.sections}
        for slot_id in required_slots:
            section = sections_by_id.get(slot_id)
            if section is None:
                ownership_errors.append(
                    "TEACHING_MISSING_ASSESSMENT_OWNERSHIP: structural assessment "
                    f"slot {slot_id!r} is missing from the teaching plan."
                )
                continue
            if any(block.source_question_ids for block in section.blocks):
                continue
            match_block = None
            match_item = None
            for block in _ordered_candidates(section):
                for item in available:
                    if item.id in used:
                        continue
                    if _assessment_item_compatible_with_block(
                        block=block, item=item, packet=packet
                    ):
                        match_block = block
                        match_item = item
                        break
                if match_item is not None:
                    break
            if match_block is None or match_item is None:
                ownership_errors.append(
                    "TEACHING_MISSING_ASSESSMENT_OWNERSHIP: structural assessment "
                    f"slot {slot_id!r} requires one approved source on an eligible "
                    "assessment block. Use only the provided approved_sources; do not "
                    "move the task to another slot or invent an item."
                )
                continue
            match_block.source_question_ids = [match_item.id]
            used.add(match_item.id)
        return ownership_errors

    # Legacy packets without an upstream question-plan slot contract.
    for section in plan.sections:
        for block in _ordered_candidates(section):
            if block.source_question_ids:
                continue
            match = None
            for item in available:
                if item.id in used:
                    continue
                if _assessment_item_compatible_with_block(
                    block=block, item=item, packet=packet
                ):
                    match = item
                    break
            if match is not None:
                block.source_question_ids = [match.id]
                used.add(match.id)
                continue
            if block.intent in required_intents:
                ownership_errors.append(
                    "TEACHING_MISSING_ASSESSMENT_OWNERSHIP: block "
                    f"{block.id!r} intent={block.intent!r} requires an approved "
                    "assessment source whose kind matches legal forms and whose stem "
                    "overlaps the block brief/objective/owned vocabulary. Do not guess "
                    "an unrelated item."
                )
    return ownership_errors


def _repair_missing_figure_visuals_for_section(
    section: TeachingPlanSection, packet: ImmutableLessonPacket
) -> list[dict[str, str]]:
    """Section-local variant of ``_repair_missing_figure_visuals``."""
    if not packet.backbone:
        return []
    figures = {
        str(f["id"]): f
        for f in (packet.backbone.get("figures") or [])
        if isinstance(f, dict) and f.get("id")
    }
    changes: list[dict[str, str]] = []
    for block in section.blocks:
        required = list(
            dict.fromkeys(
                str(ref["figure_id"])
                for sid in block.source_question_ids
                if (ref := packet.item_backbone_refs.get(sid) or {}).get("figure_id")
                and str(ref["figure_id"]) in figures
            )
        )
        if len(required) != 1:
            continue
        fid = required[0]
        figure = figures[fid]
        try:
            backbone_figure = BackboneFigure.model_validate(figure)
        except ValueError:
            continue
        mode = backbone_figure.effective_mode
        must_show = list(backbone_figure.must_show)
        labels = list(backbone_figure.labels_required)
        if block.visual is None:
            if not must_show and mode == "diagram":
                must_show = [backbone_figure.purpose]
            block.visual = VisualSpec(
                figure_ref=fid,
                mode=mode,
                purpose=backbone_figure.purpose,
                must_show=must_show,
                labels_required=labels,
            )
            changes.append(
                {"block_id": block.id, "figure_id": fid, "action": "created_visual"}
            )
        elif block.visual.figure_ref is None:
            visual = block.visual
            visual.figure_ref = fid
            visual.mode = mode
            visual.must_show = list(dict.fromkeys([*visual.must_show, *must_show]))
            visual.labels_required = list(
                dict.fromkeys([*visual.labels_required, *labels])
            )
            changes.append(
                {"block_id": block.id, "figure_id": fid, "action": "linked_visual"}
            )
    return changes


def _repair_missing_figure_visuals(
    plan: TeachingPlan, packet: ImmutableLessonPacket
) -> list[dict[str, str]]:
    """Attach the backbone figure a block's approved question relies on.

    Deterministic and conservative: only acts when exactly one backbone figure is
    required by the block's owned questions and the block does not already name
    a different figure. Anything else is left for validation to report.
    """
    changes: list[dict[str, str]] = []
    for section in plan.sections:
        changes.extend(_repair_missing_figure_visuals_for_section(section, packet))
    return changes


def _repair_invalid_evidence_refs_for_section(
    section: TeachingPlanSection,
    packet: ImmutableLessonPacket,
) -> None:
    """Section-local variant of ``_repair_invalid_evidence_refs``."""
    allowed = allowed_teaching_evidence_refs(packet)
    for block in section.blocks:
        block.evidence_refs = [ref for ref in block.evidence_refs if ref in allowed]


def _repair_invalid_evidence_refs(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Drop only evidence references that cannot resolve in this packet."""
    for section in plan.sections:
        _repair_invalid_evidence_refs_for_section(section, packet)


def _assessment_source_policy(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
) -> dict[str, Any]:
    """Project exact validator-owned assessment facts into every planner attempt."""
    assessment_intents = sorted(
        intent_id
        for intent_id, objects in snapshot.compatible_objects_by_intent.items()
        if {"questions", "choices"} & set(objects)
    )
    approved_sources = [
        {
            "approved_item_id": item.id,
            "kind": approved_item_kind(item),
            "stem": item.stem,
            "allowed_actions": list(allowed_actions_for_source_item(item)),
            "evidence_ref": f"item.{item.id}",
        }
        for item in packet.approved_items
    ]
    required_slots = list(packet.required_assessment_slots)
    return {
        "eligible_intents": assessment_intents,
        "required_assessment_slots": required_slots,
        "approved_sources": approved_sources,
        "rules": {
            "copy_ids_verbatim": True,
            "copy_evidence_refs_verbatim": True,
            "action_must_be_from_bound_source_allowed_actions": True,
            "response_action_requires_approved_source": True,
            "source_requires_learner_action": True,
            "multiple_choice_ids_per_block": "0_or_1",
            # Retain the historical projection for downstream diagnostics;
            # the authoritative mode-specific rules above still distinguish
            # formative tasks from assessment ownership.
            "selection_is_optional": True,
            "source_only_on_eligible_intent": True,
            "source_only_in_required_assessment_slots": bool(required_slots),
            "reuse_across_blocks": "forbidden",
            "item_kind_is_fixed_upstream": True,
        },
        "forbidden_terminology": [
            entry.statement for entry in packet.scope.must_not_introduce
        ],
        "allowed_evidence_refs": sorted(allowed_teaching_evidence_refs(packet)),
    }
