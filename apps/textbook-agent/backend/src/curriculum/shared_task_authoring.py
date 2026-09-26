"""Author the closed shared-task contract for an approved Teaching Plan.

This adapter is the semantic boundary between an approved plan and the task
snapshot consumed by Learn and Print.  The provider supplies task meaning only;
code owns task identity, plan lineage, sourcebook references, and approved item
ownership.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.lesson_sourcebook.models import LessonSourcebook
from curriculum.shared_tasks.models import SharedTaskDraft, SharedTaskSpec
from curriculum.shared_tasks.validation import (
    finalize_shared_tasks,
    validate_final_task_response_contract,
)
from curriculum.teaching_plan.compatibility import response_bearing_action
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringProvider,
    AuthoringRegistry,
    AuthoringRequest,
    LLMAuthoringProvider,
)
from infra.authoring.model_policy import SHARED_TASK_AUTHORING
from infra.authoring.models import AuthoringValidationError
from infra.execution.call_budget import CallBudget, CallBudgetLedger


class SharedTaskAuthoringError(ValueError):
    """An approved shared-task input or result cannot satisfy the contract."""


class ApprovedItemSnapshot(BaseModel):
    """Revision-bound approved item records supplied to task authoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    teaching_plan_id: str = Field(min_length=1)
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str = Field(min_length=1)
    items: dict[str, Any] = Field(default_factory=dict)


class SharedTaskDraftEnvelope(BaseModel):
    """The only provider-owned shape accepted by shared-task authoring."""

    model_config = ConfigDict(extra="forbid")

    tasks: list[SharedTaskDraft] = Field(default_factory=list)


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "to_dict"):
        return _jsonable(value.to_dict())
    return value


def _stable_hash(value: Any) -> str:
    raw = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def approved_item_snapshot_hash(snapshot: ApprovedItemSnapshot) -> str:
    """Return the canonical identity of an approved item snapshot."""

    return _stable_hash(snapshot.model_dump(mode="json"))


def _snapshot_from_input(
    plan: TeachingPlan,
    *,
    approved_items: Mapping[str, Any] | ApprovedItemSnapshot | None,
    approved_item_snapshot: Mapping[str, Any] | ApprovedItemSnapshot | None,
) -> ApprovedItemSnapshot:
    if approved_items is not None and approved_item_snapshot is not None:
        raise SharedTaskAuthoringError("supply approved_items or approved_item_snapshot, not both")
    raw: Any = approved_item_snapshot if approved_item_snapshot is not None else approved_items
    plan_id = str(plan.teaching_plan_id)
    revision = int(plan.revision or 0)
    plan_hash = teaching_plan_content_hash(plan)
    if raw is None:
        return ApprovedItemSnapshot(
            teaching_plan_id=plan_id,
            teaching_plan_revision=revision,
            teaching_plan_hash=plan_hash,
            items={},
        )
    if isinstance(raw, ApprovedItemSnapshot):
        snapshot = raw
    elif isinstance(raw, Mapping) and (
        "items" in raw or "approved_items" in raw or "teaching_plan_revision" in raw
    ):
        payload = dict(raw)
        items = payload.pop("items", payload.pop("approved_items", {}))
        if isinstance(items, list):
            items = {
                str(item.get("id")): item
                for item in items
                if isinstance(item, Mapping) and item.get("id")
            }
        if not isinstance(items, Mapping):
            raise SharedTaskAuthoringError("approved item snapshot items must be a mapping")
        payload.setdefault("teaching_plan_id", plan_id)
        payload.setdefault("teaching_plan_revision", payload.pop("revision", revision))
        payload.setdefault("teaching_plan_hash", plan_hash)
        payload["items"] = {str(key): _jsonable(value) for key, value in items.items()}
        try:
            snapshot = ApprovedItemSnapshot.model_validate(payload)
        except ValidationError as exc:
            raise SharedTaskAuthoringError("approved item snapshot is malformed") from exc
    elif isinstance(raw, Mapping):
        # An arbitrary legacy map has no durable revision verifier.  Rebinding
        # it to this plan would create a provenance claim the caller did not
        # supply; the future executor must provide the persisted snapshot.
        raise SharedTaskAuthoringError(
            "approved item snapshot must include revision-bound metadata and items"
        )
    else:
        raise SharedTaskAuthoringError("approved item snapshot is malformed")
    if (
        snapshot.teaching_plan_id != plan_id
        or snapshot.teaching_plan_revision != revision
        or snapshot.teaching_plan_hash != plan_hash
    ):
        raise SharedTaskAuthoringError(
            "approved item snapshot does not match the Teaching Plan revision"
        )
    return snapshot


