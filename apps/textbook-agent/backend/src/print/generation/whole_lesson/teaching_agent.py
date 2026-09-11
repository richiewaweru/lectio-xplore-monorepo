"""STANDARD-tier whole-lesson teaching approach agent."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic_ai import Agent

from core.config import settings
from core.llm.runner import RetryPolicy, run_llm
from curriculum.approved_items import approved_item_kind
from print.generation.catalogue_projections import (
    TeachingGuidanceProjection,
    project_teaching_guidance,
)
from curriculum.llm_contract_errors import is_transport_error, structured_output_errors
from print.generation.whole_lesson.legality import (
    LessonLegalitySnapshot,
    build_lesson_legality_snapshot,
    project_slot_intent_policy,
    snapshot_as_teaching_sets,
)
from print.generation.whole_lesson.packet import ImmutableLessonPacket
from print.generation.whole_lesson.prompt_render import render_teaching_prompt
from print.generation.whole_lesson.teaching_errors import (
    TeachingPlanOutputInvalidError,
    is_recognized_teaching_output_error,
)
from print.generation.whole_lesson.teaching_plan import (
    TeachingPlan,
    TeachingPlanDraft,
    materialize_teaching_plan,
)
from print.resources.selection import _form_cards
from print.generation.whole_lesson.validation import (
    ValidationReport,
    advisory_teaching_qc,
    allowed_teaching_evidence_refs,
    anchor_terms,
    validate_teaching_plan,
)
from v3_execution.config import get_v3_model, get_v3_model_settings, get_v3_slot, get_v3_spec
from v3_execution.config.models import V2_LESSON_APPROACH_PLANNER
from v3_execution.llm_helpers import NO_OUTPUT_RETRY, prepare_structured_agent


@dataclass
class TeachingPlanAttempt:
    prompt: str
    raw_response: str
    plan: TeachingPlan | None
    validation: ValidationReport
    qc: list[dict[str, Any]]
    attempt: int
    error: str | None = None


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
    """Fail closed when ordering is required but teaching omitted learner_action.

    Learn must not invent Sequence downstream. The model must emit the action
    through the teaching repair loop.
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
    # Ordering ownership belongs on sequence / guided-practice blocks, not on
    # every check-understanding assessment block.
    preferred = ("sequence", "practise-guided")
    preferred_blocks = [
        block
        for section in plan.sections
        for block in section.blocks
        if block.intent in preferred
    ]
    if not preferred_blocks:
        return [
            "TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
            "ordered sequence, but no sequence/practise-guided block exists to own "
            "an order-items learner_action."
        ]
    return [
        "TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
        "ordered sequence, but no sequence/practise-guided block declares "
        "learner_action.action='order-items'. Do not leave Learn to invent Sequence."
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
    """Fail closed when evidence-bearing check/practice blocks omit learner_action.

    Legitimate passive blocks (read/observe/worked-example follow) stay allowed.
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


def _action_source_compatibility_errors(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> list[str]:
    """Fail closed when learner_action cannot express bound approved sources."""
    from curriculum.teaching_plan.compatibility import (
        ActionSourceIncompatibleError,
        assert_action_compatible_with_sources,
    )

    by_id = {item.id: item for item in packet.approved_items}
    errors: list[str] = []
    for section in plan.sections:
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
                hint = ""
                if action == "enter-text":
                    hint = (
                        " Prefer action='select-one' or 'select-many' when the "
                        "block binds multiple-choice sources; keep enter-text "
                        "only when sources are open_response or unbound."
                    )
                errors.append(f"{exc}{hint}")
    return errors


def _unknown_learner_action_errors(plan: TeachingPlan) -> list[str]:
    """Fail closed when learner_action.action is outside learner-actions.yaml."""
    from core.policies.loader import is_known_learner_action, known_learner_actions

    legal = ", ".join(sorted(known_learner_actions()))
    errors: list[str] = []
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action is None:
                continue
            action = str(block.learner_action.action or "").strip()
            if is_known_learner_action(action):
                continue
            hint = ""
            if action == "describe-in-own-words":
                hint = (
                    " Use action='enter-text' (only without multiple-choice "
                    "source binding) and put 'describe in own words' in "
                    "target/purpose; if the block owns MC sources, use "
                    "select-one or select-many instead."
                )
            errors.append(
                "TEACHING_UNKNOWN_LEARNER_ACTION: "
                f"block {block.id!r} learner_action.action={action!r} is not in "
                f"learner-actions.yaml. Legal actions: {legal}.{hint}"
            )
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
        "into",
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


def _repair_briefs_missing_anchor_grounding(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Append owned vocabulary when a brief fails BRIEF_NO_ANCHOR_OR_TERM.

    Writers are steered to name the anchor in prose; models sometimes omit every
    owned token. Prefer terminology / must_establish / anchor description words
    over synthetic ids (ids remain a validator escape hatch, not the repair).
    """
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
    for section in plan.sections:
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


def _repair_incompatible_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Drop source bindings that cannot survive closed Print selection.

    MC items require ``choices``; open-response items require ``questions``.
    When the intent does not support the matching form, clear sources so
    non-assessment forms (e.g. worked-example) remain selectable.
    """
    by_id = {item.id: item for item in packet.approved_items}
    for section in plan.sections:
        for block in section.blocks:
            if not block.source_question_ids:
                continue
            missing = [sid for sid in block.source_question_ids if sid not in by_id]
            if missing:
                block.source_question_ids = []
                continue
            kinds = {approved_item_kind(by_id[sid]) for sid in block.source_question_ids}
            forms = _assessment_forms_for_intent(block.intent)
            if kinds == {"multiple_choice"} and "choices" not in forms:
                block.source_question_ids = []
            elif kinds == {"open_response"} and "questions" not in forms:
                block.source_question_ids = []
            elif len(kinds) > 1:
                block.source_question_ids = []


def _repair_missing_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    assessment_intents: set[str],
) -> list[str]:
    """Bind unused approved cards only on kind + concept/purpose overlap.

    Never guess with pool.pop(0). When an assessment-owning block still lacks a
    compatible source, return a structured repair request for the model.
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

    ordered_blocks = []
    for intent_name in priority:
        for section in plan.sections:
            for block in section.blocks:
                if block.intent == intent_name and not block.source_question_ids:
                    ordered_blocks.append(block)
    for section in plan.sections:
        for block in section.blocks:
            if (
                block not in ordered_blocks
                and block.intent in bind_intents
                and not block.source_question_ids
            ):
                ordered_blocks.append(block)

    ownership_errors: list[str] = []
    for block in ordered_blocks:
        if block.intent not in bind_intents:
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
        if match is None:
            ownership_errors.append(
                "TEACHING_MISSING_ASSESSMENT_OWNERSHIP: block "
                f"{block.id!r} intent={block.intent!r} requires an approved "
                "assessment source whose kind matches legal forms and whose stem "
                "overlaps the block brief/objective/owned vocabulary. Do not guess "
                "an unrelated item."
            )
            continue
        block.source_question_ids = [match.id]
        used.add(match.id)
    return ownership_errors


def _repair_invalid_evidence_refs(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Drop only evidence references that cannot resolve in this packet."""
    allowed = allowed_teaching_evidence_refs(packet)
    for section in plan.sections:
        for block in section.blocks:
            block.evidence_refs = [
                ref for ref in block.evidence_refs if ref in allowed
            ]


def _assessment_source_policy(
    packet: ImmutableLessonPacket,
    snapshot: LessonLegalitySnapshot,
) -> dict[str, Any]:
    """Project validator-owned assessment facts into both planner attempts."""
    assessment_intents = sorted(
        intent_id
        for intent_id, objects in snapshot.compatible_objects_by_intent.items()
        if {"questions", "choices"} & set(objects)
    )
    approved_sources = [
        {
            "approved_item_id": item.id,
            "kind": approved_item_kind(item),
        }
        for item in packet.approved_items
    ]
    return {
        "eligible_intents": assessment_intents,
        "approved_sources": approved_sources,
        "rules": {
            "selection_is_optional": True,
            "multiple_choice_ids_per_block": "0_or_1",
            "source_only_on_eligible_intent": True,
            "reuse_across_blocks": "forbidden",
            "item_kind_is_fixed_upstream": True,
        },
        "forbidden_terminology": [
            entry.statement for entry in packet.scope.must_not_introduce
        ],
        "allowed_evidence_refs": sorted(allowed_teaching_evidence_refs(packet)),
    }


async def _call_teaching_model(
    *,
    prompt: str,
    user_payload: dict[str, Any],
    trace_id: str,
    generation_id: str | None,
    attempt_start: int = 1,
) -> tuple[TeachingPlanDraft, str]:
    model, provider_output, structured_context, spec, _source = prepare_structured_agent(
        node_name=V2_LESSON_APPROACH_PLANNER,
        output_type=TeachingPlanDraft,
    )
    slot = get_v3_slot(V2_LESSON_APPROACH_PLANNER)
    system_prompt, _, _user = prompt.partition("\n\n## USER INPUT\n\n")
    agent = Agent(
        model=model,
        output_type=provider_output,
        system_prompt=system_prompt or prompt,
        retries=NO_OUTPUT_RETRY,
    )
    result = await run_llm(
        trace_id=trace_id,
        caller="v2_lesson_approach_planner",
        generation_id=generation_id,
        agent=agent,
        user_prompt=json.dumps(user_payload, indent=2, sort_keys=True),
        model=model,
        slot=slot,
        spec=spec,
        node=V2_LESSON_APPROACH_PLANNER,
        model_settings=get_v3_model_settings(V2_LESSON_APPROACH_PLANNER),
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(settings.page_lesson_plan_timeout_seconds),
        ),
        attempt_start=attempt_start,
        structured_context=structured_context,
    )
    raw = result.output
    raw_text = (
        raw.model_dump_json()
        if hasattr(raw, "model_dump_json")
        else json.dumps(raw, default=str)
    )
    if isinstance(raw, TeachingPlanDraft):
        return raw, raw_text
    if hasattr(raw, "model_dump"):
        return TeachingPlanDraft.model_validate(raw.model_dump()), raw_text
    return TeachingPlanDraft.model_validate(raw), raw_text


async def run_lesson_approach_planner(
    packet: ImmutableLessonPacket,
    *,
    legality: LessonLegalitySnapshot | None = None,
    trace_id: str | None = None,
    generation_id: str | None = None,
    require_items: bool = True,
) -> TeachingPlanResult:
    if require_items and not packet.approved_items:
        from curriculum.approved_items import ItemPoolEmptyError

        raise ItemPoolEmptyError(card_id="unknown", pack_id=None)

    snapshot = legality or build_lesson_legality_snapshot(packet)
    permitted, excluded, typical_by_slot = snapshot_as_teaching_sets(snapshot)
    teaching_guidance = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents={key: "excluded" for key in excluded},
    )
    slot_intent_policy = project_slot_intent_policy(snapshot)
    assessment_source_policy = _assessment_source_policy(packet, snapshot)
    prompt = render_teaching_prompt(packet, teaching_guidance, resource_id=packet.resource_id)
    user_payload = {
        "fixed_input": packet.planner_payload(),
        "teaching_guidance": teaching_guidance.to_dict(),
        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
        "assessment_source_policy": assessment_source_policy,
        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
    }
    attempts: list[TeachingPlanAttempt] = []
    last_error: str | None = None
    plan: TeachingPlan | None = None
    validation = ValidationReport(ok=False, issues=[])
    raw_response = ""
    previous_output: object | None = None
    repair_errors: list[str] = []
    last_exception: Exception | None = None
    output_invalid_details: list[str] = []
    tid = trace_id or str(uuid.uuid4())

    for attempt in (1, 2):
        last_exception = None
        try:
            call_payload = user_payload
            if attempt == 2 and repair_errors:
                call_payload = {
                    **user_payload,
                    "repair": {
                        "instruction": (
                            "Return the complete corrected TeachingPlan JSON. "
                            "Change only fields required to satisfy these errors. "
                            "Use only intents listed under slot_intent_policy for each slot."
                            " For the check-understanding block, when approved "
                            "items exist, include at least one approved "
                            "source_question_id. For a "
                            "multiple-choice assessment block, select exactly one "
                            "approved item ID; never group IDs or reuse an ID. Attach it "
                            "only to an assessment_source_policy eligible intent. Remove "
                            "forbidden terminology and use only allowed_evidence_refs."
                        ),
                        "previous_output": previous_output,
                        "validation_errors": repair_errors,
                        "slot_intent_policy": slot_intent_policy["slot_intent_policy"],
                        "legality_catalogue_hash": slot_intent_policy["catalogue_hash"],
                        "assessment_source_policy": assessment_source_policy,
                    },
                }
            draft, raw_response = await _call_teaching_model(
                prompt=prompt,
                user_payload=call_payload,
                trace_id=f"{tid}:attempt{attempt}",
                generation_id=generation_id,
                attempt_start=attempt,
            )
            previous_output = draft.model_dump(mode="json")
            try:
                plan = materialize_teaching_plan(
                    draft,
                    slot_ids=[slot.slot_id for slot in packet.slots],
                )
            except ValueError as exc:
                last_error = "validation_failed"
                repair_errors = [str(exc)]
                output_invalid_details = repair_errors
                attempts.append(
                    TeachingPlanAttempt(
                        prompt=prompt,
                        raw_response=raw_response,
                        plan=None,
                        validation=ValidationReport(ok=False, issues=[]),
                        qc=[],
                        attempt=attempt,
                        error=str(exc),
                    )
                )
                continue
            _repair_briefs_missing_anchor_grounding(plan, packet)
            ownership_errors = _missing_order_learner_action_errors(plan, packet)
            ownership_errors.extend(_missing_check_practice_action_errors(plan))
            ownership_errors.extend(_unknown_learner_action_errors(plan))
            ownership_errors.extend(_action_source_compatibility_errors(plan, packet))
            _repair_incompatible_assessment_sources(plan, packet)
            ownership_errors.extend(
                _repair_missing_assessment_sources(
                    plan,
                    packet,
                    set(assessment_source_policy["eligible_intents"]),
                )
            )
            _repair_invalid_evidence_refs(plan, packet)
            validation = validate_teaching_plan(
                plan,
                packet,
                permitted_intents=permitted,
                excluded_intents=excluded,
                typical_by_slot=typical_by_slot,
                assessment_intents=set(
                    assessment_source_policy["eligible_intents"]
                ),
            )
            qc = [finding.to_dict() for finding in advisory_teaching_qc(plan)]
            attempts.append(
                TeachingPlanAttempt(
                    prompt=prompt,
                    raw_response=raw_response,
                    plan=plan,
                    validation=validation,
                    qc=qc,
                    attempt=attempt,
                )
            )
            if validation.ok and not ownership_errors:
                return TeachingPlanResult(
                    plan=plan,
                    validation=validation,
                    qc=qc,
                    prompt=prompt,
                    raw_response=raw_response,
                    teaching_guidance=teaching_guidance,
                    attempts=attempts,
                    typical_by_slot=typical_by_slot,
                    permitted_intents=permitted,
                    excluded_intents=excluded,
                    legality=snapshot,
                )
            last_error = "validation_failed"
            repair_errors = [
                f"{issue.code}: {issue.message}" for issue in validation.issues
            ] + ownership_errors
            output_invalid_details = repair_errors
        except Exception as exc:
            last_exception = exc
            last_error = str(exc)
            attempts.append(
                TeachingPlanAttempt(
                    prompt=prompt,
                    raw_response=raw_response,
                    plan=plan,
                    validation=validation,
                    qc=[],
                    attempt=attempt,
                    error=last_error,
                )
            )
            if is_transport_error(exc):
                # Provider/backoff retry — do not invent contract repair context.
                repair_errors = []
                previous_output = previous_output
            elif is_recognized_teaching_output_error(exc):
                repair_errors = structured_output_errors(exc)
                output_invalid_details = repair_errors
            else:
                # Only teaching-output noncompliance owns the recoverable contract.
                # Generic provider behavior and programming/input failures remain terminal.
                from pydantic_ai.exceptions import UnexpectedModelBehavior

                if isinstance(exc, UnexpectedModelBehavior):
                    raise
                repair_errors = structured_output_errors(exc)
                if previous_output is None and raw_response:
                    try:
                        previous_output = json.loads(raw_response)
                    except Exception:  # noqa: BLE001
                        previous_output = raw_response
            continue

    if last_exception is not None and is_transport_error(last_exception):
        last_exception.add_note(
            "lesson approach planner exhausted "
            f"{len(attempts)} provider attempts"
        )
        raise last_exception

    if last_error == "validation_failed" or (
        last_exception is not None
        and is_recognized_teaching_output_error(last_exception)
    ):
        raise TeachingPlanOutputInvalidError(
            attempt_count=len(attempts),
            details=output_invalid_details,
        ) from last_exception

    raise RuntimeError(
        f"lesson approach planner failed after {len(attempts)} attempts: {last_error}"
        + (
            f" issues={validation.to_dict()['issues']}"
            if last_error == "validation_failed" and validation.issues
            else ""
        )
    )
