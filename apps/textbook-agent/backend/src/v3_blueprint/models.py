from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


LessonMode = Literal[
    "first_exposure",  # learner meets concept for the first time
    "consolidation",  # revisiting known content to deepen or connect
    "repair",  # targeting a known misconception or gap
    "retrieval",  # low-cue recall practice with minimal new explanation
    "transfer",  # applying understanding to an unfamiliar context
]
QuestionTemperature = Literal["warm", "medium", "cold", "transfer"]
ResourceType = Literal[
    "lesson",  # default full lesson (spec exists)
    "mini_booklet",  # full guided lesson with scaffolding (spec exists)
    "worksheet",  # practice resource; concept already taught (spec exists)
    "quiz",  # formal assessment (spec exists)
    "exit_ticket",  # short end-of-lesson check (spec exists)
    "practice_set",  # drill-style repetition (spec exists)
    "quick_explainer",  # focused concept explainer/reference card (spec exists)
]
VisualStyle = Literal["diagram_precision", "illustration"]
_VISUAL_STYLES = {"diagram_precision", "illustration"}


class BlueprintMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = "3.0"
    title: str
    subject: str


class LessonModePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_mode: LessonMode
    resource_type: ResourceType = "lesson"


class AnchorPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example: str = ""
    reuse_scope: str


class VoicePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    register_name: str = Field(alias="register", serialization_alias="register")
    tone: str | None = None
    notation: str | None = None
    variant_label: str = "Core"


class ComponentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: str
    content_intent: str


class SectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    role: str
    visual_required: bool = False
    card_id: str | None = None
    transition_note: str | None = None
    components: list[ComponentPlan] = Field(default_factory=list, min_length=1)


class CardMisconceptionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str


class CardRubricPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    card_id: str
    objective: str
    misconceptions: list[CardMisconceptionPlan] = Field(default_factory=list)


class VisualFrameInstruction(BaseModel):
    """One frame in a diagram-series visual instruction."""

    model_config = ConfigDict(extra="forbid")

    description: str
    must_show: list[str] = Field(default_factory=list)


class VisualInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    component_id: str
    subject: str
    visual_job: str
    type_hint: str
    anchor_link: str | None = None
    visual_style: VisualStyle | None = None
    must_show: list[str] = Field(default_factory=list)
    must_not_show: list[str] = Field(default_factory=list)
    source_question_ids: list[str] = Field(default_factory=list)
    frames: list[VisualFrameInstruction] = Field(default_factory=list)
    strategy: str
    density: str | None = None

    @field_validator("visual_style", mode="before")
    @classmethod
    def normalize_visual_style(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value in _VISUAL_STYLES:
            return value
        return None


class VisualStrategyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visuals: list[VisualInstruction] = Field(default_factory=list)


class QuestionPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    section_id: str
    temperature: QuestionTemperature
    prompt: str
    expected_answer: str
    diagram_required: bool = False


class AnswerKeyPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: str


class RepairFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_line: str
    what_not_to_teach: list[str] = Field(default_factory=list)


class ProductionBlueprint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata: BlueprintMetadata
    lesson: LessonModePlan
    voice: VoicePlan
    anchor: AnchorPlan
    sections: list[SectionPlan] = Field(default_factory=list, min_length=1)
    card_rubrics: list[CardRubricPlan] = Field(default_factory=list)
    question_plan: list[QuestionPlanItem] = Field(default_factory=list)
    visual_strategy: VisualStrategyPlan = Field(default_factory=VisualStrategyPlan)
    answer_key: AnswerKeyPlan
    teacher_materials: list[str] = Field(default_factory=list)
    prior_knowledge: list[str] = Field(default_factory=list)
    repair_focus: RepairFocus | None = None
