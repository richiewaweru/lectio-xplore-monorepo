from pathlib import Path
import re

path = Path("apps/textbook-agent/backend/src/print/generation/whole_lesson/teaching_agent.py")
text = path.read_text(encoding="utf-8")

if "import re\n" not in text:
    text = text.replace("import json\n", "import json\nimport re\n")

old_order = '''def _repair_missing_order_learner_actions(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
) -> None:
    """Attach order-items when the objective is ordering and teaching omitted action.

    Sequence is the only generation-ready Learn interaction writer. Ordering
    objectives that land on sequence / practise-guided / check-understanding
    without a learner_action otherwise produce content-only Learn surfaces.
    """
    objective = f"{packet.lesson.objective} {plan.arc}".lower()
    if not any(
        token in objective
        for token in ("order", "sequence", "stages", "cycle", "procedure", "steps")
    ):
        return
    if any(block.learner_action is not None for section in plan.sections for block in section.blocks):
        return
    preferred = ("sequence", "practise-guided", "check-understanding")
    target = None
    for intent_name in preferred:
        for section in plan.sections:
            for block in section.blocks:
                if block.intent == intent_name and block.learner_action is None:
                    target = block
                    break
            if target is not None:
                break
        if target is not None:
            break
    if target is None:
        return
    # Do not inherit assessment question ids — they are usually MC/open and
    # break Sequence work-order compilation. Empty sources let the Sequence
    # writer synthesize steps from the teaching block content.
    target.learner_action = LearnerActionBrief(
        action="order-items",
        support_level="guided" if target.intent != "check-understanding" else "independent",
        evidence=(
            "Objective requires reconstructing an ordered sequence; "
            "attach a Sequence interaction so the learner can respond."
        ),
        source_item_ids=[],
    )


'''

new_order = '''def _objective_requires_order_reconstruction(
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
    if any(
        block.learner_action is not None
        for section in plan.sections
        for block in section.blocks
    ):
        return []
    preferred = ("sequence", "practise-guided", "check-understanding")
    has_candidate_block = any(
        block.intent in preferred
        for section in plan.sections
        for block in section.blocks
    )
    if not has_candidate_block:
        return [
            "TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
            "ordered sequence, but no sequence/practise-guided/check-understanding "
            "block exists to own an order-items learner_action."
        ]
    return [
        "TEACHING_MISSING_ORDER_ACTION: objective requires reconstructing an "
        "ordered sequence, but no block declares a learner_action. Emit "
        "learner_action.action='order-items' on a sequence, practise-guided, or "
        "check-understanding block. Do not leave Learn to invent Sequence."
    ]


def _token_set(*texts: str) -> set[str]:
    tokens: set[str] = set()
    for text in texts:
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
            if len(tok) > 2:
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


'''

if old_order not in text:
    raise SystemExit("order repair block not found")
text = text.replace(old_order, new_order)

old_assess = '''def _repair_missing_assessment_sources(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    assessment_intents: set[str],
) -> None:
    """Assign unused approved cards when a model omits assessment ownership.

    Print closed selection rejects questions/choices without sources. Only bind
    for intents whose primary job is assessment/practice — never for orient /
    explain content blocks that merely list choices as an optional form.
    Kind must match forms legal for the intent (MC → choices; open → questions).
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
    available_by_kind: dict[str, list[str]] = {
        "multiple_choice": [],
        "open_response": [],
    }
    for item in packet.approved_items:
        if item.id in used:
            continue
        available_by_kind[approved_item_kind(item)].append(item.id)

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

    for block in ordered_blocks:
        if block.intent not in bind_intents:
            continue
        forms = _assessment_forms_for_intent(block.intent)
        pool: list[str] = []
        if "choices" in forms and available_by_kind["multiple_choice"]:
            pool = available_by_kind["multiple_choice"]
        elif "questions" in forms and available_by_kind["open_response"]:
            pool = available_by_kind["open_response"]
        if not pool:
            continue
        block.source_question_ids = [pool.pop(0)]


'''

new_assess = '''def _repair_missing_assessment_sources(
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
    by_id = {item.id: item for item in packet.approved_items}
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


'''

if old_assess not in text:
    raise SystemExit("assessment repair block not found")
text = text.replace(old_assess, new_assess)

old_call = '''            _repair_briefs_missing_anchor_grounding(plan, packet)
            _repair_missing_order_learner_actions(plan, packet)
            _repair_incompatible_assessment_sources(plan, packet)
            _repair_missing_assessment_sources(
                plan,
                packet,
                set(assessment_source_policy["eligible_intents"]),
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
            if validation.ok:
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
            ]
            output_invalid_details = repair_errors
'''

new_call = '''            _repair_briefs_missing_anchor_grounding(plan, packet)
            ownership_errors = _missing_order_learner_action_errors(plan, packet)
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
'''

if old_call not in text:
    raise SystemExit("call site block not found")
text = text.replace(old_call, new_call)

# LearnerActionBrief may become unused — keep import; still used elsewhere? check
path.write_text(text, encoding="utf-8")
print("teaching_agent.py updated")
