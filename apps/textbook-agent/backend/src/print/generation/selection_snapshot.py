"""Selection snapshot persistence and closed-set validation (Print)."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from curriculum.teaching_plan.models import TeachingPlan
from print.generation.whole_lesson.form_plan import FormDecision, FormPlan
from print.resources.selection import PASSIVE_ACTIONS, load_form_selection_view

SelectionErrorCode = Literal[
    "OUT_OF_SET",
    "MISSING_BLOCK",
    "DUPLICATE_BLOCK",
    "ALTERED_TEACHING_IDENTITY",
    "BLOCK_SET",
    "NO_COMPATIBLE_CAPABILITY",
    "UNSUPPORTED_ASSET",
]


class SelectionError(ValueError):
    def __init__(self, code: SelectionErrorCode, message: str, *, path: str = "") -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {message}")


class PrintSelectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_id: str
    form_id: str
    placement: Literal["main", "margin", "spanning"] = "main"
    reason: str = ""


class PrintSelectionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Literal["print"] = "print"
    teaching_plan_id: str
    teaching_plan_revision: int
    teaching_plan_hash: str
    native_policy_hash: str
    package_contract_hash: str
    candidate_map: dict[str, list[str]] = Field(default_factory=dict)
    decisions: list[PrintSelectionDecision] = Field(default_factory=list)
    snapshot_hash: str = ""

    def recompute_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"snapshot_hash"})
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def seal(self) -> PrintSelectionSnapshot:
        return self.model_copy(update={"snapshot_hash": self.recompute_hash()})


def snapshot_from_form_plan(
    *,
    teaching_plan: TeachingPlan,
    form_plan: FormPlan,
    candidate_map: Mapping[str, Sequence[str]],
    teaching_plan_hash: str,
    native_policy_hash: str,
    package_contract_hash: str,
) -> PrintSelectionSnapshot:
    decisions = [
        PrintSelectionDecision(
            block_id=decision.block_id,
            form_id=decision.object,
            placement=decision.placement,  # type: ignore[arg-type]
            reason=decision.reason,
        )
        for section in form_plan.sections
        for decision in section.forms
    ]
    snap = PrintSelectionSnapshot(
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=teaching_plan_hash,
        native_policy_hash=native_policy_hash,
        package_contract_hash=package_contract_hash,
        candidate_map={
            str(key): [str(item) for item in values]
            for key, values in candidate_map.items()
        },
        decisions=decisions,
    )
    return snap.seal()


def validate_print_selection(
    *,
    teaching_plan: TeachingPlan,
    decisions: Sequence[PrintSelectionDecision] | FormPlan,
    candidate_map: Mapping[str, Sequence[str]],
    expected_teaching_plan_id: str | None = None,
    expected_teaching_plan_revision: int | None = None,
    expected_teaching_plan_hash: str | None = None,
    actual_teaching_plan_hash: str | None = None,
) -> None:
    """Validate decisions against the EXACT candidate snapshot supplied to the provider."""
    if expected_teaching_plan_id is not None:
        if str(teaching_plan.teaching_plan_id or "") != expected_teaching_plan_id:
            raise SelectionError(
                "ALTERED_TEACHING_IDENTITY",
                "teaching_plan_id does not match selection snapshot",
                path="teaching_plan_id",
            )
    if expected_teaching_plan_revision is not None:
        if int(teaching_plan.revision or 0) != int(expected_teaching_plan_revision):
            raise SelectionError(
                "ALTERED_TEACHING_IDENTITY",
                "teaching_plan_revision does not match selection snapshot",
                path="teaching_plan_revision",
            )
    if (
        expected_teaching_plan_hash is not None
        and actual_teaching_plan_hash is not None
        and expected_teaching_plan_hash != actual_teaching_plan_hash
    ):
        raise SelectionError(
            "ALTERED_TEACHING_IDENTITY",
            "teaching_plan_hash does not match selection snapshot",
            path="teaching_plan_hash",
        )

    if isinstance(decisions, FormPlan):
        parsed = [
            PrintSelectionDecision(
                block_id=item.block_id,
                form_id=item.object,
                placement=item.placement,  # type: ignore[arg-type]
                reason=item.reason,
            )
            for section in decisions.sections
            for item in section.forms
        ]
    else:
        parsed = list(decisions)

    teaching_ids = [
        block.id for section in teaching_plan.sections for block in section.blocks
    ]
    decision_ids = [item.block_id for item in parsed]

    if len(decision_ids) != len(set(decision_ids)):
        raise SelectionError(
            "DUPLICATE_BLOCK",
            "selection has duplicate block ids",
            path="decisions",
        )

    missing = [block_id for block_id in teaching_ids if block_id not in set(decision_ids)]
    if missing:
        raise SelectionError(
            "MISSING_BLOCK",
            f"selection missing teaching blocks: {missing}",
            path="decisions",
        )

    extra = [block_id for block_id in decision_ids if block_id not in set(teaching_ids)]
    if extra:
        raise SelectionError(
            "BLOCK_SET",
            f"selection references unknown blocks: {extra}",
            path="decisions",
        )

    for item in parsed:
        allowed = {str(x) for x in candidate_map.get(item.block_id, ())}
        if item.form_id not in allowed:
            raise SelectionError(
                "OUT_OF_SET",
                f"form {item.form_id!r} not in candidate set for {item.block_id!r}",
                path=f"decisions.{item.block_id}",
            )


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _guidance_tokens(text: str) -> frozenset[str]:
    return frozenset(tok for tok in _TOKEN_RE.findall(text.lower()) if len(tok) > 2)


def rank_print_form_candidates(
    form_ids: Sequence[str],
    *,
    brief: str,
    intent: str,
    action: str | None,
    selection_view: Mapping[str, Any] | None = None,
) -> list[str]:
    """Rank a closed Print form shortlist by package choose_when / reject_when."""
    if not form_ids:
        return []
    view = selection_view if selection_view is not None else load_form_selection_view()
    by_id: dict[str, Mapping[str, Any]] = {}
    for row in view.get("forms") or []:
        if isinstance(row, Mapping) and row.get("id"):
            by_id[str(row["id"])] = row
    query = _guidance_tokens(f"{brief} {intent} {action or ''}")
    scored: list[tuple[int, int, int, str]] = []
    for index, form_id in enumerate(form_ids):
        record = by_id.get(form_id) or {}
        choose = _guidance_tokens(str(record.get("choose_when") or ""))
        reject = _guidance_tokens(str(record.get("reject_when") or ""))
        choose_hits = len(query & choose)
        reject_hits = len(query & reject)
        scored.append((-choose_hits, reject_hits, index, form_id))
    scored.sort()
    return [form_id for _, _, _, form_id in scored]


def select_print_first_legal(
    teaching_plan: TeachingPlan,
    *,
    candidate_map: Mapping[str, Sequence[str]],
) -> list[PrintSelectionDecision]:
    """Test helper: first legal form per block from the closed shortlist."""
    from print.resources.selection import NoCompatiblePrintCapabilityError

    decisions: list[PrintSelectionDecision] = []
    for section in teaching_plan.sections:
        for block in section.blocks:
            allowed = list(candidate_map.get(block.id) or ())
            if not allowed:
                action = None
                if block.learner_action is not None:
                    action = block.learner_action.action
                raise NoCompatiblePrintCapabilityError(
                    block_id=block.id,
                    intent=block.intent,
                    action=action,
                    constraints={"candidates": []},
                    reason="empty legal form set",
                )
            decisions.append(
                PrintSelectionDecision(
                    block_id=block.id,
                    form_id=str(allowed[0]),
                    placement="main",
                    reason="deterministic first-legal closed candidate",
                )
            )
    return decisions


def select_print_deterministically(
    teaching_plan: TeachingPlan,
    *,
    candidate_map: Mapping[str, Sequence[str]],
) -> list[PrintSelectionDecision]:
    """Production closed selection: choose_when-ranked form per block."""
    from print.resources.selection import NoCompatiblePrintCapabilityError

    decisions: list[PrintSelectionDecision] = []
    for section in teaching_plan.sections:
        for block in section.blocks:
            allowed = list(candidate_map.get(block.id) or ())
            if not allowed:
                action = None
                if block.learner_action is not None:
                    action = block.learner_action.action
                raise NoCompatiblePrintCapabilityError(
                    block_id=block.id,
                    intent=block.intent,
                    action=action,
                    constraints={"candidates": []},
                    reason="empty legal form set",
                )
            action = None
            if block.learner_action is not None:
                action = block.learner_action.action
            ranked = rank_print_form_candidates(
                allowed,
                brief=str(getattr(block, "brief", "") or ""),
                intent=block.intent,
                action=action,
            )
            decisions.append(
                PrintSelectionDecision(
                    block_id=block.id,
                    form_id=str(ranked[0]),
                    placement="main",
                    reason="choose_when-ranked closed candidate",
                )
            )
    return decisions


def build_print_selection_snapshot(
    teaching_plan: TeachingPlan,
    *,
    candidate_map: Mapping[str, Sequence[str]],
    teaching_plan_hash: str,
    native_policy_hash: str,
    package_contract_hash: str,
    decisions: Sequence[PrintSelectionDecision] | None = None,
) -> PrintSelectionSnapshot:
    chosen = (
        list(decisions)
        if decisions is not None
        else select_print_deterministically(teaching_plan, candidate_map=candidate_map)
    )
    validate_print_selection(
        teaching_plan=teaching_plan,
        decisions=chosen,
        candidate_map=candidate_map,
        expected_teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        expected_teaching_plan_revision=int(teaching_plan.revision or 1),
        expected_teaching_plan_hash=teaching_plan_hash,
        actual_teaching_plan_hash=teaching_plan_hash,
    )
    snap = PrintSelectionSnapshot(
        teaching_plan_id=str(teaching_plan.teaching_plan_id or ""),
        teaching_plan_revision=int(teaching_plan.revision or 1),
        teaching_plan_hash=teaching_plan_hash,
        native_policy_hash=native_policy_hash,
        package_contract_hash=package_contract_hash,
        candidate_map={
            str(key): [str(item) for item in values]
            for key, values in candidate_map.items()
        },
        decisions=list(chosen),
    )
    return snap.seal()


def form_plan_from_decisions(
    teaching_plan: TeachingPlan,
    decisions: Sequence[PrintSelectionDecision],
) -> FormPlan:
    by_block = {item.block_id: item for item in decisions}
    sections = []
    for section in teaching_plan.sections:
        forms: list[FormDecision] = []
        for block in section.blocks:
            decision = by_block[block.id]
            forms.append(
                FormDecision(
                    block_id=block.id,
                    object=decision.form_id,
                    placement=decision.placement,
                    reason=decision.reason,
                )
            )
        sections.append({"slot_id": section.slot_id, "forms": forms})
    return FormPlan.model_validate({"sections": sections})


__all__ = [
    "PASSIVE_ACTIONS",
    "PrintSelectionDecision",
    "PrintSelectionSnapshot",
    "SelectionError",
    "SelectionErrorCode",
    "build_print_selection_snapshot",
    "form_plan_from_decisions",
    "rank_print_form_candidates",
    "select_print_deterministically",
    "select_print_first_legal",
    "snapshot_from_form_plan",
    "validate_print_selection",
]
