from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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

    reuse_scope: str


class VoicePlan(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    register_name: str = Field(alias="register", serialization_alias="register")
    tone: str | None = None


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
    components: list[ComponentPlan] = Field(default_factory=list, min_length=1)


class VisualInstruction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    strategy: str
    density: str | None = None


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
    question_plan: list[QuestionPlanItem] = Field(default_factory=list, min_length=1)
    visual_strategy: VisualStrategyPlan = Field(default_factory=VisualStrategyPlan)
    answer_key: AnswerKeyPlan
    teacher_materials: list[str] = Field(default_factory=list)
    prior_knowledge: list[str] = Field(default_factory=list)
    repair_focus: RepairFocus | None = None