def _plan_source_refs(plan: TeachingPlan) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for section in plan.sections:
        for block in section.blocks:
            for ref in block.sourcebook_refs:
                if not isinstance(ref, str) or not ref or ref != ref.strip():
                    raise SharedTaskAuthoringError(
                        f"block {block.id!r} contains a non-canonical sourcebook ref"
                    )
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
    return tuple(refs)


def _response_blocks(plan: TeachingPlan) -> list[TeachingPlanBlock]:
    return [
        block
        for section in plan.sections
        for block in section.blocks
        if block.learner_action is not None and response_bearing_action(block.learner_action.action)
    ]


def _validate_inputs(
    plan: TeachingPlan,
    sourcebook: LessonSourcebook,
    snapshot: ApprovedItemSnapshot,
    *,
    expected_teaching_plan_hash: str | None,
    expected_sourcebook_hash: str | None,
) -> str:
    if plan.approval_status != "approved":
        raise SharedTaskAuthoringError("shared task authoring requires an approved Teaching Plan")
    if not plan.teaching_plan_id:
        raise SharedTaskAuthoringError("approved Teaching Plan is missing teaching_plan_id")
    if plan.revision is None or plan.revision < 1:
        raise SharedTaskAuthoringError("approved Teaching Plan is missing a positive revision")
    plan_hash = teaching_plan_content_hash(plan)
    if expected_teaching_plan_hash is not None and expected_teaching_plan_hash != plan_hash:
        raise SharedTaskAuthoringError("Teaching Plan hash is stale")
    if (
        sourcebook.teaching_plan_id != plan.teaching_plan_id
        or sourcebook.teaching_plan_revision != plan.revision
        or sourcebook.teaching_plan_hash != plan_hash
    ):
        raise SharedTaskAuthoringError(
            "LessonSourcebook does not match the approved Teaching Plan revision"
        )
    source_refs = _plan_source_refs(plan)
    sourcebook_ids = [entry.id for entry in sourcebook.entries]
    if len(sourcebook_ids) != len(set(sourcebook_ids)):
        raise SharedTaskAuthoringError("LessonSourcebook entry ids must be unique")
    if sourcebook_ids != list(source_refs):
        raise SharedTaskAuthoringError(
            "LessonSourcebook entries must exactly match approved sourcebook_refs"
        )
    sourcebook_hash = _stable_hash(sourcebook.model_dump(mode="json"))
    if expected_sourcebook_hash is not None and expected_sourcebook_hash != sourcebook_hash:
        raise SharedTaskAuthoringError("LessonSourcebook hash is stale")
    if (
        snapshot.teaching_plan_id != plan.teaching_plan_id
        or snapshot.teaching_plan_revision != plan.revision
        or snapshot.teaching_plan_hash != plan_hash
    ):
        raise SharedTaskAuthoringError(
            "approved item snapshot does not match the Teaching Plan revision"
        )
    missing_items = sorted(
        {
            source_id
            for block in _response_blocks(plan)
            for source_id in block.source_question_ids
            if source_id not in snapshot.items
        }
    )
    if missing_items:
        raise SharedTaskAuthoringError(
            f"approved item snapshot is missing source ids {missing_items!r}"
        )
    return sourcebook_hash


def _validate_plan_basics(plan: TeachingPlan) -> None:
    if not isinstance(plan, TeachingPlan):
        raise SharedTaskAuthoringError("shared task authoring requires a TeachingPlan")
    if plan.approval_status != "approved":
        raise SharedTaskAuthoringError("shared task authoring requires an approved Teaching Plan")
    if not plan.teaching_plan_id:
        raise SharedTaskAuthoringError("approved Teaching Plan is missing teaching_plan_id")
    if plan.revision is None or plan.revision < 1:
        raise SharedTaskAuthoringError("approved Teaching Plan is missing a positive revision")


def _draft_contract_validator(
    _definition: AuthoringDefinition,
    request: AuthoringRequest,
    payload: Mapping[str, Any],
) -> list[AuthoringValidationError]:
    try:
        envelope = SharedTaskDraftEnvelope.model_validate(payload)
    except ValidationError as exc:
        return [AuthoringValidationError("", str(exc))]
    descriptors = request.inputs.get("response_blocks", ())
    errors: list[str] = []
    if len(envelope.tasks) != len(descriptors):
        errors.append(
            f"provider must return exactly {len(descriptors)} task drafts; "
            f"received {len(envelope.tasks)}"
        )
        return [AuthoringValidationError("tasks", error) for error in errors]
    for index, (draft, descriptor) in enumerate(zip(envelope.tasks, descriptors, strict=True)):
        expected = descriptor["learner_action"]
        if draft.expected_evidence != expected["expected_evidence"]:
            errors.append(f"task {index} expected_evidence must match the approved learner action")
        if draft.difficulty != expected["difficulty"]:
            errors.append(f"task {index} difficulty must match the approved learner action")
        try:
            task = SharedTaskSpec(
                id=f"task-{descriptor['block_id']}",
                teaching_plan_id=str(request.scoped_request["teaching_plan_id"]),
                teaching_plan_revision=int(request.teaching_revision),
                teaching_plan_hash=str(request.scoped_request["teaching_plan_hash"]),
                teaching_block_id=str(descriptor["block_id"]),
                mode=("assessment" if descriptor["assessment"] else "formative"),
                action=expected["action"],
                purpose=expected["purpose"],
                prompt=draft.prompt,
                difficulty=draft.difficulty,
                sourcebook_refs=list(descriptor["sourcebook_refs"]),
                expected_evidence=draft.expected_evidence,
                response=dict(draft.response),
                evaluation=dict(draft.evaluation),
                feedback=draft.feedback,
                approved_source_ids=list(descriptor["source_question_ids"]),
            )
        except ValidationError as exc:
            errors.append(f"task {index} failed canonical model validation: {exc}")
            continue
        errors.extend(validate_final_task_response_contract(task))
    return [AuthoringValidationError("tasks", error) for error in errors]


