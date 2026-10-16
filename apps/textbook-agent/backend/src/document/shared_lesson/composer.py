"""Path-neutral composition of a section's closed ordinary node shape."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import (
    TeachingPlanBlock,
    TeachingPlanSection,
    VisualSpec,
)
from document.shared_lesson.schema_refs import inline_json_schema_refs
from infra.llm.output_failure import OutputFailureSummary, summarize_output_failure

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
        "table_duplicates_table_figure",
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
        "table_duplicates_table_figure",
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
    "compare": ("alternative", "option", "rival"),
}


#: Block intents (the closed Teaching Plan ``IntentId`` vocabulary) that make a
#: section an *explaining* section. No new plan field: the section's existing
#: block intents are the signal.
EXPLAINING_INTENTS = frozenset(
    {
        "explain",
        "explain-cause",
        "trace-flow",
        "show-structure",
        "demonstrate",
        "derive",
        "define",
        "name-parts",
        "model-thinking",
    }
)
#: Id prefix of the code-owned key-idea slot.
KEY_IDEA_SLOT_PREFIX = "shared-key-idea-"


def is_explaining_section(section: TeachingPlanSection) -> bool:
    """True when any block of the section carries an explaining intent."""
    return any(block.intent in EXPLAINING_INTENTS for block in section.blocks)


def key_idea_slot_for_section(section: TeachingPlanSection) -> CompositionItem:
    """The code-owned key-idea callout slot: first item, owned by the first block.

    Owning it by the first block keeps the composition in Teaching Plan block
    order, which the writer request validates.
    """
    return CompositionItem(
        id=_stable_id(
            KEY_IDEA_SLOT_PREFIX.rstrip("-"), f"{section.slot_id}\0{section.blocks[0].id}"
        ),
        kind="callout",
        teaching_block_id=section.blocks[0].id,
        semantic_role="explanation",
    )


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


_TABLE_WORD = re.compile(r"\btable\b", re.IGNORECASE)


def visual_is_table(visual: VisualSpec | None) -> bool:
    """True when a block's visual spec asks for a table (figure of a table).

    Looks for the whole word "table" in ``purpose`` or any ``must_show`` item.
    """
    if visual is None:
        return False
    return any(_TABLE_WORD.search(text) for text in (visual.purpose, *visual.must_show))


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
        if kind == "table" and visual_is_table(block.visual):
            continue  # the block's figure already shows the table
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
    forbid_table_duplicating_figure: bool = False,
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
                f"{choice.kind} is unsuitable for semantic role {choice.semantic_role!r};"
                f" {choice.kind} allows {', '.join(sorted(_KIND_ROLES[choice.kind]))}",
            )
        if choice.kind == "heading" and not _has_genuine_subsection_cue(block):
            _fail(
                "heading_missing_subsection_cue",
                f"blocks/{block.id}",
                f"heading for block {block.id!r} lacks a genuine subsection cue",
            )
        if (
            forbid_table_duplicating_figure
            and choice.kind == "table"
            and visual_is_table(block.visual)
        ):
            _fail(
                "table_duplicates_table_figure",
                f"choices[{choice_index}].kind",
                f"block {block.id!r} already shows a table as its figure; choose a"
                " paragraph (or another eligible kind) instead of a table"
                + _kind_missing_cue_guidance(block),
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
    reserve_key_idea: bool = True,
    forbid_table_duplicating_figure: bool = False,
) -> SectionCompositionPlan:
    """Validate model-selected form and build stable IDs plus fixed task anchors.

    ``forbid_table_duplicating_figure`` is True only for fresh provider drafts;
    stored plans are re-verified without it so existing lessons stay valid.

    Shape targets are advisory on every call. ``accept_soft_issues`` remains
    accepted for durable callers that already pass it, but it no longer
    changes provider choices or readiness. Identity, schema, and contract
    violations still fail closed.

    ``reserve_key_idea`` makes an explaining section (see
    ``is_explaining_section``) start with one code-owned ``key_idea`` callout
    slot that the writer fills. Any provider callout with the ``explanation``
    role is folded into that slot (a block it would leave empty gets a plain
    explanation paragraph). The slot is added after shape evaluation, so it
    never triggers a callout-count advisory. Verification of stored plans
    passes ``False`` unless the plan already contains a slot.
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
        forbid_table_duplicating_figure=forbid_table_duplicating_figure,
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
    if reserve_key_idea and blocks and is_explaining_section(section):
        for block in blocks:
            kept = [
                choice
                for choice in choices_by_block[block.id]
                if not (choice.kind == "callout" and choice.semantic_role == "explanation")
            ]
            if not kept:
                kept = [
                    CompositionChoice(
                        teaching_block_id=block.id, kind="paragraph", semantic_role="explanation"
                    )
                ]
            choices_by_block[block.id] = kept
        items.append(key_idea_slot_for_section(section))
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
    has_slot = False
    for item in plan.items:
        if item.kind in ("task_anchor", "figure"):
            # Anchors and figures are code-owned and re-derived below.
            continue
        if item.kind == "callout" and item.id.startswith(KEY_IDEA_SLOT_PREFIX):
            # The code-owned key-idea slot is re-derived below. Plans stored
            # before the slot existed have none and verify unchanged.
            has_slot = True
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
        section=section,
        choices=choices,
        tasks=tasks,
        policy=policy,
        accept_soft_issues=True,
        reserve_key_idea=has_slot,
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
    previous_draft: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build the composer request.

    On repair, ``repair_errors`` holds one ``path: code - message`` line per hard
    issue and ``previous_draft`` holds the rejected reply's ``items`` (``None``
    when that reply was empty or not a JSON object).
    """
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
        "previous_draft": {"items": list(previous_draft)} if previous_draft is not None else None,
    }


class _RawCompositionDraft(BaseModel):
    """Provider output type: shows the model the closed draft schema, validates nothing.

    ``compose_section`` validates the reply itself, so a reply that breaks the
    schema is kept and shown to the repair call instead of being discarded by
    the provider library. Only a reply that is not a JSON object still fails here.
    """

    model_config = ConfigDict(extra="allow")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> dict[str, Any]:
        return inline_json_schema_refs(SectionCompositionDraft.model_json_schema(mode="validation"))


def draft_as_json(draft: Any) -> Any:
    """Return a composer reply as plain JSON-shaped data (models are dumped)."""
    if isinstance(draft, BaseModel):
        return draft.model_dump(mode="json")
    return draft


async def _default_provider(payload: dict[str, Any]) -> Any:
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.structured_provider import run_structured_agent

    reply = await run_structured_agent(
        node_name="section_composer",
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("section-composer"),
        user_prompt=json.dumps(payload, sort_keys=True),
        output_type=_RawCompositionDraft,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(max_attempts=1),
    )
    # The raw parsed JSON, never a validated model: the caller validates it and
    # shows it back to the repair call when it is wrong.
    return draft_as_json(reply)


_FIGURE_KIND_MESSAGE = (
    "figure is not a composer kind: figures are placed by code from the"
    " Teaching Plan and must not be emitted"
)
_EMPTY_REPLY_MESSAGE = (
    "your previous reply was empty or was not a JSON object matching the closed"
    " composition schema; return the complete JSON draft"
)
_ITEM_INDEX = re.compile(r"^items\[(\d+)\]")
_SCHEMA_FIELD_HINTS: dict[str, str] = {
    "kind": "kind must be one of: " + ", ".join(sorted(_KIND_ROLES)),
    "semantic_role": "semantic_role must be one of: "
    + ", ".join(sorted(set().union(*_KIND_ROLES.values()))),
    "teaching_block_id": "teaching_block_id must be a Teaching Plan block id",
}


def _schema_issue_message(data: Any, path: str, error_type: str) -> str:
    """Repair guidance for one schema issue; never echoes the provider's text."""
    field = path.rsplit(".", 1)[-1] if "." in path else path
    match = _ITEM_INDEX.match(path)
    items = data.get("items") if isinstance(data, dict) else None
    if field == "kind" and match is not None and isinstance(items, list):
        index = int(match.group(1))
        item = items[index] if index < len(items) else None
        if isinstance(item, dict) and item.get("kind") == "figure":
            return _FIGURE_KIND_MESSAGE
    if error_type == "extra_forbidden":
        return "field is not part of the schema; remove it"
    if error_type == "missing":
        return "required field is missing"
    if path == "items" and error_type == "too_short":
        return "items must contain at least one choice"
    return _SCHEMA_FIELD_HINTS.get(field, f"value fails the closed schema ({error_type})")


