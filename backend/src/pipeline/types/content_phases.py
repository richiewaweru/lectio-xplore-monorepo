from __future__ import annotations

from pydantic import BaseModel

from pipeline.types.section_content import (
    CalloutBlockContent,
    ComparisonGridContent,
    DefinitionContent,
    DefinitionFamilyContent,
    ExplanationContent,
    FillInBlankContent,
    GlossaryContent,
    HookHeroContent,
    InsightStripContent,
    InterviewContent,
    KeyFactContent,
    PitfallContent,
    PracticeContent,
    PrerequisiteContent,
    ProcessContent,
    QuizContent,
    ReflectionContent,
    SectionHeaderContent,
    SectionDividerContent,
    ShortAnswerContent,
    StudentTextboxContent,
    SummaryBlockContent,
    TimelineContent,
    WhatNextContent,
    WorkedExampleContent,
)


class CoreContent(BaseModel):
    section_id: str
    template_id: str
    header: SectionHeaderContent
    hook: HookHeroContent
    explanation: ExplanationContent


class PracticePhaseContent(BaseModel):
    practice: PracticeContent
    what_next: WhatNextContent
    pitfall: PitfallContent | None = None
    pitfalls: list[PitfallContent] | None = None
    prerequisites: PrerequisiteContent | None = None


class EnrichmentPhaseContent(BaseModel):
    callout: CalloutBlockContent | None = None
    summary: SummaryBlockContent | None = None
    student_textbox: StudentTextboxContent | None = None
    short_answer: ShortAnswerContent | None = None
    fill_in_blank: FillInBlankContent | None = None
    worked_example: WorkedExampleContent | None = None
    worked_examples: list[WorkedExampleContent] | None = None
    process: ProcessContent | None = None
    definition: DefinitionContent | None = None
    definition_family: DefinitionFamilyContent | None = None
    quiz: QuizContent | None = None
    reflection: ReflectionContent | None = None
    glossary: GlossaryContent | None = None
    comparison_grid: ComparisonGridContent | None = None
    timeline: TimelineContent | None = None
    insight_strip: InsightStripContent | None = None
    interview: InterviewContent | None = None
    divider: SectionDividerContent | None = None
    key_fact: KeyFactContent | None = None