def _definition() -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id=SHARED_TASK_AUTHORING,
        native_path="shared_document",
        modes=("generate",),
        instructions=(
            "Author one task draft for every response-bearing block, in supplied order. "
            "Use the approved learner action, sourcebook entries and approved item snapshot. "
            "Copy expected_evidence and difficulty byte-for-byte from that block's "
            "learner_action; never paraphrase or infer either field. "
            "Return only the closed tasks envelope; code owns task IDs, plan lineage, "
            "sourcebook refs and approved item IDs. For select-one, use response "
            "{type: single_choice, options: [{id, text}]} and evaluation either "
            "{type: exact_match, correct_option_id} or {type: choice_keys, correct_keys}. "
            "For select-many, use response {type: multiple_choice, options: [{id, text}]} "
            "and evaluation {type: choice_keys, correct_keys}. For "
            "complete-missing-values, use response {type: missing_values, values} "
            "and evaluation {type: accepted_answers, accepted_answers}, "
            "{type: exact_match, answer}, or {type: rubric, criteria}. For "
            "classify-items, use response {type: classification, items, categories, "
            "correct_placements} and evaluation {type: mapping, correct_placements} "
            "or {type: rubric, criteria}. Every classification item and category must "
            "be a non-empty string. correct_placements must map every item string "
            "exactly once to one declared category string; include no missing or extra "
            "item keys and no undeclared categories. The mapping evaluation's "
            "correct_placements must exactly match the response placements. For "
            "match-pairs, use response "
            "{type: matching, pairs: [{left, right}]} and evaluation "
            "{type: mapping, pairs}, {type: exact_match, answer}, or "
            "{type: rubric, criteria}. For order-items and reconstruct-order, use "
            "response {type: ordered_items, items, correct_order} and evaluation "
            "{type: ordered_match, correct_order}, {type: exact_match, answer}, or "
            "{type: rubric, criteria}. For enter-number, use response {type: number} "
            "and evaluation {type: numeric, value, tolerance?, unit?}, "
            "{type: exact_match, answer}, or {type: rubric, criteria}. For enter-text, "
            "use response {type: text} and evaluation {type: accepted_answers, "
            "accepted_answers}, {type: teacher_review, review_guidance}, "
            "{type: exact_match, answer}, or {type: rubric, criteria}. Include only "
            "fields allowed for the selected response and evaluation types."
        ),
        payload_schema=SharedTaskDraftEnvelope.model_json_schema(),
        required_inputs=(
            "teaching_plan",
            "sourcebook",
            "approved_item_snapshot",
            "response_blocks",
        ),
        validator_refs=("shared_task.schema", "shared_task.contract"),
    )


def _registry() -> AuthoringRegistry:
    return (
        AuthoringRegistry()
        .with_validator("shared_task.schema", lambda *_args, **_kwargs: [])
        .with_validator("shared_task.contract", _draft_contract_validator)
    )


