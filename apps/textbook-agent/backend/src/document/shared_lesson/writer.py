"""Stateless, path-neutral writer for one composed shared lesson section."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from curriculum.teaching_plan.models import LearnerActionId, TeachingPlanSection
from document.shared_lesson.composer import (
    KEY_IDEA_SLOT_PREFIX,
    CompositionItem,
    SectionCompositionPlan,
)
from document.shared_lesson.inline import parse_inline_markup
from document.shared_lesson.models import (
    CalloutDisplay,
    CompareDisplay,
    EquationDisplay,
    FigureDisplay,
    HeadingDisplay,
    ListDisplay,
    NodeAccessibility,
    ParagraphDisplay,
    SharedLessonNode,
    SharedSection,
    TableDisplay,
    TaskAnchor,
    QuoteDisplay,
    shared_lesson_node_adapter,
)
from infra.llm.output_failure import summarize_output_failure


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
    # Raw SharedTaskSpec.evaluation, kept only for the deterministic
    # answer-leakage check below. It is never serialized into the provider
    # payload -- see `_request_payload` -- and defaults to `{}` so existing
    # callers that do not yet supply it keep working unchanged.
    evaluation: dict[str, Any] = Field(default_factory=dict)


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
    #: Caption only. Alt text is never writer-authored; the persisted figure
    #: node carries an empty (pending) alt until media binds the ready result.
    display: FigureDisplay


class WrittenTable(_WrittenNodeBase):
    kind: Literal["table"]
    display: TableDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenCallout(_WrittenNodeBase):
    kind: Literal["callout"]
    display: CalloutDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenEquation(_WrittenNodeBase):
    kind: Literal["equation"]
    display: EquationDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenQuote(_WrittenNodeBase):
    kind: Literal["quote"]
    display: QuoteDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


class WrittenCompare(_WrittenNodeBase):
    kind: Literal["compare"]
    display: CompareDisplay
    accessibility: NodeAccessibility = Field(default_factory=NodeAccessibility)


WrittenNode = Annotated[
    WrittenParagraph
    | WrittenHeading
    | WrittenList
    | WrittenFigure
    | WrittenTable
    | WrittenCallout
    | WrittenEquation
    | WrittenQuote
    | WrittenCompare,
    Field(discriminator="kind"),
]


class SectionWriterDraft(_ClosedModel):
    nodes: tuple[WrittenNode, ...] = Field(min_length=1)


class SectionWriteResult(_ClosedModel):
    section_slot_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    nodes: tuple[SharedLessonNode, ...] = Field(min_length=1)
    #: Advisory shape findings recorded for the section. They are structural
    #: paths only and never provider output or learner text. They do not alter
    #: readiness or cause another provider call.
    warnings: tuple[tuple[str, str], ...] = Field(default=(), exclude_if=lambda value: not value)
    #: Repair modes ("patch" / "full") the bounded loop used, in call order.
    #: Content-free diagnostics only, recorded as an event. Never serialized:
    #: the persisted output hash must not depend on how the section was
    #: reached, or finalization (which rebuilds this model without it) sees
    #: stale hashes and terminally blocks the run.
    repair_modes: tuple[Literal["patch", "full"], ...] = Field(default=(), exclude=True)

    @model_validator(mode="after")
    def _validate_warnings(self) -> SectionWriteResult:
        for code, _path in self.warnings:
            if code not in SOFT_SECTION_WRITE_ISSUE_CODES | ADVISORY_SHAPE_ISSUE_CODES:
                raise ValueError(
                    f"writer warning code {code!r} is not a soft issue code or advisory shape code"
                )
        return self

    def as_shared_section(self, *, section_id: str, position: int) -> SharedSection:
        return SharedSection(
            id=section_id,
            title=self.title,
            position=position,
            nodes=self.nodes,
        )


#: Closed, stable vocabulary of writer validation issue codes. Every
#: ``SectionWriteValidationError`` issue code must be a member of this set.
#: These codes (and the sanitized structural paths that accompany them) are
#: safe to persist in diagnostics: they never carry provider output, learner
#: content, or free-form validator text. Mirrors the composer's
#: ``COMPOSITION_ISSUE_CODES`` convention (see composer.py).
SECTION_WRITE_ISSUE_CODES = frozenset(
    {
        "writer_draft_schema_invalid",
        "node_count_mismatch",
        "node_id_mismatch",
        "node_kind_mismatch",
        "node_block_mismatch",
        "node_shape_mismatch",
        "table_missing_headers_or_rows",
        "table_row_width_mismatch",
        "blank_text",
        "metadata_leaked",
        "task_answer_leaked",
        "internal_id_leaked",
        "unsupported_number",
        "task_anchor_ownership_mismatch",
        "length_over_target",
        "shape_missing",
        "list_item_not_parallel",
    }
)

#: These legacy soft findings retain the writer's bounded-repair behavior:
#: they are accepted with warnings only on the final bounded attempt.
SOFT_SECTION_WRITE_ISSUE_CODES = frozenset({"task_answer_leaked", "unsupported_number"})

#: Shape findings are advisory from the first attempt. They never enter the
#: repair loop, regardless of the legacy ``accept_soft_issues`` flag.
ADVISORY_SHAPE_ISSUE_CODES = frozenset(
    {
        "length_over_target",
        "shape_missing",
        "list_item_not_parallel",
    }
)

_MAX_WRITER_ISSUE_PATH_LENGTH = 80


def _sanitize_writer_issue_path(path: str) -> str:
    """Clamp a writer-built path to a safe, structural-only representation.

    Callers only ever pass paths built from node indices, ``kind``/field
    names, or approved Teaching Plan block/section IDs -- never provider
    output or learner text -- but this still bounds length and characters
    defensively before the path is eligible for diagnostic persistence.
    """
    safe = re.sub(r"[^A-Za-z0-9_\-./\[\]]", "_", path)
    return safe[:_MAX_WRITER_ISSUE_PATH_LENGTH]


class SectionWriteValidationError(ValueError):
    """A valid structured draft does not satisfy its composition/source contract."""

    def __init__(
        self,
        errors: Sequence[str],
        *,
        affected_node_ids: Sequence[str] = (),
        issues: Sequence[tuple[str, str]] | None = None,
        repair_modes: Sequence[str] = (),
    ):
        self.errors = tuple(errors)
        self.affected_node_ids = tuple(affected_node_ids)
        #: Repair modes used before this final failure (diagnostics only).
        self.repair_modes = tuple(repair_modes)
        if issues is None:
            issues = tuple(("writer_draft_schema_invalid", "") for _ in self.errors)
        for code, _path in issues:
            if code not in SECTION_WRITE_ISSUE_CODES:
                raise ValueError(f"unknown section write issue code {code!r}")
        self.issues: tuple[tuple[str, str], ...] = tuple(
            (code, _sanitize_writer_issue_path(path)) for code, path in issues
        )
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
_EXACT_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")

# Templates that assert a task's answer VALUE as a solved result, e.g.
# "x = 9", "gives x = 9", "equals 60", "is 9", "-> 60". Deliberately narrow:
# these only fire on a result-asserting construction next to one of a
# section's anchored-task answer values, never on the bare number occurring
# elsewhere (e.g. restating the task's own given operands).
_ANSWER_BOUNDARY = r"(?<!\d){value}(?!\d)(?!\.\d)"
_RESULT_TEMPLATES = tuple(
    template.format(value=_ANSWER_BOUNDARY)
    for template in (
        r"=\s*{value}",
        r"\bequals?\s*{value}",
        r"\bequal\s+to\s*{value}",
        r"\bis\s*{value}",
        r"\bgives?\s*(?:[a-zA-Z]\w*\s*=\s*)?{value}",
        r"\byields?\s*(?:[a-zA-Z]\w*\s*=\s*)?{value}",
        r"\bresults?\s+in\s*{value}",
        r"(?:→|->)\s*{value}",
    )
)


def _composition_error(
    message: str,
    item: CompositionItem | None = None,
    *,
    code: str,
    path: str = "",
) -> SectionWriteValidationError:
    return SectionWriteValidationError(
        [message],
        affected_node_ids=(item.id,) if item is not None else (),
        issues=((code, path),),
    )


def _node_text_values(node: WrittenNode) -> list[str]:
    def strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple)):
            return [part for item in value for part in strings(item)]
        if isinstance(value, dict):
            return [part for item in value.values() for part in strings(item)]
        return []

    values = strings(node.display.model_dump(mode="json"))
    if hasattr(node, "accessibility"):
        values.extend(strings(node.accessibility.model_dump(mode="json")))
    return values


def _required_node_texts(node: WrittenNode) -> tuple[str, ...]:
    display = node.display
    if isinstance(node, (WrittenParagraph, WrittenHeading)):
        return (display.text,)
    if isinstance(node, WrittenList):
        return tuple(display.items)
    if isinstance(node, WrittenFigure):
        return (display.caption,)
    if isinstance(node, WrittenTable):
        return (*display.headers, *(cell for row in display.rows for cell in row))
    if isinstance(node, WrittenCallout):
        if display.variant == "misconception":
            return tuple(
                value
                for value in (display.belief, display.evidence, display.conclusion)
                if value is not None
            )
        if display.variant in {"key_idea", "note"}:
            return (display.body or "",)
        return (display.body,) if display.body is not None else ()
    if isinstance(node, WrittenEquation):
        return (*display.inputs, *display.outputs)
    if isinstance(node, WrittenQuote):
        return (display.text,)
    if isinstance(node, WrittenCompare):
        return tuple(value for item in display.items for value in (item.title, item.body))
    return ()


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _inline_numeric_values(value: str) -> tuple[str, ...]:
    """Return numeric facts in plain inline text, excluding notation spans."""
    values: list[str] = []

    def visit(nodes: Any, notation: bool = False) -> None:
        for node in nodes:
            if node["type"] == "text":
                if not notation:
                    values.extend(match.group(0) for match in _NUMBER.finditer(node["value"]))
                continue
            visit(node["children"], notation or node["type"] in {"subscript", "superscript"})

    # The total parser leaves malformed markers as text, so they continue
    # through the genuine numeric-fact check instead of being swallowed.
    visit(parse_inline_markup(value))
    return tuple(values)


def _shape_warning(
    warnings: list[tuple[str, str]], code: str, path: str
) -> None:
    warning = (code, _sanitize_writer_issue_path(path))
    if warning not in warnings:
        warnings.append(warning)


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


def _numeric_literal(value: Any) -> str | None:
    """Return `value` as a bare numeric string, or None if it is not one.

    Only exact, short numeric literals are considered -- never option keys,
    free text, or option labels -- so this stays conservative about what
    counts as a leak-able "answer value".
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, str):
        stripped = value.strip()
        if _EXACT_NUMBER.fullmatch(stripped):
            return stripped
    return None


