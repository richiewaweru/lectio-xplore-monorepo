"""Stateless, path-neutral writer for one composed shared lesson section."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from curriculum.teaching_plan.models import LearnerActionId, TeachingPlanSection
from document.shared_lesson.composer import CompositionItem, SectionCompositionPlan
from document.shared_lesson.models import (
    CalloutDisplay,
    FigureAccessibility,
    FigureDisplay,
    HeadingDisplay,
    ListDisplay,
    NodeAccessibility,
    ParagraphDisplay,
    SharedLessonNode,
    SharedSection,
    TableDisplay,
    TaskAnchor,
    shared_lesson_node_adapter,
)


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SectionSource(_ClosedModel):
    id: str = Field(min_length=1)
    kind: Literal["approved_fact", "sourcebook_entry", "terminology", "evidence_constraint"]
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def _nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source text must not be blank")
        return value


class SectionTaskSummary(_ClosedModel):
    task_spec_id: str = Field(min_length=1)
    teaching_block_id: str = Field(min_length=1)
    action: LearnerActionId
    purpose: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    expected_evidence: str = Field(min_length=1)


class SectionWriterRequest(_ClosedModel):
    section: TeachingPlanSection
    composition_plan: SectionCompositionPlan
    sources: tuple[SectionSource, ...] = ()
    task_summaries: tuple[SectionTaskSummary, ...] = ()

    @field_validator("section")
    @classmethod
    def _require_v2_continuity(cls, value: TeachingPlanSection) -> TeachingPlanSection:
        required = (
            "display_title",
            "entry_state",
            "must_establish",
            "avoid_repeating",
            "bridge_from_previous",
            "exit_state",
        )
        missing = [name for name in required if name not in value.model_fields_set]
        if missing:
            raise ValueError(f"section writer requires continuity fields: {', '.join(missing)}")
        if not value.display_title or not value.display_title.strip():
            raise ValueError("section writer requires display_title")
        for field_name in ("entry_state", "must_establish", "avoid_repeating", "exit_state"):
            items = getattr(value, field_name)
            if items is None or any(not item.strip() for item in items):
                raise ValueError(f"section writer requires meaningful {field_name}")
        if not value.must_establish or not value.exit_state:
            raise ValueError("section writer requires must_establish and exit_state")
        if value.bridge_from_previous is not None and not value.bridge_from_previous.strip():
            raise ValueError("bridge_from_previous must be meaningful or null")
        return value

    @field_validator("composition_plan")
    @classmethod
    def _section_owns_composition(cls, value: SectionCompositionPlan, info):
        section = info.data.get("section")
        if section is not None and value.section_slot_id != section.slot_id:
            raise ValueError("composition plan belongs to a different section")
        return value

    @field_validator("task_summaries")
    @classmethod
    def _tasks_match_anchors(cls, value: tuple[SectionTaskSummary, ...], info):
        composition = info.data.get("composition_plan")
        section = info.data.get("section")
        if composition is None or section is None:
            return value
        task_ids = [task.task_spec_id for task in value]
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("task summaries must have unique task_spec_id values")
        block_ids = {block.id for block in section.blocks}
        for task in value:
            if task.teaching_block_id not in block_ids:
                raise ValueError(f"task summary {task.task_spec_id!r} has an unknown block")
        actual = [
            (item.task_spec_id, item.teaching_block_id)
            for item in composition.items
            if item.kind == "task_anchor"
        ]
        expected = [(task.task_spec_id, task.teaching_block_id) for task in value]
        if actual != expected:
            raise ValueError("task summaries must match composition TaskAnchors in order")
        return value

    @field_validator("sources")
    @classmethod
    def _unique_source_ids(cls, value: tuple[SectionSource, ...]):
        ids = [source.id for source in value]
        if len(ids) != len(set(ids)):
            raise ValueError("section source IDs must be unique")
        return value

    @model_validator(mode="after")
    def _composition_matches_section(self) -> SectionWriterRequest:
        section_block_ids = [block.id for block in self.section.blocks]
        if len(section_block_ids) != len(set(section_block_ids)):
            raise ValueError("Teaching Plan block IDs must be unique")
        block_order = {block_id: index for index, block_id in enumerate(section_block_ids)}
        item_ids = [item.id for item in self.composition_plan.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("composition item IDs must be unique")

        ordinary_by_block = {block_id: [] for block_id in section_block_ids}
        anchors_by_block = {block_id: [] for block_id in section_block_ids}
        for item in self.composition_plan.items:
            if item.teaching_block_id not in block_order:
                raise ValueError(f"composition item {item.id!r} has an unknown block owner")
            target = anchors_by_block if item.kind == "task_anchor" else ordinary_by_block
            target[item.teaching_block_id].append(item)
        if any(not ordinary_by_block[block_id] for block_id in section_block_ids):
            raise ValueError("composition plan must realize every Teaching Plan block")
        canonical_order = [
            item
            for block_id in section_block_ids
            for item in (*ordinary_by_block[block_id], *anchors_by_block[block_id])
        ]
        if list(self.composition_plan.items) != canonical_order:
            raise ValueError(
                "composition items must follow block order with anchors after block nodes"
            )
        task_count = len(self.task_summaries)
        if task_count > len(self.composition_plan.items):
            raise ValueError("composition plan is missing task anchors")
        return self


class _WrittenNodeBase(_ClosedModel):
    id: str = Field(min_length=1)
    teaching_block_id: str = Field(min_length=1)


class WrittenParagraph(_WrittenNodeBase):
    kind: Literal["paragraph"]
    display: ParagraphDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenHeading(_WrittenNodeBase):
    kind: Literal["heading"]
    display: HeadingDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenList(_WrittenNodeBase):
    kind: Literal["list"]
    display: ListDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenFigure(_WrittenNodeBase):
    kind: Literal["figure"]
    display: FigureDisplay
    accessibility: FigureAccessibility


class WrittenTable(_WrittenNodeBase):
    kind: Literal["table"]
    display: TableDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenCallout(_WrittenNodeBase):
    kind: Literal["callout"]
    display: CalloutDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


WrittenNode = Annotated[
    WrittenParagraph | WrittenHeading | WrittenList | WrittenFigure | WrittenTable | WrittenCallout,
    Field(discriminator="kind"),
]


class SectionWriterDraft(_ClosedModel):
    nodes: tuple[WrittenNode, ...] = Field(min_length=1)


class SectionWriteResult(_ClosedModel):
    section_slot_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    nodes: tuple[SharedLessonNode, ...] = Field(min_length=1)

    def as_shared_section(self, *, section_id: str, position: int) -> SharedSection:
        return SharedSection(
            id=section_id,
            title=self.title,
            position=position,
            nodes=self.nodes,
        )


class SectionWriteValidationError(ValueError):
    """A valid structured draft does not satisfy its composition/source contract."""

    def __init__(self, errors: Sequence[str], *, affected_node_ids: Sequence[str] = ()):
        self.errors = tuple(errors)
        self.affected_node_ids = tuple(affected_node_ids)
        super().__init__("; ".join(self.errors))


Provider = Callable[[dict[str, Any]], Awaitable[Any]]

_TEXT_FIELDS = ("text", "caption", "title", "body", "description", "alt_text")
_INTERNAL_TERMS = re.compile(
    r"\b(?:section_slot_id|teaching_block_id|task_spec_id|entry_state|must_establish|"
    r"avoid_repeating|bridge_from_previous|exit_state|composition_plan|task_anchor|"
    r"sourcebook_refs|teaching plan|learn widget|print page|page layout|renderer)\b",
    re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"\b(?:TODO|TBD|placeholder|lorem ipsum)\b|\[\s*insert\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?%?(?![A-Za-z])")


def _composition_error(
    message: str, item: CompositionItem | None = None
) -> SectionWriteValidationError:
    return SectionWriteValidationError(
        [message], affected_node_ids=(item.id,) if item is not None else ()
    )


def _node_text_values(node: WrittenNode) -> list[str]:
    display = node.display.model_dump(mode="json")
    accessibility = node.accessibility.model_dump(mode="json")
    values: list[str] = []
    for mapping in (display, accessibility):
        for key, value in mapping.items():
            if isinstance(value, str) and key in _TEXT_FIELDS:
                values.append(value)
            elif isinstance(value, list):
                values.extend(item for item in value if isinstance(item, str))
            elif isinstance(value, list) and value and isinstance(value[0], list):
                values.extend(cell for row in value for cell in row if isinstance(cell, str))
    # Table cells are nested tuples after JSON-mode serialization.
    if isinstance(node, WrittenTable):
        values.extend(node.display.headers)
        values.extend(cell for row in node.display.rows for cell in row)
    if isinstance(node, WrittenList):
        values.extend(node.display.items)
    return values


def _approved_numbers(request: SectionWriterRequest) -> set[str]:
    context = [
        request.section.display_title or "",
        request.section.specific_purpose,
        request.section.bridge_from_previous or "",
        *(request.section.entry_state or ()),
        *(request.section.must_establish or ()),
        *(request.section.avoid_repeating or ()),
        *(request.section.exit_state or ()),
        *(
            value
            for block in request.section.blocks
            for value in (block.intent, block.brief, block.evidence)
        ),
        *(source.text for source in request.sources),
        *(
            value
            for task in request.task_summaries
            for value in (task.purpose, task.prompt, task.expected_evidence)
        ),
    ]
    return {match.group(0) for text in context for match in _NUMBER.finditer(text)}


def _internal_identifiers(request: SectionWriterRequest) -> tuple[str, ...]:
    candidates = {
        request.section.slot_id,
        *(block.id for block in request.section.blocks),
        *(item.id for item in request.composition_plan.items),
        *(task.task_spec_id for task in request.task_summaries),
        *(source.id for source in request.sources),
    }
    # Natural words used as identifiers are too ambiguous to block. Generated
    # IDs with separators/digits remain detectable without suppressing prose.
    return tuple(sorted(value for value in candidates if any(not char.isalpha() for char in value)))


def _check_learner_text(
    node: WrittenNode, request: SectionWriterRequest, item: CompositionItem
) -> None:
    values = _node_text_values(node)
    required: list[str] = []
    if isinstance(node, (WrittenParagraph, WrittenHeading)):
        required.append(node.display.text)
    elif isinstance(node, WrittenList):
        required.extend(node.display.items)
    elif isinstance(node, WrittenFigure):
        required.append(node.accessibility.alt_text)
    elif isinstance(node, WrittenTable):
        if not node.display.headers or not node.display.rows:
            raise _composition_error("tables require headers and at least one row", item)
        width = len(node.display.headers)
        if any(len(row) != width for row in node.display.rows):
            raise _composition_error("table rows must match the header width", item)
        required.extend(node.display.headers)
        required.extend(cell for row in node.display.rows for cell in row)
    elif isinstance(node, WrittenCallout):
        required.append(node.display.body)
    for text in required:
        if not text.strip():
            raise _composition_error("learner-facing content must not be blank", item)
    all_inputs = _approved_numbers(request)
    identifiers = _internal_identifiers(request)
    for value in values:
        if not value.strip() and value:
            raise _composition_error("learner-facing content must not be blank", item)
        if _INTERNAL_TERMS.search(value) or _PLACEHOLDER.search(value):
            raise _composition_error(
                "learner-facing content leaks planning text or a placeholder", item
            )
        for identifier in identifiers:
            if re.search(rf"(?<!\w){re.escape(identifier)}(?!\w)", value, flags=re.IGNORECASE):
                raise _composition_error(
                    "learner-facing content leaks an internal identifier", item
                )
        for number in _NUMBER.finditer(value):
            if number.group(0) not in all_inputs:
                raise _composition_error(
                    f"learner-facing content contains unsupported numeric fact {number.group(0)!r}",
                    item,
                )


def validate_and_build_section(
    *, request: SectionWriterRequest, draft: SectionWriterDraft | Any
) -> SectionWriteResult:
    """Validate exact composed shape, then insert immutable TaskAnchors by code."""
    try:
        parsed = (
            draft
            if isinstance(draft, SectionWriterDraft)
            else SectionWriterDraft.model_validate(draft)
        )
    except ValidationError as exc:
        raise SectionWriteValidationError(
            ("writer output violates the closed node schema",)
        ) from exc

    expected = [item for item in request.composition_plan.items if item.kind != "task_anchor"]
    if len(parsed.nodes) != len(expected):
        raise SectionWriteValidationError(
            [f"writer must return exactly {len(expected)} ordinary nodes"],
            affected_node_ids=tuple(item.id for item in expected),
        )
    node_by_id: dict[str, SharedLessonNode] = {}
    for expected_item, written in zip(expected, parsed.nodes, strict=True):
        if written.id != expected_item.id:
            raise _composition_error(
                "writer changed, omitted, or reordered a node ID", expected_item
            )
        if written.kind != expected_item.kind:
            raise _composition_error("writer changed a composed node kind", expected_item)
        if written.teaching_block_id != expected_item.teaching_block_id:
            raise _composition_error("writer changed teaching block ownership", expected_item)
        _check_learner_text(written, request, expected_item)
        payload = written.model_dump(mode="json")
        try:
            node_by_id[written.id] = shared_lesson_node_adapter.validate_python(payload)
        except ValidationError as exc:
            raise _composition_error(
                "writer node failed the shared document schema", expected_item
            ) from exc

    final_nodes: list[SharedLessonNode] = []
    for item in request.composition_plan.items:
        if item.kind == "task_anchor":
            task = next(
                summary
                for summary in request.task_summaries
                if summary.task_spec_id == item.task_spec_id
            )
            if task.teaching_block_id != item.teaching_block_id:
                raise _composition_error(
                    "TaskAnchor ownership differs from its finalized task", item
                )
            final_nodes.append(
                TaskAnchor(
                    id=item.id,
                    kind="task_anchor",
                    task_spec_id=task.task_spec_id,
                    teaching_block_id=task.teaching_block_id,
                    role=None,
                )
            )
        else:
            final_nodes.append(node_by_id[item.id])
    return SectionWriteResult(
        section_slot_id=request.section.slot_id,
        title=request.section.display_title or "",
        nodes=tuple(final_nodes),
    )


def _request_payload(
    request: SectionWriterRequest,
    *,
    repair_scope: str,
    errors: Sequence[str],
    affected_node_ids: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "section_contract": {
            "display_title": request.section.display_title,
            "entry_state": request.section.entry_state,
            "must_establish": request.section.must_establish,
            "avoid_repeating": request.section.avoid_repeating,
            "bridge_from_previous": request.section.bridge_from_previous,
            "exit_state": request.section.exit_state,
            "specific_purpose": request.section.specific_purpose,
            "blocks": [
                {
                    "id": block.id,
                    "intent": block.intent,
                    "brief": block.brief,
                    "evidence": block.evidence,
                }
                for block in request.section.blocks
            ],
        },
        "composition_plan": [
            item.model_dump(mode="json") for item in request.composition_plan.items
        ],
        "sources": [source.model_dump(mode="json") for source in request.sources],
        "task_summaries": [task.model_dump(mode="json") for task in request.task_summaries],
        "repair": (
            {
                "scope": repair_scope,
                "issues": list(errors),
                "affected_node_ids": list(affected_node_ids),
            }
            if errors
            else None
        ),
    }


async def _default_provider(payload: dict[str, Any]) -> Any:
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.structured_provider import run_structured_agent

    return await run_structured_agent(
        node_name="shared_section_writer",
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("shared-section-writer"),
        user_prompt=json.dumps(payload, sort_keys=True),
        output_type=SectionWriterDraft,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(max_attempts=1),
    )


async def write_section(
    *, request: SectionWriterRequest, provider: Provider | None = None
) -> SectionWriteResult:
    """Write one section with one initial, one section, and one targeted call max."""
    dispatch = provider or _default_provider
    repair_scopes = ("initial", "section", "targeted")
    issues: tuple[str, ...] = ()
    affected_node_ids: tuple[str, ...] = ()
    last_error: SectionWriteValidationError | None = None
    for attempt, scope in enumerate(repair_scopes):
        raw = await dispatch(
            _request_payload(
                request,
                repair_scope=scope,
                errors=issues,
                affected_node_ids=affected_node_ids,
            )
        )
        try:
            return validate_and_build_section(request=request, draft=raw)
        except SectionWriteValidationError as exc:
            last_error = exc
            issues = exc.errors
            affected_node_ids = exc.affected_node_ids
            if attempt == len(repair_scopes) - 1:
                raise
    if last_error is None:
        raise AssertionError("bounded writer loop exhausted unexpectedly")
    raise last_error


__all__ = [
    "SectionSource",
    "SectionTaskSummary",
    "SectionWriteResult",
    "SectionWriteValidationError",
    "SectionWriterDraft",
    "SectionWriterRequest",
    "WrittenCallout",
    "WrittenFigure",
    "WrittenHeading",
    "WrittenList",
    "WrittenNode",
    "WrittenParagraph",
    "WrittenTable",
    "validate_and_build_section",
    "write_section",
]
