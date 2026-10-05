"""Path-neutral composition of a section's closed ordinary node shape."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanBlock, TeachingPlanSection

#: Figures are placed by code from the Teaching Plan visual spec; the composer
#: never chooses one.
OrdinaryNodeKind = Literal[
    "paragraph",
    "heading",
    "list",
    "table",
    "callout",
    "equation",
    "quote",
    "compare",
]
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
    kind: Literal[
        "paragraph",
        "heading",
        "list",
        "figure",
        "table",
        "callout",
        "equation",
        "quote",
        "compare",
        "task_anchor",
    ]
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
    #: Shape findings accepted as advisory records. Every code here is a member
    #: of ``SOFT_COMPOSITION_ISSUE_CODES``; never provider output or learner text.
    warnings: tuple[tuple[str, str], ...] = Field(default=(), exclude_if=lambda value: not value)

    @model_validator(mode="after")
    def _validate_warnings(self) -> SectionCompositionPlan:
        for code, _path in self.warnings:
            if code not in SOFT_COMPOSITION_ISSUE_CODES:
                raise ValueError(f"composition warning code {code!r} is not a soft issue code")
        return self


class CompositionPolicy(_ClosedModel):
    """Deterministic bounded policy; defaults implement the Phase 5 guardrails."""

    max_ordinary_nodes: int = Field(default=10, ge=1, le=40)
    max_nodes_per_block: int = Field(default=2, ge=1, le=8)
    max_callouts: int = Field(default=1, ge=0, le=4)


#: Closed, stable vocabulary of composer validation issue codes. Every
#: ``CompositionValidationError`` issue code must be a member of this set.
#: These codes (and the sanitized structural paths that accompany them) are
#: safe to persist in diagnostics: they never carry provider output, learner
#: content, or free-form validator text.
COMPOSITION_ISSUE_CODES = frozenset(
    {
        "duplicate_block_ids",
        "duplicate_task_ids",
        "task_unknown_block",
        "item_unknown_block",
        "block_order_violation",
        "paragraph_run_exceeded",
        "kind_role_mismatch",
        "heading_missing_subsection_cue",
        "kind_missing_semantic_cue",
        "callout_missing_cautionary_cue",
        "block_missing_ordinary_node",
        "block_exceeds_node_limit",
        "section_exceeds_node_limit",
        "section_exceeds_callout_limit",
        "task_anchor_mismatch",
        "plan_diverges_from_deterministic",
        "provider_draft_schema_invalid",
    }
)

#: HARD issue codes protect the accepted document contract. Shape targets such
#: as counts, runs, and preferred forms remain advisory and never trigger a
#: repair or alter the provider's chosen content.
HARD_COMPOSITION_ISSUE_CODES = frozenset(
    {
        "duplicate_block_ids",
        "duplicate_task_ids",
        "task_unknown_block",
        "item_unknown_block",
        "block_order_violation",
        "block_missing_ordinary_node",
        "task_anchor_mismatch",
        "plan_diverges_from_deterministic",
        "provider_draft_schema_invalid",
        "kind_role_mismatch",
    }
)

#: Advisory findings are persisted on the section plan and in telemetry. They
#: never drive a repair call or rewrite a provider choice.
SOFT_COMPOSITION_ISSUE_CODES = COMPOSITION_ISSUE_CODES - HARD_COMPOSITION_ISSUE_CODES

_MAX_COMPOSITION_PATH_LENGTH = 80


def _sanitize_composition_path(path: str) -> str:
    """Clamp a composer-built path to a safe, structural-only representation.

    Callers only ever pass paths built from node indices, ``kind``/field
    names, or approved Teaching Plan block/section IDs -- never provider
    output or learner text -- but this still bounds length and characters
    defensively before the path is eligible for diagnostic persistence.
    """
    safe = re.sub(r"[^A-Za-z0-9_\-./\[\]]", "_", path)
    return safe[:_MAX_COMPOSITION_PATH_LENGTH]


class CompositionValidationError(ValueError):
    """A structurally valid provider draft violates deterministic policy."""

    def __init__(
        self,
        errors: Sequence[str],
        issues: Sequence[tuple[str, str]] | None = None,
    ):
        self.errors = tuple(errors)
        if issues is None:
            issues = tuple(("provider_draft_schema_invalid", "") for _ in self.errors)
        for code, _path in issues:
            if code not in COMPOSITION_ISSUE_CODES:
                raise ValueError(f"unknown composition issue code {code!r}")
        self.issues: tuple[tuple[str, str], ...] = tuple(
            (code, _sanitize_composition_path(path)) for code, path in issues
        )
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
    "table": {"comparison", "evidence"},
    "callout": {"explanation", "summary", "misconception", "safety_guidance"},
    "equation": {"worked_example", "explanation", "sequence"},
    "quote": {"interpretation", "evidence", "misconception"},
    "compare": {"comparison"},
}
#: Role of the code-inserted figure item for a block that carries a visual spec.
_FIGURE_ROLE: SemanticRole = "visual_model"
_SUBSECTION_CUES = ("subsection", "subtopic", "case study", "phase", "stage", "category")
_KIND_CUES: dict[str, tuple[str, ...]] = {
    "table": ("compare", "contrast", "relationship", "data", "evidence"),
    "list": ("sequence", "step", "stage", "set", "category", "example", "evidence", "sort"),
    "equation": ("equation", "formula", "input", "output", "process", "calculate"),
    "quote": ("claim", "quote", "says", "assert"),
    "compare": ("compare", "contrast", "alternative", "option", "rival"),
}


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def figure_item_for_block(section_slot_id: str, block: TeachingPlanBlock) -> CompositionItem:
    """The code-owned figure item for a block whose plan carries a visual spec."""
    return CompositionItem(
        id=_stable_id("shared-figure-node", f"{section_slot_id}\0{block.id}"),
        kind="figure",
        teaching_block_id=block.id,
        semantic_role=_FIGURE_ROLE,
    )


def _block_text(block: TeachingPlanBlock) -> str:
    return f"{block.intent} {block.brief} {block.evidence}".casefold()


def _has_genuine_subsection_cue(block: TeachingPlanBlock) -> bool:
    text = _block_text(block)
    return any(cue in text for cue in _SUBSECTION_CUES)


_CALLOUT_CUES = (
    "key idea",
    "explain",
    "misconception",
    "mistake",
    "warning",
    "safety",
    "caution",
)


def _eligible_non_paragraph_kinds(block: TeachingPlanBlock) -> tuple[tuple[str, str], ...]:
    """Return (kind, matched cue) pairs this block is eligible for, per the
    same deterministic cue tables the validator uses. Paragraph is excluded
    because it is always eligible and needs no cue.
    """
    text = _block_text(block)
    eligible: list[tuple[str, str]] = []
    subsection_cue = next((cue for cue in _SUBSECTION_CUES if cue in text), None)
    if subsection_cue is not None:
        eligible.append(("heading", subsection_cue))
    for kind, cues in _KIND_CUES.items():
        matched = next((cue for cue in cues if cue in text), None)
        if matched is not None:
            eligible.append((kind, matched))
    callout_cue = next((cue for cue in _CALLOUT_CUES if cue in text), None)
    if callout_cue is not None:
        eligible.append(("callout", callout_cue))
    return tuple(eligible)


def _format_eligible_kinds(block_id: str, eligible: Sequence[tuple[str, str]]) -> str:
    if not eligible:
        return f"block {block_id!r} has no eligible non-paragraph kind"
    parts = "; ".join(f"{kind} (cue {cue!r})" for kind, cue in eligible)
    return f"block {block_id!r} is eligible for {parts}"


def _kind_missing_cue_guidance(block: TeachingPlanBlock) -> str:
    eligible = _eligible_non_paragraph_kinds(block)
    return " " + _format_eligible_kinds(block.id, eligible) + "; paragraph is always eligible."


def _evaluate_composition(
    *,
    draft_items: Sequence[CompositionChoice],
    blocks: Sequence[TeachingPlanBlock],
    block_by_id: dict[str, TeachingPlanBlock],
    block_order: dict[str, int],
    task_owning_block_ids: set[str],
    policy: CompositionPolicy,
    section_slot_id: str,
    soft_bounds: bool,
) -> tuple[
    list[str],
    list[tuple[str, str]],
    list[tuple[str, str]],
    dict[str, list[CompositionChoice]],
    int,
    int,
]:
    """One deterministic pass over ``draft_items``.

    ``soft_bounds`` is retained for compatibility with persisted callers.
    All shaping findings are advisory on every pass; only identity, schema,
    and contract violations are returned as errors.
    """
    errors: list[str] = []
    issues: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []

    def _fail(code: str, path: str, message: str) -> None:
        if code in HARD_COMPOSITION_ISSUE_CODES:
            errors.append(message)
            issues.append((code, path))
        else:
            warnings.append((code, path))

    def _warn(code: str, path: str) -> None:
        warnings.append((code, path))

    choices_by_block: dict[str, list[CompositionChoice]] = {block.id: [] for block in blocks}
    last_block_index = -1
    ordinary_count = 0
    paragraph_run = 0
    callout_count = 0
    callout_choice_paths: list[str] = []

    for choice_index, choice in enumerate(draft_items):
        block = block_by_id.get(choice.teaching_block_id)
        if block is None:
            _fail(
                "item_unknown_block",
                f"choices[{choice_index}]",
                f"unknown Teaching Plan block {choice.teaching_block_id!r}",
            )
            continue
        index = block_order[block.id]
        if index < last_block_index:
            _fail(
                "block_order_violation",
                f"choices[{choice_index}]",
                "ordinary nodes must preserve Teaching Plan block order",
            )
        last_block_index = max(last_block_index, index)
        choices_by_block[block.id].append(choice)
        ordinary_count += 1
        if choice.kind == "paragraph":
            paragraph_run += 1
            if paragraph_run > 2:
                path = f"choices[{choice_index}]"
                _warn("paragraph_run_exceeded", path)
        else:
            paragraph_run = 0
        if choice.kind == "callout":
            callout_count += 1
            callout_choice_paths.append(f"choices[{choice_index}].kind")
        if choice.semantic_role not in _KIND_ROLES[choice.kind]:
            _fail(
                "kind_role_mismatch",
                f"choices[{choice_index}].kind",
                f"{choice.kind} is unsuitable for semantic role {choice.semantic_role!r}",
            )
        if choice.kind == "heading" and not _has_genuine_subsection_cue(block):
            _fail(
                "heading_missing_subsection_cue",
                f"blocks/{block.id}",
                f"heading for block {block.id!r} lacks a genuine subsection cue",
            )
        kind_cues = _KIND_CUES.get(choice.kind)
        if kind_cues and not any(cue in _block_text(block) for cue in kind_cues):
            _fail(
                "kind_missing_semantic_cue",
                f"choices[{choice_index}].kind",
                f"{choice.kind} for block {block.id!r} lacks suitable semantic cues"
                + _kind_missing_cue_guidance(block),
            )
        if choice.kind == "callout":
            text = _block_text(block)
            callout_cues = (
                _CALLOUT_CUES
                if choice.semantic_role in {"explanation", "summary"}
                else _CALLOUT_CUES[2:]
            )
            if not any(cue in text for cue in callout_cues):
                _fail(
                    "callout_missing_cautionary_cue",
                    f"blocks/{block.id}",
                    f"callout for block {block.id!r} lacks cautionary semantics",
                )
        is_last_choice_for_block = (
            choice_index + 1 == len(draft_items)
            or draft_items[choice_index + 1].teaching_block_id != choice.teaching_block_id
        )
        if is_last_choice_for_block and block.id in task_owning_block_ids:
            # A TaskAnchor is inserted here (see below); it breaks the
            # paragraph run the same way code places it.
            paragraph_run = 0

    for block in blocks:
        count = len(choices_by_block[block.id])
        if count == 0:
            _fail(
                "block_missing_ordinary_node",
                f"blocks/{block.id}",
                f"Teaching Plan block {block.id!r} has no ordinary node",
            )
        elif count > policy.max_nodes_per_block:
            path = f"blocks/{block.id}"
            _warn("block_exceeds_node_limit", path)
    if ordinary_count > policy.max_ordinary_nodes:
        path = f"section/{section_slot_id}"
        _warn("section_exceeds_node_limit", path)
    for path in callout_choice_paths[policy.max_callouts :]:
        _warn("section_exceeds_callout_limit", path)

    return errors, issues, warnings, choices_by_block, ordinary_count, callout_count


def validate_and_build_composition(
    *,
    section: TeachingPlanSection,
    choices: Sequence[CompositionChoice] | SectionCompositionDraft,
    tasks: Sequence[SharedTaskSpec],
    policy: CompositionPolicy | None = None,
    accept_soft_issues: bool = False,
) -> SectionCompositionPlan:
    """Validate model-selected form and build stable IDs plus fixed task anchors.

    Shape targets are advisory on every call. ``accept_soft_issues`` remains
    accepted for durable callers that already pass it, but it no longer
    changes provider choices or readiness. Identity, schema, and contract
    violations still fail closed.
    """
    policy = policy or CompositionPolicy()
    draft_items = choices.items if isinstance(choices, SectionCompositionDraft) else tuple(choices)
    errors: list[str] = []
    issues: list[tuple[str, str]] = []

    def _fail(code: str, path: str, message: str) -> None:
        errors.append(message)
        issues.append((code, path))

    blocks = list(section.blocks)
    block_by_id = {block.id: block for block in blocks}
    if len(block_by_id) != len(blocks):
        _fail("duplicate_block_ids", "blocks", "Teaching Plan block IDs must be unique")

    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        _fail("duplicate_task_ids", "tasks", "section task IDs must be unique")
    for task_index, task in enumerate(tasks):
        if task.teaching_block_id not in block_by_id:
            _fail(
                "task_unknown_block",
                f"tasks[{task_index}]",
                f"task {task.id!r} belongs to an unknown Teaching Plan block",
            )

    block_order = {block.id: index for index, block in enumerate(blocks)}
    task_owning_block_ids = {task.teaching_block_id for task in tasks}

    (
        pass_errors,
        pass_issues,
        pass_warnings,
        choices_by_block,
        _pass_ordinary_count,
        _pass_callout_count,
    ) = _evaluate_composition(
        draft_items=draft_items,
        blocks=blocks,
        block_by_id=block_by_id,
        block_order=block_order,
        task_owning_block_ids=task_owning_block_ids,
        policy=policy,
        section_slot_id=section.slot_id,
        soft_bounds=accept_soft_issues,
    )
    errors.extend(pass_errors)
    issues.extend(pass_issues)

    warnings: tuple[tuple[str, str], ...] = tuple(pass_warnings)

    if errors:
        raise CompositionValidationError(errors, issues)

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
        if block.visual is not None:
            # Code-placed: after the block's ordinary nodes, before its anchors.
            items.append(figure_item_for_block(section_key, block))
        for task in tasks_by_block[block.id]:
            items.append(
                CompositionItem(
                    id=_stable_id("shared-task-anchor", task.id),
                    kind="task_anchor",
                    teaching_block_id=block.id,
                    task_spec_id=task.id,
                )
            )
    return SectionCompositionPlan(section_slot_id=section_key, items=tuple(items), warnings=warnings)


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
        if item.kind in ("task_anchor", "figure"):
            # Anchors and figures are code-owned and re-derived below.
            continue
        choices.append(
            CompositionChoice(
                teaching_block_id=item.teaching_block_id,
                kind=item.kind,
                semantic_role=item.semantic_role,
            )
        )
    # Warnings are excluded from the equality check below because they describe
    # the provider's accepted shape rather than code-owned identity.
    expected = validate_and_build_composition(
        section=section, choices=choices, tasks=tasks, policy=policy, accept_soft_issues=True
    )
    if plan.section_slot_id != expected.section_slot_id or plan.items != expected.items:
        expected_anchors = [item for item in expected.items if item.kind == "task_anchor"]
        actual_anchors = [item for item in plan.items if item.kind == "task_anchor"]
        section_path = f"section/{section.slot_id}"
        if actual_anchors != expected_anchors:
            raise CompositionValidationError(
                ["TaskAnchors are missing, invented, reordered, or moved from their owning block"],
                [("task_anchor_mismatch", section_path)],
            )
        raise CompositionValidationError(
            ["composition plan differs from deterministic composition"],
            [("plan_diverges_from_deterministic", section_path)],
        )


def _section_prompt_payload(
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    repair_errors: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "section": section.model_dump(mode="json"),
        "shaping_targets": {
            "paragraph_words_max": 60,
            "key_idea_words_max": 25,
            "note_words_max": 50,
            "misconception_words_max": {"belief": 30, "evidence": 45, "conclusion": 30},
            "list_item_words_max": 30,
            "table_cell_words_max": 12,
            "equation_inputs_target_max": 4,
            "equation_outputs_target_max": 3,
            "compare_items_target_max": 3,
            "prose_section_words_target": [150, 280],
        },
        "inline_vocabulary": {
            "strong": "**text**",
            "emphasis": "*text*",
            "subscript": "~text~",
            "superscript": "^text^",
            "paragraph_break": "\\n\\n",
        },
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


def _draft_contains_figure(raw: Any) -> bool:
    items = raw.get("items") if isinstance(raw, dict) else None
    return isinstance(items, list) and any(
        isinstance(item, dict) and item.get("kind") == "figure" for item in items
    )


async def compose_section(
    *,
    section: TeachingPlanSection,
    tasks: Sequence[SharedTaskSpec],
    provider: Provider | None = None,
    policy: CompositionPolicy | None = None,
) -> SectionCompositionPlan:
    """Compose with one initial call and at most one validation-directed repair.

    Shape findings are returned as warnings from the initial response and
    never trigger a repair. Only hard identity/schema/contract findings are
    sent through the bounded correction call.
    """
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
                section=section,
                choices=draft,
                tasks=tasks,
                policy=policy,
                accept_soft_issues=(attempt == 1),
            )
        except (ValidationError, CompositionValidationError) as exc:
            if isinstance(exc, CompositionValidationError):
                previous_errors = exc.errors
            elif _draft_contains_figure(raw):
                previous_errors = (
                    "figure is not a composer kind: figures are placed by code from the"
                    " Teaching Plan and must not be emitted",
                )
            else:
                previous_errors = ("invalid closed schema",)
            if attempt == 1:
                raise CompositionValidationError(
                    previous_errors,
                    exc.issues if isinstance(exc, CompositionValidationError)
                    else (("provider_draft_schema_invalid", "items"),),
                ) from exc
    raise AssertionError("bounded composer loop exhausted unexpectedly")


__all__ = [
    "COMPOSITION_ISSUE_CODES",
    "HARD_COMPOSITION_ISSUE_CODES",
    "SOFT_COMPOSITION_ISSUE_CODES",
    "CompositionChoice",
    "CompositionItem",
    "CompositionPolicy",
    "CompositionValidationError",
    "SectionCompositionDraft",
    "SectionCompositionPlan",
    "compose_section",
    "figure_item_for_block",
    "validate_and_build_composition",
    "validate_composition_plan",
]