def _task_answer_values(task: SectionTaskSummary) -> set[str]:
    """Derive the numeric answer value(s) of one anchored task's evaluation.

    Inspects only the evaluation shapes that name an exact numeric result:
    ``exact_match`` (``correct_value``/``answer``), ``numeric`` (``value``),
    and ``accepted_answers`` (``accepted_answers``). Choice-key, mapping,
    ordered-match, rubric, and teacher-review evaluations do not name a
    literal numeric result and are intentionally left alone.
    """
    evaluation = task.evaluation or {}
    eval_type = evaluation.get("type")
    values: set[str] = set()
    if eval_type == "exact_match":
        for field in ("correct_value", "answer"):
            literal = _numeric_literal(evaluation.get(field))
            if literal is not None:
                values.add(literal)
    elif eval_type == "numeric":
        literal = _numeric_literal(evaluation.get("value"))
        if literal is not None:
            values.add(literal)
    elif eval_type == "accepted_answers":
        for candidate in evaluation.get("accepted_answers") or ():
            literal = _numeric_literal(candidate)
            if literal is not None:
                values.add(literal)
    return values


def _leaked_task_answer(text: str, request: SectionWriterRequest) -> str | None:
    """Return the first anchored-task answer value stated as a result in `text`.

    A number merely occurring in the text (e.g. restating "4x = 36") is not
    enough; the text must assert the value as a result via one of the narrow
    `_RESULT_TEMPLATES` constructions.
    """
    for task in request.task_summaries:
        for answer in _task_answer_values(task):
            for template in _RESULT_TEMPLATES:
                pattern = template.format(value=re.escape(answer))
                if re.search(pattern, text, flags=re.IGNORECASE):
                    return answer
    return None


