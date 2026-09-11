"""LLM document composer — Teaching Plan → compact CompositionPlan choices.

Composition describes STRUCTURE choices only (kind/role/reason), never content.
Heuristics in ``document.heuristics`` remain a narrow emergency fallback.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from curriculum.teaching_plan.models import TeachingPlan, TeachingPlanBlock
from document.composition import CompositionDecision, CompositionPlan
from document.heuristics import choose_document_primitive
from document.models import DOCUMENT_PRIMITIVE_KINDS
from document.writer_prompts import document_composer_prompt
from infra.authoring import (
    AuthoringDefinition,
    AuthoringEngine,
    AuthoringEngineError,
    AuthoringProvider,
    AuthoringRequest,
)
from infra.authoring.engine import AuthoringRegistry

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
                    # Prefer optional string over ["string","null"] for structured
                    # providers that reject OpenAPI-style nullable unions.
                    "section_id": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": sorted(DOCUMENT_PRIMITIVE_KINDS),
                    },
                    "role": {"type": "string"},
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


def _teaching_plan_summary(plan: TeachingPlan) -> dict[str, Any]:
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
        required_inputs=("teaching_plan",),
        validator_refs=("document.composer_schema",),
        definition_hash="document-composer-v1",
    )


def _noop_validator(*_args: Any, **_kwargs: Any) -> list[Any]:
    return []


def _validate_composer_payload(
    plan: TeachingPlan,
    payload: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    try:
        parsed = ComposerOutput.model_validate(payload)
    except ValidationError as exc:
        return [str(exc)]

    known = _block_index(plan)
    seen_ids: set[str] = set()
    for node in parsed.nodes:
        if node.id in seen_ids:
            errors.append(f"duplicate composer node id {node.id!r}")
        seen_ids.add(node.id)
        if node.teaching_block_id not in known:
            errors.append(
                f"composer referenced unknown teaching_block_id {node.teaching_block_id!r}"
            )
        if node.kind not in DOCUMENT_PRIMITIVE_KINDS:
            errors.append(f"illegal ordinary kind {node.kind!r}")
    if not parsed.nodes:
        errors.append("composer returned no nodes")
    return errors


def heuristic_compose_document_plan(
    teaching_plan: TeachingPlan | Mapping[str, Any],
    *,
    path: Literal["print", "learn"],
) -> CompositionPlan:
    """Emergency fallback: one ordinary node per teaching block via heuristics."""
    plan = _as_plan(teaching_plan)
    section_map = _section_for_block(plan)
    decisions: list[CompositionDecision] = []
    for section in plan.sections:
        for block in section.blocks:
            kind, reason = choose_document_primitive(block)
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
) -> CompositionPlan:
    """LLM composition of ordinary document structure.

    Does not emit interactions or Print task treatments — those are path-owned
    and layered by the Learn/Print realizers after composition.
    """
    plan = _as_plan(teaching_plan)
    if not any(section.blocks for section in plan.sections):
        return CompositionPlan(
            path=path,
            teaching_plan_id=plan.teaching_plan_id,
            teaching_plan_revision=plan.revision,
            decisions=[],
        )

    if provider is None and engine is None:
        if allow_heuristic_fallback:
            return heuristic_compose_document_plan(plan, path=path)
        raise DocumentComposerError(
            "NO_PROVIDER",
            "document composer requires an authoring provider",
        )

    definition = _composer_definition(path=path)
    request = AuthoringRequest(
        work_order_id=f"compose-{uuid.uuid4().hex[:12]}",
        definition=definition,
        scoped_request={
            "stage": "document_composition",
            "path": path,
            "allowed_kinds": sorted(DOCUMENT_PRIMITIVE_KINDS),
        },
        inputs={"teaching_plan": _teaching_plan_summary(plan)},
        teaching_revision=int(plan.revision or 1),
        source_identities=(str(plan.teaching_plan_id or "teaching-plan"),),
        mode="generate",
    )
    selected = engine or AuthoringEngine(
        registry=AuthoringRegistry().with_validator(
            "document.composer_schema", _noop_validator
        ),
        provider=provider,
        max_repair_attempts=2,
    )
    try:
        result = await selected.execute(request, provider=provider)
    except AuthoringEngineError as exc:
        if allow_heuristic_fallback:
            return heuristic_compose_document_plan(plan, path=path)
        raise DocumentComposerError(exc.code, str(exc)) from exc

    errors = _validate_composer_payload(plan, result.payload)
    if errors:
        # Stage-local repair: one more generate with error feedback is handled by
        # AuthoringEngine already. If still invalid, fall back or raise.
        if allow_heuristic_fallback:
            return heuristic_compose_document_plan(plan, path=path)
        raise DocumentComposerError(
            "INVALID_COMPOSITION",
            "; ".join(errors),
        )
    return _decisions_from_composer(plan, result.payload, path=path)


__all__ = [
    "COMPOSER_SCHEMA",
    "ComposerOutput",
    "DocumentComposerError",
    "compose_document_plan",
    "heuristic_compose_document_plan",
]
