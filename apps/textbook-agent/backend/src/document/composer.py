"""LLM document composer — Teaching Plan → compact CompositionPlan choices.

Composition describes STRUCTURE choices only (kind/role/reason), never content.
Heuristics in ``document.heuristics`` remain a narrow emergency fallback.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import CompositionDecision, CompositionPlan
from document.heuristics import choose_document_primitive
from document.models import DOCUMENT_PRIMITIVE_KINDS
from document.writer_prompts import (
    document_composer_prompt,
    document_composer_prompt_hash,
)
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringRequest,
)
from infra.authoring.engine import AuthoringRegistry
from infra.execution.call_budget import BudgetExhaustedError, CallBudget, CallBudgetLedger
from infra.execution.checkpoints import (
    CheckpointCompatibility,
    CheckpointStore,
    content_hash,
)

COMPOSER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["nodes"],
    "properties": {
        "nodes": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "teaching_block_id", "kind", "reason"],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "teaching_block_id": {"type": "string", "minLength": 1},
                    "section_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "kind": {
                        "type": "string",
                        "enum": sorted(DOCUMENT_PRIMITIVE_KINDS),
                    },
                    "role": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "reason": {"type": "string", "minLength": 1},
                },
            },
        }
    },
}


class ComposerNodeChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    teaching_block_id: str = Field(min_length=1)
    section_id: str | None = None
    kind: Literal["paragraph", "heading", "list", "figure", "table", "callout"]
    role: str | None = None
    reason: str = Field(min_length=1)


class ComposerOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nodes: list[ComposerNodeChoice] = Field(min_length=1)


class DocumentComposerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _as_plan(plan: TeachingPlan | Mapping[str, Any]) -> TeachingPlan:
    if isinstance(plan, TeachingPlan):
        return plan
    return TeachingPlan.model_validate(plan)


def _block_index(plan: TeachingPlan) -> dict[str, TeachingPlanBlock]:
    return {block.id: block for section in plan.sections for block in section.blocks}


def _section_for_block(plan: TeachingPlan) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for section in plan.sections:
        for block in section.blocks:
            mapping[block.id] = str(section.slot_id or "")
    return mapping


def _closed_kind_map(
    plan: TeachingPlan,
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None,
) -> dict[str, tuple[str, ...]]:
    """Freeze the exact ordinary primitive set exposed for each teaching block."""
    all_kinds = tuple(sorted(DOCUMENT_PRIMITIVE_KINDS))
    supplied = allowed_kinds_by_block is not None
    out: dict[str, tuple[str, ...]] = {}
    for section in plan.sections:
        for block in section.blocks:
            if not supplied:
                out[block.id] = all_kinds
                continue
            raw = allowed_kinds_by_block.get(block.id, ())  # type: ignore[union-attr]
            legal = tuple(
                dict.fromkeys(
                    str(kind)
                    for kind in raw
                    if str(kind) in DOCUMENT_PRIMITIVE_KINDS
                )
            )
            out[block.id] = legal
    return out


def _teaching_plan_summary(
    plan: TeachingPlan,
    *,
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    closed = _closed_kind_map(plan, allowed_kinds_by_block)
    sections: list[dict[str, Any]] = []
    for section in plan.sections:
        blocks: list[dict[str, Any]] = []
        for block in section.blocks:
            action = None
            if block.learner_action is not None:
                action = {
                    "action": block.learner_action.action,
                    "target": block.learner_action.target,
                    "purpose": block.learner_action.purpose,
                }
            blocks.append(
                {
                    "id": block.id,
                    "intent": block.intent,
                    "brief": block.brief,
                    "evidence": block.evidence,
                    "learner_action": action,
                    "allowed_kinds": list(closed[block.id]),
                }
            )
        sections.append(
            {
                "slot_id": section.slot_id,
                "specific_purpose": section.specific_purpose,
                "blocks": blocks,
            }
        )
    return {
        "teaching_plan_id": plan.teaching_plan_id,
        "revision": plan.revision,
        "arc": plan.arc,
        "sections": sections,
    }


def _composer_definition(*, path: Literal["print", "learn"]) -> AuthoringDefinition:
    return AuthoringDefinition(
        capability_id="document-composer",
        native_path=path,
        modes=("generate",),
        instructions=document_composer_prompt(),
        payload_schema=COMPOSER_SCHEMA,
        required_inputs=("teaching_plan", "allowed_kinds_by_block"),
        validator_refs=("document.composer_schema",),
        definition_hash=document_composer_prompt_hash(),
    )


def _noop_validator(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


def _validate_composer_payload(
    plan: TeachingPlan,
    payload: Mapping[str, Any],
    *,
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    try:
        parsed = ComposerOutput.model_validate(payload)
    except ValidationError as exc:
        return [str(exc)]

    known = _block_index(plan)
    closed = _closed_kind_map(plan, allowed_kinds_by_block)
    seen_ids: set[str] = set()
    covered_blocks: set[str] = set()
    for node in parsed.nodes:
        if node.id in seen_ids:
            errors.append(f"duplicate composer node id {node.id!r}")
        seen_ids.add(node.id)
        block = known.get(node.teaching_block_id)
        if block is None:
            errors.append(
                f"composer referenced unknown teaching_block_id {node.teaching_block_id!r}"
            )
            continue
        allowed = set(closed.get(node.teaching_block_id, ()))
        if node.kind not in allowed:
            errors.append(
                f"composer kind {node.kind!r} is outside allowed_kinds={sorted(allowed)} "
                f"for teaching block {node.teaching_block_id!r}"
            )
            continue
        covered_blocks.add(node.teaching_block_id)

    for block_id, allowed in closed.items():
        if allowed and block_id not in covered_blocks:
            errors.append(
                f"composer omitted teaching block {block_id!r} despite non-empty "
                f"allowed_kinds={list(allowed)}"
            )
        if not allowed and block_id in covered_blocks:
            errors.append(
                f"composer emitted ordinary content for task-only block {block_id!r}"
            )
    if not parsed.nodes:
        errors.append("composer returned no nodes")
    return errors


def _fallback_kind_for_block(
    block: TeachingPlanBlock,
    allowed: Sequence[str],
) -> tuple[str, str] | None:
    if not allowed:
        return None
    preferred, reason = choose_document_primitive(block)
    if preferred in allowed:
        return preferred, reason
    # Deterministic fallback inside the exact closed set. Never widen it.
    preference_order = ("paragraph", "list", "table", "figure", "callout", "heading")
    chosen = next((kind for kind in preference_order if kind in allowed), allowed[0])
    return chosen, f"{reason}; preferred kind unavailable, chose first legal {chosen!r}"


def heuristic_compose_document_plan(
    teaching_plan: TeachingPlan | Mapping[str, Any],
    *,
    path: Literal["print", "learn"],
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None = None,
) -> CompositionPlan:
    """Emergency fallback constrained by the same exact per-block allowlists."""
    plan = _as_plan(teaching_plan)
    section_map = _section_for_block(plan)
    closed = _closed_kind_map(plan, allowed_kinds_by_block)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        for block in section.blocks:
            choice = _fallback_kind_for_block(block, closed[block.id])
            if choice is None:
                continue
            kind, reason = choice
            decisions.append(
                CompositionDecision(
                    teaching_block_id=block.id,
                    kind=kind,
                    lane="document",
                    reason=f"heuristic fallback: {reason}",
                    section_id=section_map.get(block.id) or None,
                    role=None,
                )
            )
    return CompositionPlan(
        path=path,
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        composition_mode="heuristic_fallback",
        decisions=decisions,
    )


def _decisions_from_composer(
    plan: TeachingPlan,
    payload: Mapping[str, Any],
    *,
    path: Literal["print", "learn"],
) -> CompositionPlan:
    parsed = ComposerOutput.model_validate(payload)
    section_map = _section_for_block(plan)
    decisions = [
        CompositionDecision(
            teaching_block_id=node.teaching_block_id,
            kind=node.kind,
            lane="document",
            reason=node.reason,
            section_id=node.section_id or section_map.get(node.teaching_block_id) or None,
            role=node.role,
        )
        for node in parsed.nodes
    ]
    return CompositionPlan(
        path=path,
        teaching_plan_id=plan.teaching_plan_id,
        teaching_plan_revision=plan.revision,
        decisions=decisions,
    )


async def compose_document_plan(
    teaching_plan: TeachingPlan | Mapping[str, Any],
    *,
    path: Literal["print", "learn"],
    provider: AuthoringProvider | None = None,
    engine: AuthoringEngine | None = None,
    allow_heuristic_fallback: bool = True,
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None = None,
    work_order_id: str | None = None,
    call_budget: CallBudget | None = None,
    budget_ledger: CallBudgetLedger | None = None,
    checkpoint_store: CheckpointStore | None = None,
    progress_store: Any | None = None,
    progress_run_id: str | None = None,
) -> CompositionPlan:
    """LLM composition of ordinary document structure inside exact allowlists.

    Interactions and Print task treatments are path-owned and layered after
    composition. A block with an explicit empty ordinary allowlist is task-only
    and the composer is not allowed to manufacture ordinary content for it.
    """
    plan = _as_plan(teaching_plan)
    if not any(section.blocks for section in plan.sections):
        return CompositionPlan(
            path=path,
            teaching_plan_id=plan.teaching_plan_id,
            teaching_plan_revision=plan.revision,
            decisions=[],
        )

    closed = _closed_kind_map(plan, allowed_kinds_by_block)
    if allowed_kinds_by_block is not None and not any(closed.values()):
        return CompositionPlan(
            path=path,
            teaching_plan_id=plan.teaching_plan_id,
            teaching_plan_revision=plan.revision,
            decisions=[],
        )

    order_id = work_order_id or f"compose-{uuid.uuid4().hex[:12]}"
    definition = _composer_definition(path=path)
    inputs = {
        "teaching_plan": _teaching_plan_summary(
            plan, allowed_kinds_by_block=closed
        ),
        "allowed_kinds_by_block": {
            block_id: list(kinds) for block_id, kinds in closed.items()
        },
    }
    compatibility = CheckpointCompatibility(
        teaching_revision=int(plan.revision or 1),
        input_hash=content_hash(inputs),
        definition_hash=str(definition.definition_hash or ""),
        composition_identity=order_id,
    )
    checkpoint_key = f"composition:{order_id}"
    if checkpoint_store is not None:
        prior = checkpoint_store.get(checkpoint_key)
        if prior is not None and prior.status == "ready" and prior.payload is not None:
            return CompositionPlan.model_validate(prior.payload)

    if provider is None and engine is None:
        if allow_heuristic_fallback:
            return _budgeted_heuristic_fallback(
                plan,
                path=path,
                allowed_kinds_by_block=closed,
                call_budget=call_budget,
                budget_ledger=budget_ledger,
                work_order_id=order_id,
                checkpoint_store=checkpoint_store,
                compatibility=compatibility,
                checkpoint_key=checkpoint_key,
            )
        raise DocumentComposerError(
            "NO_PROVIDER",
            "document composer requires an authoring provider",
        )

    request = AuthoringRequest(
        work_order_id=order_id,
        definition=definition,
        scoped_request={
            "stage": "document_composition",
            "path": path,
            "allowed_kinds_by_block": {
                block_id: list(kinds) for block_id, kinds in closed.items()
            },
            "allow_heuristic_fallback": allow_heuristic_fallback,
        },
        inputs=inputs,
        teaching_revision=int(plan.revision or 1),
        source_identities=(str(plan.teaching_plan_id or "teaching-plan"),),
        mode="generate",
        policy={
            "allow_heuristic_composition_fallback": allow_heuristic_fallback,
            "closed_per_block_allowlists": True,
        },
    )
    repair_cap = 1 if allow_heuristic_fallback else 2
    selected = engine or AuthoringEngine(
        registry=AuthoringRegistry().with_validator(
            "document.composer_schema", _noop_validator
        ),
        provider=provider,
        max_repair_attempts=repair_cap,
        max_transport_attempts=1,
        call_budget=call_budget,
        budget_ledger=budget_ledger,
        max_provider_calls=3,
        progress_store=progress_store,
        progress_run_id=progress_run_id,
        progress_stage="composition",
    )
    if checkpoint_store is not None:
        checkpoint_store.begin(checkpoint_key, compatibility=compatibility)

    try:
        result = await selected.execute(
            request,
            provider=provider,
            call_budget=call_budget,
        )
    except AuthoringEngineError as exc:
        if allow_heuristic_fallback:
            return _budgeted_heuristic_fallback(
                plan,
                path=path,
                allowed_kinds_by_block=closed,
                call_budget=call_budget or selected.call_budget,
                budget_ledger=budget_ledger or selected.budget_ledger,
                work_order_id=order_id,
                checkpoint_store=checkpoint_store,
                compatibility=compatibility,
                checkpoint_key=checkpoint_key,
            )
        raise DocumentComposerError(exc.code, str(exc)) from exc

    errors = _validate_composer_payload(
        plan,
        result.payload,
        allowed_kinds_by_block=closed,
    )
    if errors:
        if allow_heuristic_fallback:
            return _budgeted_heuristic_fallback(
                plan,
                path=path,
                allowed_kinds_by_block=closed,
                call_budget=call_budget or selected.call_budget,
                budget_ledger=budget_ledger or selected.budget_ledger,
                work_order_id=order_id,
                checkpoint_store=checkpoint_store,
                compatibility=compatibility,
                checkpoint_key=checkpoint_key,
            )
        raise DocumentComposerError(
            "INVALID_COMPOSITION",
            "; ".join(errors),
        )
    composed = _decisions_from_composer(plan, result.payload, path=path)
    if checkpoint_store is not None:
        checkpoint_store.commit(
            checkpoint_key,
            payload=composed.model_dump(mode="json"),
            compatibility=compatibility,
            outcome=composed.composition_mode,
        )
    return composed


def _budgeted_heuristic_fallback(
    plan: TeachingPlan,
    *,
    path: Literal["print", "learn"],
    allowed_kinds_by_block: Mapping[str, Sequence[str]] | None,
    call_budget: CallBudget | None,
    budget_ledger: CallBudgetLedger | None,
    work_order_id: str,
    checkpoint_store: CheckpointStore | None,
    compatibility: CheckpointCompatibility,
    checkpoint_key: str,
) -> CompositionPlan:
    budget = call_budget
    if budget is None and budget_ledger is not None:
        budget = budget_ledger.get_or_create(work_order_id, max_calls=3)
    if budget is not None:
        try:
            budget.declare_fallback()
        except BudgetExhaustedError as exc:
            raise DocumentComposerError("BUDGET_EXHAUSTED", str(exc)) from exc
        if budget_ledger is not None:
            budget_ledger.persist(budget)
    composed = heuristic_compose_document_plan(
        plan,
        path=path,
        allowed_kinds_by_block=allowed_kinds_by_block,
    )
    if checkpoint_store is not None:
        checkpoint_store.commit(
            checkpoint_key,
            payload=composed.model_dump(mode="json"),
            compatibility=compatibility,
            outcome=composed.composition_mode,
        )
    return composed


__all__ = [
    "COMPOSER_SCHEMA",
    "ComposerOutput",
    "DocumentComposerError",
    "compose_document_plan",
    "heuristic_compose_document_plan",
]