def _check_learner_text(
    node: WrittenNode,
    request: SectionWriterRequest,
    item: CompositionItem,
    *,
    node_index: int,
    accept_soft_issues: bool,
    warnings: list[tuple[str, str]],
) -> None:
    node_path = f"nodes[{node_index}]"
    values = _node_text_values(node)
    required = _required_node_texts(node)
    if isinstance(node, WrittenTable):
        if not node.display.headers or not node.display.rows:
            raise _composition_error(
                "tables require headers and at least one row",
                item,
                code="table_missing_headers_or_rows",
                path=f"{node_path}.table",
            )
        width = len(node.display.headers)
        if any(len(row) != width for row in node.display.rows):
            raise _composition_error(
                "table rows must match the header width",
                item,
                code="table_row_width_mismatch",
                path=f"{node_path}.table.rows",
            )
    for text in required:
        if not text.strip():
            raise _composition_error(
                "learner-facing content must not be blank",
                item,
                code="blank_text",
                path=f"{node_path}.text",
            )
    all_inputs = _approved_numbers(request)
    identifiers = _internal_identifiers(request)
    for value in values:
        if not value.strip() and value:
            raise _composition_error(
                "learner-facing content must not be blank",
                item,
                code="blank_text",
                path=f"{node_path}.text",
            )
        if _INTERNAL_TERMS.search(value) or _PLACEHOLDER.search(value):
            raise _composition_error(
                "learner-facing content leaks planning text or a placeholder",
                item,
                code="metadata_leaked",
                path=f"{node_path}.text",
            )
        leaked_answer = _leaked_task_answer(value, request)
        if leaked_answer is not None:
            code, path = "task_answer_leaked", f"{node_path}.text"
            if accept_soft_issues:
                if (code, path) not in warnings:
                    warnings.append((code, path))
            else:
                raise _composition_error(
                    "learner-facing content states the result of an anchored task "
                    f"({leaked_answer!r}) instead of leaving it for the learner to solve",
                    item,
                    code=code,
                    path=path,
                )
        for identifier in identifiers:
            if re.search(rf"(?<!\w){re.escape(identifier)}(?!\w)", value, flags=re.IGNORECASE):
                raise _composition_error(
                    "learner-facing content leaks an internal identifier",
                    item,
                    code="internal_id_leaked",
                    path=f"{node_path}.text",
                )
        for number in _inline_numeric_values(value):
            if number not in all_inputs:
                code, path = "unsupported_number", f"{node_path}.text"
                if accept_soft_issues:
                    if (code, path) not in warnings:
                        warnings.append((code, path))
                else:
                        raise _composition_error(
                            f"learner-facing content contains unsupported numeric fact "
                            f"{number!r}",
                        item,
                        code=code,
                        path=path,
                    )


