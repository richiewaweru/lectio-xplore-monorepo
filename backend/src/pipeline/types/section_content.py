# -- AUTO-GENERATED - DO NOT EDIT -------------------------------------------
# Source: @richiewaweru/lectio src/lib/schema/types.ts
# Generated from: contracts/section-content-schema.json
# Generator: scripts/generate-python-types.ts
# Run `npm run export-contracts` in the Lectio repo to regenerate.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict

class SectionHeaderContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    subtitle: Optional[str] = None
    subject: str
    section_number: Optional[str] = None
    grade_band: GradeBand
    objectives: Optional[list[str]] = None
    level_pills: Optional[list[LevelPill]] = None
class LevelPill(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    variant: Literal["all", "warm", "medium", "cold"]
class HookHeroContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    headline: str
    body: str
    anchor: str
    type: Optional[HookType] = None
    image: Optional[HookImage] = None
    svg_content: Optional[str] = None
    quote_attribution: Optional[str] = None
    question_options: Optional[list[str]] = None
    data_point: Optional[HookHeroContentDataPoint] = None
class HookImage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    alt: str
class ExplanationContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str
    emphasis: list[str]
    callouts: Optional[list[ExplanationCallout]] = None
class ExplanationCallout(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal["remember", "insight", "sidenote", "warning", "exam-tip"]
    text: str
class PracticeContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    problems: list[PracticeProblem]
    hints_visible_default: Optional[bool] = None
    solutions_available: Optional[bool] = None
    label: Optional[str] = None
class PracticeProblem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    difficulty: Difficulty
    problem_type: Optional[Literal["structured", "open"]] = None
    question: str
    hints: list[PracticeHint]
    solution: Optional[PracticeSolution] = None
    writein_lines: Optional[float] = None
    self_assess: Optional[bool] = None
    context: Optional[str] = None
    diagram: Optional[DiagramContent] = None
class PracticeHint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    level: HintLevel
    text: str
class PracticeSolution(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approach: str
    answer: str
    worked: Optional[str] = None
class WhatNextContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str
    next: str
    preview: Optional[str] = None
    prerequisites: Optional[list[str]] = None
class PrerequisiteContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: Optional[str] = None
    items: list[PrerequisiteItem]
class PrerequisiteItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    concept: str
    refresher: Optional[str] = None
class DefinitionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    term: str
    formal: str
    plain: str
    etymology: Optional[str] = None
    notation: Optional[str] = None
    related_terms: Optional[list[str]] = None
    symbol: Optional[str] = None
    examples: Optional[list[str]] = None
class DefinitionFamilyContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    family_title: str
    family_intro: Optional[str] = None
    definitions: list[DefinitionContent]
class WorkedExampleContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    setup: str
    steps: list[WorkedStep]
    conclusion: str
    method_label: Optional[str] = None
    alternative: Optional[WorkedExampleContent] = None
    answer: Optional[str] = None
    alternatives: Optional[list[str]] = None
    diagram: Optional[DiagramContent] = None
class WorkedStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    content: str
    note: Optional[str] = None
    formula: Optional[str] = None
    diagram_ref: Optional[str] = None
class ProcessContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: Optional[str] = None
    steps: list[ProcessStepItem]
    checklist_mode: Optional[bool] = None
class ProcessStepItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    number: float
    action: str
    detail: str
    input: Optional[str] = None
    output: Optional[str] = None
    warning: Optional[str] = None
class DiagramContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    svg_content: Optional[str] = None
    image_url: Optional[str] = None
    caption: str
    zoom_label: Optional[str] = None
    alt_text: str
    callouts: Optional[list[DiagramCallout]] = None
    figure_number: Optional[float] = None
class DiagramCallout(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    x: float
    y: float
    label: str
    explanation: str
class DiagramCompareContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    before_svg: Optional[str] = None
    after_svg: Optional[str] = None
    before_image_url: Optional[str] = None
    after_image_url: Optional[str] = None
    before_label: str
    after_label: str
    before_details: Optional[list[str]] = None
    after_details: Optional[list[str]] = None
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
    svg_content: Optional[str] = None
    image_url: Optional[str] = None
class VideoEmbedContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_id: str
    caption: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    print_fallback: Literal["thumbnail", "qr-link", "hide"]
class ImageBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    media_id: str
    caption: Optional[str] = None
    alt_text: str
    width: Optional[Literal["full", "half", "third"]] = None
    alignment: Optional[Literal["left", "center", "right"]] = None
class ComparisonGridContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: Optional[str] = None
    columns: list[ComparisonColumn]
    rows: list[ComparisonRow]
    apply_prompt: Optional[str] = None
class ComparisonColumn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    title: str
    summary: str
    badge: Optional[str] = None
    detail: Optional[str] = None
    highlight: Optional[bool] = None
class ComparisonRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    criterion: str
    values: list[str]
    takeaway: Optional[str] = None
class TimelineContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str
    intro: Optional[str] = None
    events: list[TimelineEvent]
    closing_takeaway: Optional[str] = None
class TimelineEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    era: Optional[str] = None
    year: str
    title: str
    summary: str
    impact: Optional[str] = None
    tags: Optional[list[str]] = None
class InsightStripContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    cells: list[InsightCell]
class InsightCell(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
    value: str
    note: Optional[str] = None
    highlight: Optional[bool] = None
class PitfallContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    misconception: str
    correction: str
    example: Optional[str] = None
    severity: Optional[Literal["minor", "major"]] = None
    examples: Optional[list[str]] = None
    why: Optional[str] = None
class QuizContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    quiz_type: Optional[Literal["multiple-choice", "true-false"]] = None
    options: list[QuizOption]
    feedback_correct: str
    feedback_incorrect: str
    show_explanations: Optional[bool] = None
class QuizOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    correct: bool
    explanation: str
class ReflectionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    type: ReflectionType
    space: Optional[float] = None
    sentence_stem: Optional[str] = None
    time_minutes: Optional[float] = None
    pair_instruction: Optional[str] = None
class GlossaryContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    terms: list[GlossaryTerm]
class GlossaryTerm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    term: str
    definition: str
    used_in: Optional[str] = None
    pronunciation: Optional[str] = None
    related: Optional[list[str]] = None
class SimulationContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    spec: InteractionSpec
    html_content: Optional[str] = None
    fallback_diagram: Optional[DiagramContent] = None
    explanation: Optional[str] = None
class InteractionSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: str
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
    follow_up: Optional[str] = None
class CalloutBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    variant: CalloutVariant
    heading: Optional[str] = None
    body: str
class SummaryBlockContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    heading: Optional[str] = None
    items: list[SummaryItem]
    closing: Optional[str] = None
class SummaryItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
class StudentTextboxContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str
    lines: Optional[float] = None
    label: Optional[str] = None
class ShortAnswerContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    marks: Optional[float] = None
    lines: Optional[float] = None
    mark_scheme: Optional[str] = None
class FillInBlankContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    instruction: Optional[str] = None
    segments: list[FillInBlankSegment]
    word_bank: Optional[list[str]] = None
class FillInBlankSegment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    is_blank: bool
    answer: Optional[str] = None
class SectionDividerContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    label: str
class KeyFactContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fact: str
    context: Optional[str] = None
    source: Optional[str] = None
class HookHeroContentDataPoint(BaseModel):
    model_config = ConfigDict(extra='forbid')
    value: str
    label: str
    source: Optional[str] = None
class SectionContent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    section_id: str
    template_id: str
    header: SectionHeaderContent
    hook: HookHeroContent
    explanation: ExplanationContent
    practice: PracticeContent
    what_next: WhatNextContent
    prerequisites: Optional[PrerequisiteContent] = None
    definition: Optional[DefinitionContent] = None
    definition_family: Optional[DefinitionFamilyContent] = None
    worked_example: Optional[WorkedExampleContent] = None
    worked_examples: Optional[list[WorkedExampleContent]] = None
    process: Optional[ProcessContent] = None
    diagram: Optional[DiagramContent] = None
    diagram_compare: Optional[DiagramCompareContent] = None
    diagram_series: Optional[DiagramSeriesContent] = None
    video_embed: Optional[VideoEmbedContent] = None
    image_block: Optional[ImageBlockContent] = None
    comparison_grid: Optional[ComparisonGridContent] = None
    timeline: Optional[TimelineContent] = None
    insight_strip: Optional[InsightStripContent] = None
    pitfall: Optional[PitfallContent] = None
    pitfalls: Optional[list[PitfallContent]] = None
    quiz: Optional[QuizContent] = None
    reflection: Optional[ReflectionContent] = None
    glossary: Optional[GlossaryContent] = None
    simulation: Optional[SimulationContent] = None
    interview: Optional[InterviewContent] = None
    callout: Optional[CalloutBlockContent] = None
    summary: Optional[SummaryBlockContent] = None
    student_textbox: Optional[StudentTextboxContent] = None
    short_answer: Optional[ShortAnswerContent] = None
    fill_in_blank: Optional[FillInBlankContent] = None
    divider: Optional[SectionDividerContent] = None
    key_fact: Optional[KeyFactContent] = None

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
WhatNextContent.model_rebuild()
PrerequisiteContent.model_rebuild()
PrerequisiteItem.model_rebuild()
DefinitionContent.model_rebuild()
DefinitionFamilyContent.model_rebuild()
WorkedExampleContent.model_rebuild()
WorkedStep.model_rebuild()
ProcessContent.model_rebuild()
ProcessStepItem.model_rebuild()
DiagramContent.model_rebuild()
DiagramCallout.model_rebuild()
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
SectionContent.model_rebuild()
