"""Hard validation and advisory QC for whole-lesson teaching and form plans."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from contracts.lectio_page import PAGE_OBJECT_IDS
from planning.page_blocks import validate_intent_departure
from planning.whole_lesson.form_plan import FormPlan
from planning.whole_lesson.packet import ImmutableLessonPacket
from planning.whole_lesson.teaching_plan import TeachingPlan

BANNED_BRIEF_PHRASES = (
    "explain the concept clearly",
    "give a useful example",
    "provide an engaging introduction",
    "ask students what they learned",
    "help learners understand",
    "create a clear explanation",
)

REQUIRED_SLOTS = ("orient", "explain", "confront", "check")


@dataclass
class ValidationIssue:
    code: str
    message: str
    path: str = ""
    blocking: bool = True


@dataclass
class ValidationReport:
    ok: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "path": issue.path,
                    "blocking": issue.blocking,
                }
                for issue in self.issues
            ],
        }


@dataclass
class AdvisoryFinding:
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "path": self.path}


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def _contains_object_id(text: str) -> str | None:
    """Detect page-object catalogue leaks without flagging ordinary English.

    Hyphenated catalogue ids (worked-example, answer-key) must never appear.
    Bare English object names (questions, list, prose, table, ...) are only
    treated as leaks when quoted as exact JSON string values — i.e. form/object
    selection — not when they appear inside teaching prose.
    """
    lowered = text.lower()
    for object_id in PAGE_OBJECT_IDS:
        oid = object_id.lower()
        if "-" in oid:
            if oid in lowered:
                return object_id
            continue
        if f'"{oid}"' in lowered:
            return object_id
    return None


def validate_teaching_plan(
    plan: TeachingPlan,
    packet: ImmutableLessonPacket,
    *,
    permitted_intents: set[str],
    excluded_intents: set[str],
    typical_by_slot: dict[str, set[str]],
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    slot_ids = [section.slot_id for section in plan.sections]
    expected_slots = [slot.slot_id for slot in packet.slots] or list(REQUIRED_SLOTS)
    if slot_ids != expected_slots:
        issues.append(
            ValidationIssue(
                code="SLOT_ORDER",
                message=f"sections must be {expected_slots} in order; got {slot_ids}",
                path="sections",
            )
        )

    seen_block_ids: set[str] = set()
    total_blocks = 0
    must_ids = {entry.id for entry in packet.scope.must_establish}
    referenced_must: set[str] = set()
    approved_ids = set(packet.approved_item_ids())
    misconception_ids = {item.id for item in packet.misconceptions}
    terminology = {term.lower() for term in packet.scope.terminology}
    excluded_terms = {
        entry.statement.lower() for entry in packet.scope.must_not_introduce
    }

    for section in plan.sections:
        if not section.blocks:
            issues.append(
                ValidationIssue(
                    code="EMPTY_SECTION",
                    message=f"section {section.slot_id!r} has no blocks",
                    path=f"sections.{section.slot_id}",
                )
            )
        if len(section.blocks) > packet.limits.max_blocks_per_section:
            issues.append(
                ValidationIssue(
                    code="SECTION_BLOCK_LIMIT",
                    message="section exceeds max_blocks_per_section",
                    path=f"sections.{section.slot_id}",
                )
            )
        typical = typical_by_slot.get(section.slot_id, set())
        for index, block in enumerate(section.blocks):
            total_blocks += 1
            path = f"sections.{section.slot_id}.blocks[{index}]"
            if block.position != index:
                issues.append(
                    ValidationIssue(
                        code="POSITION",
                        message=f"expected position {index}",
                        path=path,
                    )
                )
            if block.id in seen_block_ids:
                issues.append(
                    ValidationIssue(
                        code="DUPLICATE_BLOCK_ID",
                        message=f"duplicate block id {block.id!r}",
                        path=path,
                    )
                )
            seen_block_ids.add(block.id)
            try:
                validate_intent_departure(
                    intent=block.intent,
                    typical_intents=typical,
                    permitted_intents=permitted_intents,
                    excluded_intents=excluded_intents,
                    departure_reason=block.departure_reason,
                )
            except ValueError as exc:
                issues.append(
                    ValidationIssue(code="INTENT_LEGALITY", message=str(exc), path=path)
                )

            leaked = _contains_object_id(block.brief) or _contains_object_id(block.evidence)
            if leaked:
                issues.append(
                    ValidationIssue(
                        code="OBJECT_LEAK",
                        message=f"page-object id {leaked!r} appears in teaching artifact",
                        path=path,
                    )
                )

            if _word_count(block.brief) < 15:
                issues.append(
                    ValidationIssue(
                        code="BRIEF_TOO_SHORT",
                        message="brief has fewer than 15 words",
                        path=f"{path}.brief",
                    )
                )
            brief_l = block.brief.lower()
            if packet.anchor.id not in block.brief and not any(
                term and term in brief_l for term in terminology
            ):
                issues.append(
                    ValidationIssue(
                        code="BRIEF_NO_ANCHOR_OR_TERM",
                        message="brief must mention anchor id or approved terminology",
                        path=f"{path}.brief",
                    )
                )
            for phrase in BANNED_BRIEF_PHRASES:
                if phrase in brief_l:
                    issues.append(
                        ValidationIssue(
                            code="BRIEF_GENERIC",
                            message=f"banned generic phrase: {phrase!r}",
                            path=f"{path}.brief",
                        )
                    )
            for term in excluded_terms:
                if term and term in brief_l:
                    issues.append(
                        ValidationIssue(
                            code="EXCLUDED_TERM",
                            message=f"excluded term appears in brief: {term!r}",
                            path=f"{path}.brief",
                        )
                    )

            for ref in block.evidence_refs:
                if ref.startswith("scope.must_establish.") or ref.startswith("must-"):
                    mid = ref.split(".")[-1]
                    if mid in must_ids:
                        referenced_must.add(mid)
                if ref.startswith("lesson.must_establish") or ref == "lesson.objective":
                    continue
                if ref.startswith("anchor."):
                    aid = ref.split(".", 1)[-1]
                    if aid != packet.anchor.id and ref != f"anchor.{packet.anchor.id}":
                        if aid not in {packet.anchor.id, packet.anchor.description}:
                            issues.append(
                                ValidationIssue(
                                    code="EVIDENCE_REF",
                                    message=f"unresolvable evidence_ref {ref!r}",
                                    path=f"{path}.evidence_refs",
                                )
                            )
                elif ref.startswith("item.") or ref.startswith("approved_item"):
                    iid = ref.split(".")[-1]
                    if iid not in approved_ids:
                        issues.append(
                            ValidationIssue(
                                code="EVIDENCE_REF",
                                message=f"unknown item evidence_ref {ref!r}",
                                path=f"{path}.evidence_refs",
                            )
                        )

            for qid in block.source_question_ids:
                if qid not in approved_ids:
                    issues.append(
                        ValidationIssue(
                            code="UNKNOWN_ITEM",
                            message=f"unknown source_question_id {qid!r}",
                            path=path,
                        )
                    )
            # Question content must never appear as invented stems in planner output.
            if "correct_key" in block.brief.lower() or re.search(
                r"\bA\)|\bB\)|\bC\)|\bD\)", block.brief
            ):
                issues.append(
                    ValidationIssue(
                        code="QUESTION_CONTENT",
                        message="planner must not write question content",
                        path=f"{path}.brief",
                    )
                )

    if total_blocks > packet.limits.max_total_blocks:
        issues.append(
            ValidationIssue(
                code="LESSON_BLOCK_LIMIT",
                message=f"total blocks {total_blocks} exceed max {packet.limits.max_total_blocks}",
                path="sections",
            )
        )

    for focus_id in plan.misconception_focus_ids:
        if focus_id not in misconception_ids:
            issues.append(
                ValidationIssue(
                    code="UNKNOWN_MISCONCEPTION",
                    message=f"misconception_focus_id {focus_id!r} not in approved list",
                    path="misconception_focus_ids",
                )
            )

    if must_ids and not (must_ids & referenced_must) and must_ids:
        # Soften: also accept refs like lesson.objective covering must-establish via evidence_refs listing must ids
        for section in plan.sections:
            for block in section.blocks:
                for ref in block.evidence_refs:
                    for mid in must_ids:
                        if mid in ref:
                            referenced_must.add(mid)
        missing = must_ids - referenced_must
        if missing:
            issues.append(
                ValidationIssue(
                    code="MUST_ESTABLISH_UNCOVERED",
                    message=f"must_establish entries not referenced: {sorted(missing)}",
                    path="scope.must_establish",
                    # Patch 01 architecture proof: incomplete evidence coverage is a
                    # quality concern, not a contract/slot-shape gate failure.
                    blocking=False,
                )
            )

    leaked_plan = _contains_object_id(plan.model_dump_json())
    if leaked_plan:
        issues.append(
            ValidationIssue(
                code="OBJECT_LEAK",
                message=f"page-object id {leaked_plan!r} appears in teaching plan JSON",
                path="$",
            )
        )

    blocking = [issue for issue in issues if issue.blocking]
    return ValidationReport(ok=not blocking, issues=issues)


def advisory_teaching_qc(plan: TeachingPlan) -> list[AdvisoryFinding]:
    findings: list[AdvisoryFinding] = []
    briefs = [block.brief for section in plan.sections for block in section.blocks]
    if len(briefs) >= 4:
        first = sum(_word_count(b) for b in briefs[: max(1, len(briefs) // 4)]) / max(
            1, len(briefs) // 4
        )
        last = sum(_word_count(b) for b in briefs[-max(1, len(briefs) // 4) :]) / max(
            1, len(briefs) // 4
        )
        if first > 0 and last < first * 0.6:
            findings.append(
                AdvisoryFinding(
                    code="LATE_BRIEF_THINNING",
                    message=f"final-quarter briefs average {last:.1f} words vs first-quarter {first:.1f}",
                )
            )
    intents = [block.intent for section in plan.sections for block in section.blocks]
    for index in range(len(intents) - 2):
        if intents[index] == intents[index + 1] == intents[index + 2]:
            findings.append(
                AdvisoryFinding(
                    code="REPEATED_TEACHING_JOB",
                    message=f"intent {intents[index]!r} appears in three consecutive blocks",
                    path=f"blocks[{index}:{index+2}]",
                )
            )
            break
    for section in plan.sections:
        for block in section.blocks:
            if _word_count(block.evidence) < 8:
                findings.append(
                    AdvisoryFinding(
                        code="GENERIC_EVIDENCE",
                        message="evidence sentence is short",
                        path=f"{section.slot_id}.{block.id}",
                    )
                )
    return findings


def validate_form_plan(
    form_plan: FormPlan,
    teaching_plan: TeachingPlan,
    *,
    candidate_map: dict[str, tuple[str, ...] | set[str]],
    compatible_objects: dict[str, set[str]] | None = None,
) -> ValidationReport:
    """Validate form-owned decisions against teaching identity + legal candidates.

    `candidate_map` is the single shared legality source (block_id → objects).
    `compatible_objects` is accepted only as a legacy alias and ignored when
    `candidate_map` is provided.
    """
    del compatible_objects  # ownership: candidate_map is the sole legality source
    issues: list[ValidationIssue] = []
    teaching_blocks = {
        block.id: (section.slot_id, block)
        for section in teaching_plan.sections
        for block in section.blocks
    }
    form_ids: list[str] = []
    for section in form_plan.sections:
        for index, decision in enumerate(section.forms):
            form_ids.append(decision.block_id)
            path = f"sections.{section.slot_id}.forms[{index}]"
            if decision.block_id not in teaching_blocks:
                issues.append(
                    ValidationIssue(
                        code="UNKNOWN_BLOCK",
                        message=(
                            f"form plan references unknown block {decision.block_id!r}"
                        ),
                        path=path,
                    )
                )
                continue
            slot_id, teaching = teaching_blocks[decision.block_id]
            if section.slot_id != slot_id:
                issues.append(
                    ValidationIssue(
                        code="SECTION_MISMATCH",
                        message="form section does not match teaching section",
                        path=path,
                    )
                )
            if decision.object == "heading":
                issues.append(
                    ValidationIssue(
                        code="HEADING_OBJECT",
                        message="heading object is forbidden",
                        path=path,
                    )
                )
            if decision.object == "answer-key":
                issues.append(
                    ValidationIssue(
                        code="ANSWER_KEY_OBJECT",
                        message="answer-key is document-level and not selectable",
                        path=path,
                    )
                )
            if decision.block_id not in candidate_map:
                issues.append(
                    ValidationIssue(
                        code="MISSING_CANDIDATE_SET",
                        message=(
                            f"no candidate map entry for block {decision.block_id!r}"
                        ),
                        path=path,
                    )
                )
            else:
                allowed = set(candidate_map[decision.block_id])
                if not allowed:
                    issues.append(
                        ValidationIssue(
                            code="NO_LEGAL_OBJECT",
                            message=(
                                f"block {decision.block_id!r} has an empty legal "
                                "object candidate set"
                            ),
                            path=path,
                        )
                    )
                elif decision.object not in allowed:
                    issues.append(
                        ValidationIssue(
                            code="INCOMPATIBLE_OBJECT",
                            message=(
                                f"object {decision.object!r} not in legal candidates "
                                f"for block {decision.block_id!r}"
                            ),
                            path=path,
                        )
                    )
            if decision.object == "questions" and not teaching.source_question_ids:
                issues.append(
                    ValidationIssue(
                        code="QUESTION_IDS",
                        message=(
                            "questions object requires teaching source_question_ids"
                        ),
                        path=path,
                    )
                )
            if decision.placement not in {"main", "margin"}:
                issues.append(
                    ValidationIssue(
                        code="PLACEMENT",
                        message=f"illegal placement {decision.placement!r}",
                        path=path,
                    )
                )

    if set(form_ids) != set(teaching_blocks):
        issues.append(
            ValidationIssue(
                code="BLOCK_SET",
                message="form plan must map exactly the teaching blocks",
                path="sections",
            )
        )
    if len(form_ids) != len(set(form_ids)):
        issues.append(
            ValidationIssue(
                code="DUPLICATE_FORM_BLOCK",
                message="form plan has duplicate block ids",
                path="sections",
            )
        )

    blocking = [issue for issue in issues if issue.blocking]
    return ValidationReport(ok=not blocking, issues=issues)


def advisory_form_qc(form_plan: FormPlan) -> list[AdvisoryFinding]:
    findings: list[AdvisoryFinding] = []
    objects = [
        decision.object
        for section in form_plan.sections
        for decision in section.forms
    ]
    for index in range(len(objects) - 2):
        if (
            objects[index] == objects[index + 1] == objects[index + 2]
            and objects[index] != "questions"
        ):
            findings.append(
                AdvisoryFinding(
                    code="FORM_STREAK",
                    message=f"object {objects[index]!r} selected three consecutive times",
                )
            )
            break
    if objects:
        from collections import Counter

        counts = Counter(obj for obj in objects if obj != "questions")
        if counts:
            top_obj, top_count = counts.most_common(1)[0]
            if top_count / max(1, len(objects)) > 0.6:
                findings.append(
                    AdvisoryFinding(
                        code="FORM_DOMINANCE",
                        message=(
                            f"object {top_obj!r} dominates form plan "
                            f"({top_count}/{len(objects)})"
                        ),
                    )
                )
    figure_idxs = [i for i, obj in enumerate(objects) if obj == "figure"]
    if len(figure_idxs) > 2:
        findings.append(
            AdvisoryFinding(code="FIGURE_OVERUSE", message="more than two figure blocks")
        )
    for a, b in zip(figure_idxs, figure_idxs[1:]):
        if b == a + 1:
            findings.append(
                AdvisoryFinding(code="FIGURE_OVERUSE", message="consecutive figure blocks")
            )
            break
    return findings