def _record_shape_advisories(
    *,
    nodes: Sequence[WrittenNode],
    items: Sequence[CompositionItem],
    warnings: list[tuple[str, str]],
) -> None:
    """Record writer targets without changing the accepted node payload.

    These checks deliberately inspect the full provider output.  They never
    trim text, cap equation terms, or collapse comparison cards.
    """
    key_idea_count = 0
    explanation_present = any(item.semantic_role == "explanation" for item in items)
    heading_present = False
    prose_words = 0
    for node_index, node in enumerate(nodes):
        node_path = f"nodes[{node_index}]"
        display = node.display
        if isinstance(node, WrittenParagraph):
            prose_words += _word_count(display.text)
            if _word_count(display.text) > 60:
                _shape_warning(
                    warnings,
                    "length_over_target",
                    f"{node_path}.text/{_word_count(display.text)}/60",
                )
        elif isinstance(node, WrittenHeading):
            heading_present = True
        elif isinstance(node, WrittenList):
            for item_index, value in enumerate(display.items):
                if _word_count(value) > 30:
                    _shape_warning(
                        warnings,
                        "length_over_target",
                        f"{node_path}.items[{item_index}]/{_word_count(value)}/30",
                    )
        elif isinstance(node, WrittenTable):
            for row_index, row in enumerate((display.headers, *display.rows)):
                for cell_index, value in enumerate(row):
                    if _word_count(value) > 12:
                        _shape_warning(
                            warnings,
                            "length_over_target",
                            f"{node_path}.table[{row_index}][{cell_index}]/{_word_count(value)}/12",
                        )
        elif isinstance(node, WrittenCallout):
            if display.variant == "key_idea":
                key_idea_count += 1
                if display.body is not None and _word_count(display.body) > 25:
                    _shape_warning(
                        warnings,
                        "length_over_target",
                        f"{node_path}.body/{_word_count(display.body)}/25",
                    )
            elif display.variant == "note":
                if display.body is not None and _word_count(display.body) > 50:
                    _shape_warning(
                        warnings,
                        "length_over_target",
                        f"{node_path}.body/{_word_count(display.body)}/50",
                    )
            elif display.variant == "misconception":
                for field_name, value, target in (
                    ("belief", display.belief, 30),
                    ("evidence", display.evidence, 45),
                    ("conclusion", display.conclusion, 30),
                ):
                    if value is not None and _word_count(value) > target:
                        _shape_warning(
                            warnings,
                            "length_over_target",
                            f"{node_path}.{field_name}/{_word_count(value)}/{target}",
                        )
        elif isinstance(node, WrittenEquation):
            if len(display.inputs) > 4:
                _shape_warning(
                    warnings,
                    "length_over_target",
                    f"{node_path}.inputs/{len(display.inputs)}/4",
                )
            if len(display.outputs) > 3:
                _shape_warning(
                    warnings,
                    "length_over_target",
                    f"{node_path}.outputs/{len(display.outputs)}/3",
                )
        elif isinstance(node, WrittenCompare) and len(display.items) > 3:
            _shape_warning(
                warnings,
                "length_over_target",
                f"{node_path}.items/{len(display.items)}/3",
            )

    if explanation_present and key_idea_count != 1:
        _shape_warning(warnings, "shape_missing", "section/key_idea")
    if prose_words > 120 and not heading_present:
        _shape_warning(warnings, "shape_missing", "section/subheading")


#: ``(issue_code, safe_path, short_message)``. Messages are fixed validator text
#: or pydantic error types, never learner or model text.
NodeIssue = tuple[str, str, str]

_WRITTEN_NODE_ADAPTER: TypeAdapter[Any] = TypeAdapter(WrittenNode)