def _schema_error(
    data: Any, summary: OutputFailureSummary | None
) -> CompositionValidationError:
    """Turn a provider schema/empty-reply failure into a repairable composer error.

    Paths are ``loc``-built and messages come from fixed guidance, so neither
    carries provider output.
    """
    if summary is None or not summary.issues:
        return CompositionValidationError(
            [_EMPTY_REPLY_MESSAGE], [("provider_draft_schema_invalid", "")]
        )
    pairs = summary.issues
    if any(_ITEM_INDEX.match(path) for path, _error_type in pairs):
        # Pydantic also reports ``items`` as too short when an entry fails; the
        # entry-level issue is the real one.
        pairs = tuple(pair for pair in pairs if pair != ("items", "too_short"))
    return CompositionValidationError(
        [_schema_issue_message(data, path, error_type) for path, error_type in pairs],
        [("provider_draft_schema_invalid", path) for path, _error_type in pairs],
    )


def _validate_raw_draft(data: Any) -> SectionCompositionDraft:
    try:
        return SectionCompositionDraft.model_validate(data)
    except ValidationError as exc:
        raise _schema_error(data, summarize_output_failure(exc)) from exc


def _repair_lines(error: CompositionValidationError) -> tuple[str, ...]:
    """One ``path: code - message`` line per hard issue, for the repair call."""
    return tuple(
        f"{path or 'draft'}: {code} - {message}"
        for message, (code, path) in zip(error.errors, error.issues, strict=False)
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
    sent through the bounded correction call, together with the rejected
    draft's ``items`` so the provider corrects it instead of re-planning. The
    provider returns raw JSON that is validated here; an empty/non-actionable
    provider reply becomes a ``provider_draft_schema_invalid`` error and is
    repaired without a draft. Other provider errors (transport, timeouts)
    propagate unchanged.
    """
    dispatch = provider or _default_provider
    repair_errors: tuple[str, ...] = ()
    previous_draft: list[Any] | None = None
    for attempt in range(2):
        data: Any = None
        try:
            try:
                raw = await dispatch(
                    _section_prompt_payload(section, tasks, repair_errors, previous_draft)
                )
            except Exception as provider_exc:
                summary = summarize_output_failure(provider_exc)
                if summary is None:
                    raise
                raise _schema_error(None, summary) from provider_exc
            data = draft_as_json(raw)
            return validate_and_build_composition(
                section=section,
                choices=_validate_raw_draft(data),
                tasks=tasks,
                policy=policy,
                accept_soft_issues=(attempt == 1),
                forbid_table_duplicating_figure=True,
            )
        except CompositionValidationError as exc:
            if attempt == 1:
                raise
            repair_errors = _repair_lines(exc)
            items = data.get("items") if isinstance(data, dict) else None
            previous_draft = list(items) if isinstance(items, list) else None
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
    "EXPLAINING_INTENTS",
    "draft_as_json",
    "KEY_IDEA_SLOT_PREFIX",
    "compose_section",
    "is_explaining_section",
    "key_idea_slot_for_section",
    "figure_item_for_block",
    "validate_and_build_composition",
    "validate_composition_plan",
]
