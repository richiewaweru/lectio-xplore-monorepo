# -- AUTO-GENERATED - DO NOT EDIT -------------------------------------------
# Source: @richiewaweru/lectio src/lib/schema/types.ts
# Generated from: contracts/section-content-schema.json
# Generator: scripts/generate-python-types.ts
# Run `npm run export-contracts` in the Lectio repo to regenerate.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class SectionHeaderContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    subtitle: str | None = None
    subject: str
    section_number: str | None = None
    grade_band: GradeBand
    objectives: list[str] | None = None
    level_pills: list[LevelPill] | None = None
class LevelPill(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    variant: Literal["all", "warm", "medium", "cold"]
class HookHeroContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    headline: str
    body: str
    anchor: str
    type: HookType | None = None
    image: HookImage | None = None
    svg_content: str | None = None
    quote_attribution: str | None = None
    question_options: list[str] | None = None
    data_point: HookHeroContentDataPoint | None = None
class HookImage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    alt: str
class ExplanationContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str
    emphasis: list[str]
    callouts: list[ExplanationCallout] | None = None
class ExplanationCallout(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["remember", "insight", "sidenote", "warning", "exam-tip"]
    text: str
class PracticeContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    problems: list[PracticeProblem]
    hints_visible_default: bool | None = None
    solutions_available: bool | None = None
    label: str | None = None
class PracticeProblem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    difficulty: Difficulty
    problem_type: Literal["structured", "open"] | None = None
    question: str
    hints: list[PracticeHint]
    solution: PracticeSolution | None = None
    writein_lines: float | None = None
    self_assess: bool | None = None
    context: str | None = None
    diagram: DiagramContent | None = None
class PracticeHint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    level: HintLevel
    text: str
class PracticeSolution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approach: str
    answer: str
    worked: str | None = None
class DiagramContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_id: str | None = None
    svg_content: str | None = None
    image_url: str | None = None
    caption: str
    zoom_label: str | None = None
    alt_text: str
    callouts: list[DiagramCallout] | None = None
    figure_number: float | None = None
    figure_ref: str | None = None
    description: str | None = None
    width: Literal["full", "half", "third"] | None = None
class DiagramCallout(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    x: float
    y: float
    label: str
    explanation: str
class WhatNextContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str
    next: str
    preview: str | None = None
    prerequisites: list[str] | None = None
class PrerequisiteContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str | None = None
    items: list[PrerequisiteItem]
class PrerequisiteItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    concept: str
    refresher: str | None = None
class DefinitionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    term: str
    formal: str
    plain: str
    etymology: str | None = None
    notation: str | None = None
    related_terms: list[str] | None = None
    symbol: str | None = None
    examples: list[str] | None = None
class DefinitionFamilyContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    family_title: str
    family_intro: str | None = None
    definitions: list[DefinitionContent]
class WorkedExampleContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    setup: str
    steps: list[WorkedStep]
    conclusion: str
    method_label: str | None = None
    alternative: WorkedExampleContent | None = None
    answer: str | None = None
    alternatives: list[str] | None = None
    diagram: DiagramContent | None = None
class WorkedStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    content: str
    note: str | None = None
    formula: str | None = None
    diagram_ref: str | None = None
class ProcessContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: str | None = None
    steps: list[ProcessStepItem]
    checklist_mode: bool | None = None
class ProcessStepItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    number: float
    action: str
    detail: str
    input: str | None = None
    output: str | None = None
    warning: str | None = None
class DiagramCompareContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    before_media_id: str | None = None
    before_svg: str | None = None
    after_media_id: str | None = None
    after_svg: str | None = None
    before_image_url: str | None = None
    after_image_url: str | None = None
    before_label: str
    after_label: str
    before_details: list[str] | None = None
    after_details: list[str] | None = None
    caption: str
    alt_text: str
class DiagramSeriesContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    diagrams: list[DiagramSeriesStep]
class DiagramSeriesStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step_label: str
    caption: str
    media_id: str | None = None
    svg_content: str | None = None
    image_url: str | None = None
class VideoEmbedContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_id: str
    caption: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    print_fallback: Literal["thumbnail", "qr-link", "hide"]
class ImageBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_id: str
    caption: str | None = None
    alt_text: str
    width: Literal["full", "half", "third"] | None = None
    alignment: Literal["left", "center", "right"] | None = None
class ComparisonGridContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: str | None = None
    columns: list[ComparisonColumn]
    rows: list[ComparisonRow]
    apply_prompt: str | None = None
class ComparisonColumn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    title: str
    summary: str
    badge: str | None = None
    detail: str | None = None
    highlight: bool | None = None
class ComparisonRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    criterion: str
    values: list[str | ComparisonRowValuesItem]
    takeaway: str | None = None
class TimelineContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: str | None = None
    events: list[TimelineEvent]
    closing_takeaway: str | None = None
class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    era: str | None = None
    year: str
    title: str
    summary: str
    impact: str | None = None
    tags: list[str] | None = None
class InsightStripContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cells: list[InsightCell]
class InsightCell(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    value: str
    note: str | None = None
    highlight: bool | None = None
class PitfallContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    misconception: str
    correction: str
    label: str | None = None
    example: str | None = None
    severity: Literal["minor", "major"] | None = None
    examples: list[str] | None = None
    why: str | None = None
class QuizContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    quiz_type: Literal["multiple-choice", "true-false"] | None = None
    options: list[QuizOption]
    feedback_correct: str
    feedback_incorrect: str
    show_explanations: bool | None = None
class QuizOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    correct: bool
    explanation: str
    diagnoses: str | None = None
class AnswerKeyContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str | None = None
    note: str | None = None
    entries: list[AnswerKeyEntry]
class AnswerKeyEntry(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question_number: float
    question: str
    correct_answer: str
    correct_key: str | None = None
    diagnostics: list[AnswerKeyDiagnostic] | None = None
class AnswerKeyDiagnostic(BaseModel):
    model_config = ConfigDict(extra='forbid')
    option_key: str | None = None
    option_text: str
    misconception_id: str
    misconception_label: str
class ReflectionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    type: ReflectionType
    space: float | None = None
    sentence_stem: str | None = None
    time_minutes: float | None = None
    pair_instruction: str | None = None
class GlossaryContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    terms: list[GlossaryTerm]
class GlossaryTerm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    term: str
    definition: str
    used_in: str | None = None
    pronunciation: str | None = None
    related: list[str] | None = None
class SimulationContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    spec: InteractionSpec
    html_content: str | None = None
    fallback_diagram: DiagramContent | None = None
    explanation: str | None = None
class InteractionSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: SimulationType
    goal: str
    anchor_content: dict[str, Any]
    context: InteractionContext
    dimensions: InteractionDimensions
    print_translation: Literal["static_midstate", "static_diagram", "hide"]
class InteractionContext(BaseModel):
    model_config = ConfigDict(extra='forbid')
    learner_level: str
    template_id: str
    color_mode: Literal["light", "dark"]
    accent_color: str
    surface_color: str
    font_mono: str
class InteractionDimensions(BaseModel):
    model_config = ConfigDict(extra='forbid')
    width: str
    height: float
    resizable: bool
class InterviewContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    audience: str
    follow_up: str | None = None
class CalloutBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    variant: CalloutVariant
    heading: str | None = None
    body: str
class SummaryBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    heading: str | None = None
    items: list[SummaryItem]
    closing: str | None = None
class SummaryItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
class StudentTextboxContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    lines: float | None = None
    label: str | None = None
class ShortAnswerContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    marks: float | None = None
    lines: float | None = None
    mark_scheme: str | None = None
class FillInBlankContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instruction: str | None = None
    segments: list[FillInBlankSegment]
    word_bank: list[str | FillInBlankContentWordBankItem] | None = None
class FillInBlankSegment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    is_blank: bool
    answer: str | None = None
class SectionDividerContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
class KeyFactContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fact: str
    formula: str | None = None
    context: str | None = None
    source: str | None = None
class HookHeroContentDataPoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str
    label: str
    source: str | None = None
class ComparisonRowValuesItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
class FillInBlankContentWordBankItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    word: str
class SectionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    section_id: str
    template_id: str
    card_id: str | None = None
    varies_on: str | None = None
    header: SectionHeaderContent | None = None
    hook: HookHeroContent | None = None
    explanation: ExplanationContent | None = None
    practice: PracticeContent | None = None
    what_next: WhatNextContent | None = None
    prerequisites: PrerequisiteContent | None = None
    definition: DefinitionContent | None = None
    definition_family: DefinitionFamilyContent | None = None
    worked_example: WorkedExampleContent | None = None
    worked_examples: list[WorkedExampleContent] | None = None
    process: ProcessContent | None = None
    diagram: DiagramContent | None = None
    diagram_compare: DiagramCompareContent | None = None
    diagram_series: DiagramSeriesContent | None = None
    video_embed: VideoEmbedContent | None = None
    image_block: ImageBlockContent | None = None
    comparison_grid: ComparisonGridContent | None = None
    timeline: TimelineContent | None = None
    insight_strip: InsightStripContent | None = None
    pitfall: PitfallContent | None = None
    pitfalls: list[PitfallContent] | None = None
    quiz: QuizContent | None = None
    answer_key: AnswerKeyContent | None = None
    reflection: ReflectionContent | None = None
    glossary: GlossaryContent | None = None
    simulation: SimulationContent | None = None
    interview: InterviewContent | None = None
    callout: CalloutBlockContent | None = None
    summary: SummaryBlockContent | None = None
    student_textbox: StudentTextboxContent | None = None
    short_answer: ShortAnswerContent | None = None
    fill_in_blank: FillInBlankContent | None = None
    divider: SectionDividerContent | None = None
    key_fact: KeyFactContent | None = None

CalloutVariant = Literal["info", "tip", "warning", "exam-tip", "remember"]
Difficulty = Literal["warm", "medium", "cold", "extension"]
GradeBand = Literal["primary", "secondary", "advanced"]
HintLevel = Literal[1, 2, 3]
HookType = Literal["prose", "quote", "question", "data-point"]
ReflectionType = Literal["open", "pair-share", "sentence-stem", "timed", "connect", "predict", "transfer"]
SimulationType = str

SectionHeaderContent.model_rebuild()
LevelPill.model_rebuild()
HookHeroContent.model_rebuild()
HookImage.model_rebuild()
ExplanationContent.model_rebuild()
ExplanationCallout.model_rebuild()
PracticeContent.model_rebuild()
PracticeProblem.model_rebuild()
PracticeHint.model_rebuild()
PracticeSolution.model_rebuild()
DiagramContent.model_rebuild()
DiagramCallout.model_rebuild()
WhatNextContent.model_rebuild()
PrerequisiteContent.model_rebuild()
PrerequisiteItem.model_rebuild()
DefinitionContent.model_rebuild()
DefinitionFamilyContent.model_rebuild()
WorkedExampleContent.model_rebuild()
WorkedStep.model_rebuild()
ProcessContent.model_rebuild()
ProcessStepItem.model_rebuild()
DiagramCompareContent.model_rebuild()
DiagramSeriesContent.model_rebuild()
DiagramSeriesStep.model_rebuild()
VideoEmbedContent.model_rebuild()
ImageBlockContent.model_rebuild()
ComparisonGridContent.model_rebuild()
ComparisonColumn.model_rebuild()
ComparisonRow.model_rebuild()
TimelineContent.model_rebuild()
TimelineEvent.model_rebuild()
InsightStripContent.model_rebuild()
InsightCell.model_rebuild()
PitfallContent.model_rebuild()
QuizContent.model_rebuild()
QuizOption.model_rebuild()
AnswerKeyContent.model_rebuild()
AnswerKeyEntry.model_rebuild()
AnswerKeyDiagnostic.model_rebuild()
ReflectionContent.model_rebuild()
GlossaryContent.model_rebuild()
GlossaryTerm.model_rebuild()
SimulationContent.model_rebuild()
InteractionSpec.model_rebuild()
InteractionContext.model_rebuild()
InteractionDimensions.model_rebuild()
InterviewContent.model_rebuild()
CalloutBlockContent.model_rebuild()
SummaryBlockContent.model_rebuild()
SummaryItem.model_rebuild()
StudentTextboxContent.model_rebuild()
ShortAnswerContent.model_rebuild()
FillInBlankContent.model_rebuild()
FillInBlankSegment.model_rebuild()
SectionDividerContent.model_rebuild()
KeyFactContent.model_rebuild()
HookHeroContentDataPoint.model_rebuild()
ComparisonRowValuesItem.model_rebuild()
FillInBlankContentWordBankItem.model_rebuild()
SectionContent.model_rebuild()
