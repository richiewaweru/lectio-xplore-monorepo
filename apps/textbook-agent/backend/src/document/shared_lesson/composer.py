"""Path-neutral composition of a section's closed ordinary node shape."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection

OrdinaryNodeKind = Literal["paragraph", "heading", "list", "figure", "table", "callout"]
SemanticRole = Literal[
    "bridge",
    "explanation",
    "worked_example",
    "interpretation",
    "summary",
    "sequence",
    "comparison",
    "evidence",
    "visual_model",
    "visual_interpretation",
    "misconception",
    "safety_guidance",
    "subsection",
]


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CompositionChoice(_ClosedModel):
    """Provider choice; identity and TaskAnchor placement remain code-owned."""

    teaching_block_id: str = Field(min_length=1)
    kind: OrdinaryNodeKind
    semantic_role: SemanticRole


class SectionCompositionDraft(_ClosedModel):
    items: tuple[CompositionChoice, ...] = Field(min_length=1)


class CompositionItem(_ClosedModel):
    id: str = Field(min_length=1)
    kind: Literal["paragraph", "heading", "list", "figure", "table", "callout", "task_anchor"]
    teaching_block_id: str = Field(min_length=1)
    semantic_role: SemanticRole | None = None
    task_spec_id: str | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> CompositionItem:
        if self.kind == "task_anchor":
            if self.task_spec_id is None or self.semantic_role is not None:
                raise ValueError("task anchors require task_spec_id and no semantic_role")
        elif self.task_spec_id is not None or self.semantic_role is None:
            raise ValueError("ordinary items require semantic_role and cannot name a task")
        return self


class SectionCompositionPlan(_ClosedModel):
    section_slot_id: str = Field(min_length=1)
    items: tuple[CompositionItem, ...] = Field(min_length=1)


class CompositionPolicy(_ClosedModel):
    """Deterministic bounded policy; defaults implement the Phase 5 guardrails."""

    max_ordinary_nodes: int = Field(default=10, ge=1, le=40)
    max_nodes_per_block: int = Field(default=2, ge=1, le=8)
    max_callouts: int = Field(default=1, ge=0, le=4)


class CompositionValidationError(ValueError):
    """A structurally valid provider draft violates deterministic policy."""

    def __init__(self, errors: Sequence[str]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


Provider = Callable[[dict[str, Any]], Awaitable[Any]]

_KIND_ROLES: dict[str, set[str]] = {
    "paragraph": {
        "bridge",
        "explanation",
        "worked_example",
        "interpretation",
        "summary",
        "evidence",
        "misconception",
        "safety_guidance",
    },
    "heading": {"subsection"},
    "list": {"sequence", "evidence"},
    "figure": {"visual_model", "visual_interpretation"},
    "table": {"comparison", "evidence"},
    "callout": {"misconception", "safety_guidance"},
}
_SUBSECTION_CUES = ("subsection", "subtopic", "case study", "phase", "stage", "category")
_KIND_CUES: dict[str, tuple[str, ...]] = {
    "figure": (
        "visual",
        "diagram",
        "figure",
        "show",
        "model",
        "structure",
        "part",
        "flow",
        "map",
        "image",
    ),
    "table": ("compare", "contrast", "relationship", "data", "evidence"),
    "list": ("sequence", "step", "stage", "set", "category", "example", "evidence"),
}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _block_text(block: TeachingPlanBlock) -> str:
    return f"{block.intent} {block.brief} {block.evidence}".casefold()


def _has_genuine_subsection_cue(block: TeachingPlanBlock) -> bool:
    text = _block_text(block)
    return any(cue in text for cue in _SUBSECTION_CUES)


def validate_and_build_composition(
    *,
    section: TeachingPlanSection,
    choices: Sequence[CompositionChoice] | SectionCompositionDraft,
    tasks: Sequence[SharedTaskSpec],
    policy: CompositionPolicy | None = None,
) -> SectionCompositionPlan:
    """Validate model-selected form and build stable IDs plus fixed task anchors."""
    policy = policy or CompositionPolicy()
    draft_items = choices.items if isinstance(choices, SectionCompositionDraft) else tuple(choices)
    errors: list[str] = []
    blocks = list(section.blocks)
    block_by_id = {block.id: block for block in blocks}
    if len(block_by_id) != len(blocks):
        errors.append("Teaching Plan block IDs must be unique")

    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        errors.append("section task IDs must be unique")
    for task in tasks:
        if task.teaching_block_id not in block_by_id:
            errors.append(f"task {task.id!r} belongs to an unknown Teaching Plan block")

    block_order = {block.id: index for index, block in enumerate(blocks)}
    choices_by_block: dict[str, list[CompositionChoice]] = {block.id: [] for block in blocks}
    last_block_index = -1
    ordinary_count = 0
    paragraph_run = 0
    callout_count = 0
    for choice in draft_items:
        block = block_by_id.get(choice.teaching_block_id)
        if block is None:
            errors.append(f"unknown Teaching Plan block {choice.teaching_block_id!r}")
            continue
        index = block_order[block.id]
        if index < last_block_index:
            errors.append("ordinary nodes must preserve Teaching Plan block order")
        last_block_index = max(last_block_index, index)
        choices_by_block[block.id].append(choice)
        ordinary_count += 1
        if choice.kind == "paragraph":
            paragraph_run += 1
            if paragraph_run > 2:
                errors.append("more than two consecutive paragraphs")
        else:
            paragraph_run = 0
        if choice.kind == "callout":
            callout_count += 1
        if choice.semantic_role not in _KIND_ROLES[choice.kind]:
            errors.append(f"{choice.kind} is unsuitable for semantic role {choice.semantic_role!r}")
        if choice.kind == "heading" and not _has_genuine_subsection_cue(block):
            errors.append(f"heading for block {block.id!r} lacks a genuine subsection cue")
        kind_cues = _KIND_CUES.get(choice.kind)
        if kind_cues and not any(cue in _block_text(block) for cue in kind_cues):
            errors.append(f"{choice.kind} for block {block.id!r} lacks suitable semantic cues")
        if choice.kind == "callout":
            text = _block_text(block)
            cues = ("misconception", "mistake", "warning", "safety", "caution")
            if not any(cue in text for cue in cues):
                errors.append(f"callout for block {block.id!r} lacks cautionary semantics")

    for block in blocks:
        count = len(choices_by_block[block.id])
        if count == 0:
            errors.append(f"Teaching Plan block {block.id!r} has no ordinary node")
        if count > policy.max_nodes_per_block:
            errors.append(
                f"Teaching Plan block {block.id!r} exceeds {policy.max_nodes_per_block} ordinary nodes"
            )
    if ordinary_count > policy.max_ordinary_nodes:
        errors.append(f"section exceeds {policy.max_ordinary_nodes} ordinary nodes")
    if callout_count > policy.max_callouts:
        errors.append(f"section exceeds {policy.max_callouts} callouts")
    if errors:
        raise CompositionValidationError(errors)

    tasks_by_block: dict[str, list[SharedTaskSpec]] = {block.id: [] for block in blocks}
    for task in tasks:
        tasks_by_block[task.teaching_block_id].append(task)

    section_key = section.slot_id
    items: list[CompositionItem] = []
    for block in blocks:
        for offset, choice in enumerate(choices_by_block[block.id]):
            identity = f"{section_key}\0{block.id}\0{offset}\0{choice.kind}\0{choice.semantic_role}"
            items.append(
                CompositionItem(
                    id=_stable_id("shared-node", identity),
                    kind=choice.kind,
                    teaching_block_id=block.id,
                    semantic_role=choice.semantic_role,
                )
            )
        for task in tasks_by_block[block.id]:
            items.append(
                CompositionItem(
                    id=_stable_id("shared-task-anchor", task.id),
                    kind="task_anchor",
                    teaching_block_id=block.id,
                    task_spec_id=task.id,
                )
            )
    return SectionCompositionPlan(section_slot_id=section_key, items=tuple(items))


def validate_composition_plan(
    *,
    plan: SectionCompositionPlan,
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    policy: CompositionPolicy | None = None,
) -> None:
    """Reject mutated plans, including moved, duplicated, or invented anchors."""
    choices: list[CompositionChoice] = []
    for item in plan.items:
        if item.kind == "task_anchor":
            continue
        choices.append(
            CompositionChoice(
                teaching_block_id=item.teaching_block_id,
                kind=item.kind,
                semantic_role=item.semantic_role,
            )
        )
    expected = validate_and_build_composition(
        section=section, choices=choices, tasks=tasks, policy=policy
    )
    if plan != expected:
        expected_anchors = [item for item in expected.items if item.kind == "task_anchor"]
        actual_anchors = [item for item in plan.items if item.kind == "task_anchor"]
        if actual_anchors != expected_anchors:
            raise CompositionValidationError(
                ["TaskAnchors are missing, invented, reordered, or moved from their owning block"]
            )
        raise CompositionValidationError(
            ["composition plan differs from deterministic composition"]
        )


def _section_prompt_payload(
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    repair_errors: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "section": section.model_dump(mode="json"),
        "tasks": [
            {
                "id": task.id,
                "teaching_block_id": task.teaching_block_id,
                "action": task.action,
                "purpose": task.purpose,
                "expected_evidence": task.expected_evidence,
            }
            for task in tasks
        ],
        "repair_errors": list(repair_errors),
    }


async def _default_provider(payload: dict[str, Any]) -> Any:
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.structured_provider import run_structured_agent

    return await run_structured_agent(
        node_name="section_composer",
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("section-composer"),
        user_prompt=json.dumps(payload, sort_keys=True),
        output_type=SectionCompositionDraft,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(max_attempts=1),
    )


async def compose_section(
    *,
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    provider: Provider | None = None,
    policy: CompositionPolicy | None = None,
) -> SectionCompositionPlan:
    """Compose with one initial call and at most one validation-directed repair."""
    dispatch = provider or _default_provider
    previous_errors: tuple[str, ...] = ()
    for attempt in range(2):
        raw = await dispatch(_section_prompt_payload(section, tasks, previous_errors))
        try:
            draft = (
                raw
                if isinstance(raw, SectionCompositionDraft)
                else SectionCompositionDraft.model_validate(raw)
            )
            return validate_and_build_composition(
                section=section, choices=draft, tasks=tasks, policy=policy
            )
        except (ValidationError, CompositionValidationError) as exc:
            previous_errors = (
                exc.errors
                if isinstance(exc, CompositionValidationError)
                else ("invalid closed schema",)
            )
            if attempt == 1:
                raise CompositionValidationError(previous_errors) from exc
    raise AssertionError("bounded composer loop exhausted unexpectedly")


__all__ = [
    "CompositionChoice",
    "CompositionItem",
    "CompositionPolicy",
    "CompositionValidationError",
    "SectionCompositionDraft",
    "SectionCompositionPlan",
    "compose_section",
    "validate_and_build_composition",
    "validate_composition_plan",
]
