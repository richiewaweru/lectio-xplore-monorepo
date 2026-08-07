"""Typed page-object content models and writer result types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from v3_blueprint.planning.models import PlannedBlock


class WriterError(ValueError):
    pass


@dataclass(frozen=True)
class WriterContext:
    """Immutable writer context. No alternative objects. No lesson prose for questions."""

    planned: PlannedBlock
    terminology: tuple[str, ...] = ()
    neighbour_summaries: tuple[str, ...] = ()
    item_records: tuple[dict[str, Any], ...] = ()
    lesson_context: dict[str, Any] | None = None
    generation_id: str | None = None
    use_llm: bool = False
    section_id: str | None = None


@dataclass
class WriterOutcome:
    """Runtime wrapper for writer content. Object/intent live on ResolvedBlockPlan."""

    block_id: str
    content: dict[str, Any]
    status: str = "ready"
    request_id: str | None = None
    answer_entries: tuple[dict[str, Any], ...] = ()


# Backward-compatible alias; prefer WriterOutcome.
WriterResult = WriterOutcome


class _ForbidModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProseContent(_ForbidModel):
    paragraphs: list[str] = Field(min_length=1)


class ListItem(_ForbidModel):
    text: str


class ListContent(_ForbidModel):
    style: Literal["ordered", "unordered", "steps", "glossary"]
    items: list[ListItem] = Field(min_length=1)
    lead_in: str | None = None


class TableColumn(_ForbidModel):
    id: str = Field(min_length=1)
    label: str


class TableRow(_ForbidModel):
    cells: dict[str, str]


class TableContent(_ForbidModel):
    columns: list[TableColumn] = Field(min_length=1)
    rows: list[TableRow] = Field(min_length=1)
    caption: str | None = None
    presentation: Literal["standard", "comparison", "timeline"] | None = None


class FigureAsset(_ForbidModel):
    kind: Literal["image", "svg"] | None = None
    status: Literal["ready", "pending", "failed"] | None = None
    request_id: str | None = None
    src: str | None = None
    svg: str | None = None


class FigureContent(_ForbidModel):
    asset: FigureAsset
    alt_text: str = Field(min_length=1)
    caption: str | None = None
    width: Literal["main", "span"] | None = None


class AsideContent(_ForbidModel):
    body: str
    label: str | None = None


class WorkedExampleStep(_ForbidModel):
    text: str


class WorkedExampleContent(_ForbidModel):
    problem: str
    steps: list[WorkedExampleStep] = Field(min_length=1)
    answer: str
    title: str | None = None
    check: str | None = None


class QuestionsItem(_ForbidModel):
    id: str = Field(min_length=1)
    prompt: str
    marks: float | int | None = None
    answer_lines: int | None = Field(default=None, ge=0)


class QuestionsContent(_ForbidModel):
    items: list[QuestionsItem] = Field(min_length=1)
    instructions: str | None = None


class ChoicesOption(_ForbidModel):
    letter: str = Field(min_length=1)
    text: str


class ChoicesContent(_ForbidModel):
    stem: str
    options: list[ChoicesOption] = Field(min_length=2)
    marks: float | int | None = None


class AnswerEntry(_ForbidModel):
    question_id: str = Field(min_length=1)
    answer: str
    alternatives: list[str] | None = None
    working: str | None = None
    rubric: str | None = None


class AssessmentBundle(_ForbidModel):
    """Student assessment blocks plus separated answer entries."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    student_blocks: list[Any]
    answer_entries: list[AnswerEntry]


GENERATED_FORM_IDS: tuple[str, ...] = (
    "prose",
    "list",
    "table",
    "figure",
    "aside",
    "worked-example",
    "questions",
    "choices",
)

FORM_OUTPUTS: dict[str, type[BaseModel]] = {
    "prose": ProseContent,
    "list": ListContent,
    "table": TableContent,
    "figure": FigureContent,
    "aside": AsideContent,
    "worked-example": WorkedExampleContent,
    "questions": QuestionsContent,
    "choices": ChoicesContent,
}