async def author_shared_tasks(
    plan: TeachingPlan,
    sourcebook: LessonSourcebook,
    *,
    approved_items: Mapping[str, Any] | ApprovedItemSnapshot | None = None,
    approved_item_snapshot: Mapping[str, Any] | ApprovedItemSnapshot | None = None,
    expected_teaching_plan_hash: str | None = None,
    expected_sourcebook_hash: str | None = None,
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    work_order_id: str | None = None,
    trace_id: str | None = None,
    call_budget: CallBudget | None = None,
    budget_ledger: CallBudgetLedger | None = None,
) -> list[SharedTaskSpec]:
    """Generate and finalize tasks against exact durable semantic inputs."""

    _validate_plan_basics(plan)
    if not isinstance(sourcebook, LessonSourcebook):
        raise SharedTaskAuthoringError("shared task authoring requires a LessonSourcebook")
    snapshot = _snapshot_from_input(
        plan,
        approved_items=approved_items,
        approved_item_snapshot=approved_item_snapshot,
    )
    sourcebook_hash = _validate_inputs(
        plan,
        sourcebook,
        snapshot,
        expected_teaching_plan_hash=expected_teaching_plan_hash,
        expected_sourcebook_hash=expected_sourcebook_hash,
    )
    blocks = _response_blocks(plan)
    plan_id = str(plan.teaching_plan_id)
    revision = int(plan.revision or 0)
    plan_hash = teaching_plan_content_hash(plan)
    if not blocks:
        return finalize_shared_tasks(plan, [], sourcebook=sourcebook)

    descriptors = [
        {
            "block_id": block.id,
            "sourcebook_refs": list(block.sourcebook_refs),
            "source_question_ids": list(block.source_question_ids),
            "assessment": block.task_mode == "assessment" or bool(block.source_question_ids),
            "learner_action": {
                "action": block.learner_action.action,  # type: ignore[union-attr]
                "purpose": block.learner_action.purpose,  # type: ignore[union-attr]
                "target": block.learner_action.target,  # type: ignore[union-attr]
                "expected_evidence": block.learner_action.expected_evidence,  # type: ignore[union-attr]
                "difficulty": block.learner_action.difficulty,  # type: ignore[union-attr]
            },
            "task_mode": block.task_mode,
            "intent": block.intent,
            "brief": block.brief,
        }
        for block in blocks
    ]
    snapshot_hash = approved_item_snapshot_hash(snapshot)
    request = AuthoringRequest(
        work_order_id=work_order_id or f"shared-tasks:{plan_id}:{revision}:{plan_hash[:16]}",
        definition=_definition(),
        scoped_request={
            "stage": "shared_task_authoring",
            "teaching_plan_id": plan_id,
            "teaching_plan_revision": revision,
            "teaching_plan_hash": plan_hash,
            "sourcebook_hash": sourcebook_hash,
            "approved_item_snapshot_hash": snapshot_hash,
        },
        inputs={
            "teaching_plan": plan.model_dump(mode="json"),
            "sourcebook": sourcebook.model_dump(mode="json"),
            "approved_item_snapshot": snapshot.model_dump(mode="json"),
            "response_blocks": descriptors,
        },
        teaching_revision=revision,
        source_identities=(plan_id, plan_hash, sourcebook_hash, snapshot_hash),
        mode="generate",
        trace_id=trace_id,
    )
    selected_engine = engine
    if selected_engine is None:
        selected_engine = AuthoringEngine(
            registry=_registry(),
            provider=provider
            or LLMAuthoringProvider(
                node_name=SHARED_TASK_AUTHORING,
                output_type=SharedTaskDraftEnvelope,
            ),
            max_repair_attempts=1,
            max_provider_calls=2,
            budget_ledger=budget_ledger,
        )
    result = await selected_engine.execute(request, provider=provider, call_budget=call_budget)
    try:
        draft = SharedTaskDraftEnvelope.model_validate(result.payload)
    except ValidationError as exc:
        raise SharedTaskAuthoringError(
            "authoring engine returned an invalid task envelope"
        ) from exc
    tasks = [
        SharedTaskSpec(
            id=f"task-{block.id}",
            teaching_plan_id=plan_id,
            teaching_plan_revision=revision,
            teaching_plan_hash=plan_hash,
            teaching_block_id=block.id,
            mode=("assessment" if descriptor["assessment"] else "formative"),
            action=block.learner_action.action,  # type: ignore[union-attr]
            purpose=block.learner_action.purpose,  # type: ignore[union-attr]
            prompt=draft_task.prompt,
            difficulty=draft_task.difficulty,
            sourcebook_refs=list(block.sourcebook_refs),
            expected_evidence=draft_task.expected_evidence,
            response=dict(draft_task.response),
            evaluation=dict(draft_task.evaluation),
            feedback=draft_task.feedback,
            approved_source_ids=list(block.source_question_ids),
        )
        for block, descriptor, draft_task in zip(blocks, descriptors, draft.tasks, strict=True)
    ]
    expected_ids = [f"task-{block.id}" for block in blocks]
    if [task.id for task in tasks] != expected_ids:
        raise SharedTaskAuthoringError("shared task authoring produced non-canonical task IDs")
    try:
        return finalize_shared_tasks(plan, tasks, sourcebook=sourcebook)
    except ValueError as exc:
        raise SharedTaskAuthoringError(str(exc)) from exc


__all__ = [
    "ApprovedItemSnapshot",
    "SharedTaskAuthoringError",
    "SharedTaskDraftEnvelope",
    "approved_item_snapshot_hash",
    "author_shared_tasks",
]