@dataclass(frozen=True)
class NodeValidation:
    """Outcome for one expected ordinary node position."""

    index: int
    item: CompositionItem
    node: SharedLessonNode | None = None
    written: WrittenNode | None = None
    issues: tuple[NodeIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class DraftValidation:
    """Every problem found in one raw writer draft, per node position.

    ``section_issues`` are problems no single node owns (unparseable root, wrong
    node count); when present ``nodes`` is empty. Otherwise ``nodes`` holds one
    entry per expected ordinary node, in composition order.
    """

    expected: tuple[CompositionItem, ...]
    nodes: tuple[NodeValidation, ...] = ()
    section_issues: tuple[NodeIssue, ...] = ()
    warnings: tuple[tuple[str, str], ...] = ()
    #: The draft's raw ``nodes`` list when it had one (else ``None``).
    raw_nodes: tuple[Any, ...] | None = None

    @property
    def ok(self) -> bool:
        return not self.section_issues and all(node.ok for node in self.nodes)

    @property
    def broken_node_ids(self) -> tuple[str, ...]:
        return tuple(node.item.id for node in self.nodes if not node.ok)

    @property
    def kept_node_ids(self) -> tuple[str, ...]:
        return tuple(node.item.id for node in self.nodes if node.ok)

    @property
    def repair_mode(self) -> Literal["patch", "full"]:
        """``patch`` only when every problem belongs to a specific node."""
        if self.section_issues or self.raw_nodes is None or not self.broken_node_ids:
            return "full"
        return "patch"

    def to_error(self) -> SectionWriteValidationError:
        errors: list[str] = []
        issues: list[tuple[str, str]] = []
        for code, path, message in self.section_issues:
            errors.append(f"{path or 'draft'}: {message}")
            issues.append((code, path))
        for node in self.nodes:
            for code, path, message in node.issues:
                errors.append(f"{path} ({node.item.id}): {message}")
                issues.append((code, path))
        if not self.section_issues:
            affected: tuple[str, ...] = self.broken_node_ids
        elif any(code == "node_count_mismatch" for code, _path, _message in self.section_issues):
            affected = tuple(item.id for item in self.expected)
        else:
            affected = ()
        return SectionWriteValidationError(errors, affected_node_ids=affected, issues=issues)


def draft_as_json(draft: Any) -> Any:
    """Return a writer reply as plain JSON-shaped data (models are dumped)."""
    if isinstance(draft, BaseModel):
        return draft.model_dump(mode="json")
    return draft


def _node_schema_issues(raw: Any, index: int) -> tuple[WrittenNode | None, list[NodeIssue]]:
    node_path = f"nodes[{index}]"
    try:
        return _WRITTEN_NODE_ADAPTER.validate_python(raw), []
    except ValidationError as exc:
        summary = summarize_output_failure(exc)
        pairs = summary.issues if summary is not None and summary.issues else (("", "invalid"),)
        return None, [
            (
                "writer_draft_schema_invalid",
                f"{node_path}.{path}" if path else node_path,
                error_type,
            )
            for path, error_type in pairs
        ]


def _check_node_against_item(
    written: WrittenNode,
    request: SectionWriterRequest,
    expected_item: CompositionItem,
    *,
    node_index: int,
    accept_soft_issues: bool,
    warnings: list[tuple[str, str]],
) -> tuple[WrittenNode, SharedLessonNode]:
    """Check one parsed node against its composed slot; raises on the first problem."""
    node_path = f"nodes[{node_index}]"
    if isinstance(written, WrittenFigure) and written.display.asset_id is not None:
        # The asset is code-owned (media binds it). A model-invented asset_id
        # would make the figure look bound with empty alt and block media.
        written = written.model_copy(
            update={"display": written.display.model_copy(update={"asset_id": None})}
        )
    if written.id != expected_item.id:
        raise _composition_error(
            "writer changed, omitted, or reordered a node ID",
            expected_item,
            code="node_id_mismatch",
            path=f"{node_path}.id",
        )
    if written.kind != expected_item.kind:
        raise _composition_error(
            "writer changed a composed node kind",
            expected_item,
            code="node_kind_mismatch",
            path=f"{node_path}.kind",
        )
    if written.teaching_block_id != expected_item.teaching_block_id:
        raise _composition_error(
            "writer changed teaching block ownership",
            expected_item,
            code="node_block_mismatch",
            path=f"{node_path}.teaching_block_id",
        )
    _check_learner_text(
        written,
        request,
        expected_item,
        node_index=node_index,
        accept_soft_issues=accept_soft_issues,
        warnings=warnings,
    )
    payload = written.model_dump(mode="json")
    if isinstance(written, WrittenFigure):
        # Alt text is pending until media binds the ready result.
        payload["accessibility"] = {"alt_text": ""}
    try:
        return written, shared_lesson_node_adapter.validate_python(payload)
    except ValidationError as exc:
        raise _composition_error(
            "writer node failed the shared document schema",
            expected_item,
            code="node_shape_mismatch",
            path=node_path,
        ) from exc


def validate_draft_nodes(
    *,
    request: SectionWriterRequest,
    draft: Any,
    accept_soft_issues: bool = False,
) -> DraftValidation:
    """Validate a raw writer draft and report every broken node, not just the first.

    The draft is plain parsed JSON (a ``SectionWriterDraft`` is also accepted).
    Each expected ordinary node is checked independently with the same closed
    node schema, identity, learner-text and shared-document checks the section
    contract has always applied.
    """
    expected = tuple(item for item in request.composition_plan.items if item.kind != "task_anchor")
    data = draft_as_json(draft)
    if not isinstance(data, Mapping):
        return DraftValidation(
            expected=expected,
            section_issues=(
                ("writer_draft_schema_invalid", "", "writer output must be a JSON object"),
            ),
        )
    raw_nodes = data.get("nodes")
    if not isinstance(raw_nodes, (list, tuple)):
        return DraftValidation(
            expected=expected,
            section_issues=(
                ("writer_draft_schema_invalid", "", "writer output needs a `nodes` list"),
            ),
        )
    raw_nodes = tuple(raw_nodes)
    if set(data) - {"nodes"}:
        return DraftValidation(
            expected=expected,
            section_issues=(
                ("writer_draft_schema_invalid", "", "writer output must contain only `nodes`"),
            ),
            raw_nodes=raw_nodes,
        )

    parsed = [_node_schema_issues(raw, index) for index, raw in enumerate(raw_nodes)]
    if len(raw_nodes) != len(expected):
        schema_issues = tuple(issue for _written, found in parsed for issue in found)
        return DraftValidation(
            expected=expected,
            section_issues=schema_issues
            or (
                (
                    "node_count_mismatch",
                    "nodes",
                    f"writer must return exactly {len(expected)} ordinary nodes",
                ),
            ),
            raw_nodes=raw_nodes,
        )

    warnings: list[tuple[str, str]] = []
    results: list[NodeValidation] = []
    for node_index, (expected_item, (written, schema_issues)) in enumerate(
        zip(expected, parsed, strict=True)
    ):
        if written is None:
            results.append(NodeValidation(node_index, expected_item, issues=tuple(schema_issues)))
            continue
        try:
            checked, node = _check_node_against_item(
                written,
                request,
                expected_item,
                node_index=node_index,
                accept_soft_issues=accept_soft_issues,
                warnings=warnings,
            )
        except SectionWriteValidationError as exc:
            code, path = exc.issues[0]
            results.append(
                NodeValidation(
                    node_index,
                    expected_item,
                    written=written,
                    issues=((code, path, exc.errors[0]),),
                )
            )
            continue
        results.append(NodeValidation(node_index, expected_item, node=node, written=checked))

    if all(result.ok for result in results):
        _record_shape_advisories(
            nodes=[result.written for result in results if result.written is not None],
            items=expected,
            warnings=warnings,
        )
    return DraftValidation(
        expected=expected,
        nodes=tuple(results),
        warnings=tuple(warnings),
        raw_nodes=raw_nodes,
    )


def _build_section(
    request: SectionWriterRequest,
    validation: DraftValidation,
    *,
    repair_modes: tuple[Literal["patch", "full"], ...] = (),
) -> SectionWriteResult:
    """Insert immutable TaskAnchors by code around the validated ordinary nodes."""
    node_by_id = {result.item.id: result.node for result in validation.nodes}
    final_nodes: list[SharedLessonNode] = []
    for item_index, item in enumerate(request.composition_plan.items):
        if item.kind == "task_anchor":
            task = next(
                summary
                for summary in request.task_summaries
                if summary.task_spec_id == item.task_spec_id
            )
            if task.teaching_block_id != item.teaching_block_id:
                raise _composition_error(
                    "TaskAnchor ownership differs from its finalized task",
                    item,
                    code="task_anchor_ownership_mismatch",
                    path=f"composition_plan.items[{item_index}].teaching_block_id",
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
        warnings=validation.warnings,
        repair_modes=repair_modes,
    )


def validate_and_build_section(
    *,
    request: SectionWriterRequest,
    draft: SectionWriterDraft | Any,
    accept_soft_issues: bool = False,
) -> SectionWriteResult:
    """Validate exact composed shape, then insert immutable TaskAnchors by code.

    Shape findings are recorded as advisory warnings on every attempt and
    never trigger repair. Legacy soft findings in
    ``SOFT_SECTION_WRITE_ISSUE_CODES`` are recorded only when
    ``accept_soft_issues=True`` on the final bounded attempt. All other
    validation errors still fail closed; the raised error lists every broken
    node (see ``validate_draft_nodes``).
    """
    validation = validate_draft_nodes(
        request=request, draft=draft, accept_soft_issues=accept_soft_issues
    )
    if not validation.ok:
        raise validation.to_error()
    return _build_section(request, validation)


def ordinary_nodes_as_draft(nodes: Sequence[SharedLessonNode]) -> SectionWriterDraft:
    """Re-express persisted ordinary nodes as a writer draft.

    Figures keep no writer-authored accessibility (alt is pending until media
    binds), so it is dropped here instead of failing the closed writer schema.
    """
    payloads: list[dict[str, Any]] = []
    for node in nodes:
        if node.kind == "task_anchor":
            continue
        payload = node.model_dump(mode="json")
        if node.kind == "figure":
            payload.pop("accessibility", None)
        payloads.append(payload)
    return SectionWriterDraft.model_validate({"nodes": payloads})


def _request_payload(
    request: SectionWriterRequest,
    *,
    repair_scope: str,
    errors: Sequence[str],
    affected_node_ids: Sequence[str] = (),
    repair_mode: Literal["patch", "full"] | None = None,
    previous_draft: dict[str, Any] | None = None,
    keep_node_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build the writer user prompt.

    Without ``repair_mode`` the repair block keeps its legacy shape (used by
    boundary repair). With it, the block carries the previous draft:
    ``patch`` asks for only ``affected_node_ids`` (= the nodes to repair) and
    lists the read-only ``keep_node_ids``; ``full`` asks for the whole draft.
    """
    repair: dict[str, Any] | None = None
    if errors:
        repair = {
            "scope": repair_scope,
            "issues": list(errors),
            "affected_node_ids": list(affected_node_ids),
        }
        if repair_mode is not None:
            repair = {"mode": repair_mode, **repair, "previous_draft": previous_draft}
            if repair_mode == "patch":
                repair["keep_node_ids"] = list(keep_node_ids)
                repair["repair_node_ids"] = list(affected_node_ids)
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
                    "visual": (
                        block.visual.model_dump(mode="json")
                        if block.visual is not None
                        else None
                    ),
                }
                for block in request.section.blocks
            ],
        },
        "composition_plan": [
            item.model_dump(mode="json") for item in request.composition_plan.items
        ],
        # Code-reserved key-idea slot: one `key_idea` callout of at most 25
        # words, first in the section. Advisory; never repaired.
        "key_idea_slot_node_id": next(
            (
                item.id
                for item in request.composition_plan.items
                if item.kind == "callout" and item.id.startswith(KEY_IDEA_SLOT_PREFIX)
            ),
            None,
        ),
        "shaping_targets": {
            "paragraph_words_max": 60,
            "key_idea_words_max": 25,
            "note_words_max": 50,
            "misconception_words_max": {
                "belief": 30,
                "evidence": 45,
                "conclusion": 30,
            },
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
        "sources": [source.model_dump(mode="json") for source in request.sources],
        # Only the visible task/prompt/purpose context is ordinary input.
        # `expected_evidence` names the worked answer and evaluation names
        # the exact accepted value(s); neither is learner-facing text, so
        # both are kept out of ordinary context. `expected_evidence` is
        # still supplied, but quarantined under an explicit "do not reveal"
        # key so the provider cannot mistake it for prose to include, and
        # the raw `evaluation` shape is never sent at all.
        "task_summaries": [
            {
                "task_spec_id": task.task_spec_id,
                "teaching_block_id": task.teaching_block_id,
                "action": task.action,
                "purpose": task.purpose,
                "prompt": task.prompt,
            }
            for task in request.task_summaries
        ],
        "hidden_answer_context_do_not_reveal": [
            {"task_spec_id": task.task_spec_id, "expected_evidence": task.expected_evidence}
            for task in request.task_summaries
        ],
        "repair": repair,
    }


def _inline_json_schema_refs(schema: dict[str, Any]) -> dict[str, Any]:
    defs = schema.get("$defs", {})

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].rsplit("/", 1)[-1]])
            return {
                key: walk(value)
                for key, value in node.items()
                if key not in {"$defs", "discriminator"}
            }
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(schema)  # type: ignore[no-any-return]


class _RawSectionDraft(BaseModel):
    """Provider output type: shows the model the closed draft schema, validates nothing.

    Our own validation runs per node (``validate_draft_nodes``) so a reply with
    one bad node is kept and patched instead of being discarded wholesale. Only
    a reply that is not a JSON object still fails here.
    """

    model_config = ConfigDict(extra="allow")

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema: Any, handler: Any) -> dict[str, Any]:
        return _inline_json_schema_refs(SectionWriterDraft.model_json_schema(mode="validation"))


async def _default_provider(payload: dict[str, Any]) -> Any:
    from core.llm.runner import RetryPolicy

    from core.prompts import effective_prompt_text
    from infra.authoring.structured_provider import run_structured_agent
    from infra.execution.timeouts import V3_TIMEOUTS

    reply = await run_structured_agent(
        node_name="shared_section_writer",
        trace_id=None,
        generation_id=None,
        system_prompt=effective_prompt_text("shared-section-writer"),
        user_prompt=json.dumps(payload, sort_keys=True),
        output_type=_RawSectionDraft,
        repair_attempts=0,
        retries={"output": 0},
        retry_policy=RetryPolicy(
            max_attempts=1,
            call_timeout_seconds=float(V3_TIMEOUTS["section_writer"]),
        ),
    )
    # The raw parsed JSON, never a validated model: the caller keeps it when a
    # node is wrong so repair can patch just that node.
    return draft_as_json(reply)


_NODE_PATH_INDEX = re.compile(r"^nodes\[(\d+)\]")


def _provider_output_failure_as_validation_error(
    exc: BaseException, request: SectionWriterRequest
) -> SectionWriteValidationError | None:
    """Turn a provider-side schema/empty-reply failure into a repairable error.

    The structured provider validates the reply itself and raises
    ``UnexpectedModelBehavior`` before ``validate_and_build_section`` sees it.
    Returns ``None`` for anything that is not an output failure (transport
    errors, timeouts), which must keep propagating. Error strings carry only
    ``loc``-built paths and pydantic error types, never model output.
    """
    summary = summarize_output_failure(exc)
    if summary is None:
        return None
    if not summary.issues:
        return SectionWriteValidationError(
            [
                "your previous reply was empty or was not a JSON object matching the "
                "closed node schema; return the complete JSON draft"
            ],
            issues=(("writer_draft_schema_invalid", ""),),
        )
    expected = [item for item in request.composition_plan.items if item.kind != "task_anchor"]
    affected: list[str] = []
    for path, _error_type in summary.issues:
        match = _NODE_PATH_INDEX.match(path)
        if match is not None and int(match.group(1)) < len(expected):
            node_id = expected[int(match.group(1))].id
            if node_id not in affected:
                affected.append(node_id)
    return SectionWriteValidationError(
        [f"{path or 'draft'}: {error_type}" for path, error_type in summary.issues],
        affected_node_ids=affected,
        issues=tuple(("writer_draft_schema_invalid", path) for path, _kind in summary.issues),
    )


def _merge_node_patch(validation: DraftValidation, reply: Any) -> dict[str, Any]:
    """Return the previous draft with each repaired node swapped for its patch.

    Only nodes whose id was requested are taken from the reply (first one wins);
    anything else in the reply is ignored. Every node that was not requested
    stays exactly as the previous draft had it, and positions never move.
    """
    repair_ids = set(validation.broken_node_ids)
    data = draft_as_json(reply)
    patched: dict[str, Any] = {}
    if isinstance(data, Mapping) and isinstance(data.get("nodes"), (list, tuple)):
        for node in data["nodes"]:
            node_id = node.get("id") if isinstance(node, Mapping) else None
            if isinstance(node_id, str) and node_id in repair_ids and node_id not in patched:
                patched[node_id] = node
    previous = validation.raw_nodes or ()
    return {
        "nodes": [patched.get(result.item.id, previous[result.index]) for result in validation.nodes]
    }


async def write_section(
    *, request: SectionWriterRequest, provider: Provider | None = None
) -> SectionWriteResult:
    """Write one section with one initial, one section, and one targeted call max.

    Shape findings are accepted on the initial response and returned as
    advisory warnings. Only hard identity, schema, leakage, and task
    correctness issues enter the bounded repair loop. The provider returns the
    raw parsed JSON and every node is validated here, so one reply reports all
    broken nodes. A repair call then either patches exactly those nodes (every
    problem is node-level) or rewrites the full draft (unparseable reply, wrong
    node count); both carry the previous draft. A patch is merged into the
    previous draft by id and the whole section is re-validated. A provider reply
    that is empty/non-actionable becomes a ``writer_draft_schema_invalid`` error
    and is repaired in full mode; other provider errors propagate unchanged.
    """
    dispatch = provider or _default_provider
    repair_scopes = ("initial", "section", "targeted")
    issues: tuple[str, ...] = ()
    affected_node_ids: tuple[str, ...] = ()
    repair_kwargs: dict[str, Any] = {}
    prior_validation: DraftValidation | None = None
    modes: list[Literal["patch", "full"]] = []
    last_error: SectionWriteValidationError | None = None
    for attempt, scope in enumerate(repair_scopes):
        final_attempt = attempt == len(repair_scopes) - 1
        reply_validation: DraftValidation | None = None
        reply_draft: Any = None
        try:
            try:
                raw = await dispatch(
                    _request_payload(
                        request,
                        repair_scope=scope,
                        errors=issues,
                        affected_node_ids=affected_node_ids,
                        **repair_kwargs,
                    )
                )
            except Exception as provider_exc:
                converted = _provider_output_failure_as_validation_error(provider_exc, request)
                if converted is None:
                    raise
                raise converted from provider_exc
            if repair_kwargs.get("repair_mode") == "patch" and prior_validation is not None:
                reply_draft = _merge_node_patch(prior_validation, raw)
            else:
                reply_draft = draft_as_json(raw)
            reply_validation = validate_draft_nodes(
                request=request, draft=reply_draft, accept_soft_issues=final_attempt
            )
            if not reply_validation.ok:
                raise reply_validation.to_error()
            return _build_section(request, reply_validation, repair_modes=tuple(modes))
        except SectionWriteValidationError as exc:
            last_error = exc
            if final_attempt:
                exc.repair_modes = tuple(modes)
                raise
            issues = exc.errors
            affected_node_ids = exc.affected_node_ids
            if reply_validation is not None:
                prior_validation = reply_validation
            elif prior_validation is not None:
                # An empty/unusable reply must not discard the last usable
                # draft: keep repairing from it, with its own issues.
                issues = (*prior_validation.to_error().errors, *exc.errors)
                if prior_validation.raw_nodes is not None:
                    reply_draft = {"nodes": list(prior_validation.raw_nodes)}
            if prior_validation is not None and prior_validation.repair_mode == "patch":
                modes.append("patch")
                affected_node_ids = prior_validation.broken_node_ids
                repair_kwargs = {
                    "repair_mode": "patch",
                    "previous_draft": {"nodes": list(prior_validation.raw_nodes or ())},
                    "keep_node_ids": prior_validation.kept_node_ids,
                }
            else:
                modes.append("full")
                repair_kwargs = {
                    "repair_mode": "full",
                    "previous_draft": reply_draft if isinstance(reply_draft, Mapping) else None,
                }
    if last_error is None:
        raise AssertionError("bounded writer loop exhausted unexpectedly")
    raise last_error


__all__ = [
    "SECTION_WRITE_ISSUE_CODES",
    "SOFT_SECTION_WRITE_ISSUE_CODES",
    "ADVISORY_SHAPE_ISSUE_CODES",
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
    "ordinary_nodes_as_draft",
    "validate_and_build_section",
    "validate_draft_nodes",
    "write_section",
]
