from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator


# ── Stage 1 output models ─────────────────────────────────────────────────

VisualStyle = Literal["diagram_precision", "illustration"]
_VISUAL_STYLES = {"diagram_precision", "illustration"}


class LessonIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        description="By the end of this lesson the student can... "
        "One sentence, specific and testable. Max 200 chars.",
        max_length=200,
    )
    structure_rationale: str = Field(
        description="Why this structure was chosen given this learner group "
        "and concept. Max 300 chars.",
        max_length=300,
    )


class AnchorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    example: str = Field(
        description="Named anchor example. Specific, concrete, reusable. "
        "e.g. 'splitting a pizza into 8 equal slices'. Max 100 chars.",
        max_length=100,
    )
    reuse_scope: str = Field(
        description="How the anchor recurs across sections — named per section. "
        "Max 200 chars.",
        max_length=200,
    )


class ComponentSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(description="Component slug from registry. Must exist.")
    purpose: str = Field(
        description="One-line pedagogical purpose of this component "
        "at this exact point in the lesson. Aim for 80 chars or fewer, "
        "but preserve a longer purpose when needed for clarity.",
    )


class SectionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Unique section identifier slug e.g. 'orient', 'model'")
    title: str = Field(description="Section title. Max 80 chars.", max_length=80)
    role: str = Field(description="Spec-vocabulary role string for this section.")
    card_id: str | None = Field(
        default=None,
        description="Stable concept-card id for teaching sections; null for plain sections.",
    )
    visual_required: bool
    transition_note: str | None = Field(
        default=None,
        description="Why this section follows the previous one. "
        "Names what prior section established and what this one does with it. "
        "Null for first section only. Max 120 chars.",
        max_length=120,
    )
    components: list[ComponentSlot] = Field(
        description="Ordered component slots. Max 4 per section.",
        max_length=4,
    )

    @field_validator("components")
    @classmethod
    def max_four_components(cls, v: list[ComponentSlot]) -> list[ComponentSlot]:
        if len(v) > 4:
            raise ValueError("Max 4 components per section")
        return v


class QPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    section_id: str
    temperature: Literal["warm", "medium", "cold", "transfer"]
    diagram_required: bool = False


class VoiceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    register_name: Literal["simple", "balanced", "formal"]
    tone: Literal["encouraging", "neutral", "direct"]
    notation: str | None = Field(
        default=None,
        description="Notation and terminology constraint shared by all sections.",
    )


class Misconception(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Misconception id unique within this card, e.g. M1.")
    description: str
    source: Literal["drafted", "teacher"] = "drafted"


class ConceptCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable lowercase dotted concept slug.")
    title: str
    objective: str = Field(description="One observable learner capability.")
    prereqs: list[str] = Field(default_factory=list)
    misconceptions: list[Misconception] = Field(default_factory=list)
    no_known_misconceptions: bool = False
    opens_by: str = Field(
        default="",
        description="Specific continuity instruction for how this card opens.",
    )


class VariantSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    voice: VoiceSpec
    group_description: str


class RepairFocus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_line: str = Field(
        description="Precisely what went wrong in prior learning."
    )
    what_not_to_teach: list[str] = Field(
        description="Concepts or approaches to avoid repeating."
    )


class StructuralPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_mode: Literal[
        "first_exposure", "consolidation", "repair", "retrieval", "transfer"
    ]
    lesson_intent: LessonIntent
    anchor: AnchorSpec
    voice: VoiceSpec
    prior_knowledge: list[str]
    repair_focus: RepairFocus | None = None
    cards: list[ConceptCard] = Field(default_factory=list)
    sections: list[SectionPlan] = Field(
        description="Ordered section plans. Max 6.",
    )
    question_plan: list[QPlanItem]
    answer_key_style: Literal[
        "brief_explanations", "full_working", "answers_only"
    ]

    @field_validator("sections")
    @classmethod
    def max_six_sections(cls, v: list[SectionPlan]) -> list[SectionPlan]:
        if len(v) > 6:
            raise ValueError("Max 6 sections")
        return v

    @model_validator(mode="after")
    def first_section_no_transition(self) -> StructuralPlan:
        if self.sections and self.sections[0].transition_note is not None:
            raise ValueError("First section must have transition_note=null")
        return self

    @model_validator(mode="after")
    def repair_mode_requires_repair_focus(self) -> StructuralPlan:
        if self.lesson_mode == "repair" and self.repair_focus is None:
            raise ValueError("lesson_mode=repair requires repair_focus")
        return self


# ── Stage 1 error types ───────────────────────────────────────────────────


class Stage1PlanFailure(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__(f"Stage 1 failed after 2 attempts: {errors}")


# ── Stage 2 output models ─────────────────────────────────────────────────


class VisualFrameBrief(BaseModel):
    """Stage 2 description of one frame in a diagram-series."""

    model_config = ConfigDict(extra="ignore")

    description: str = Field(
        description="What this frame shows. One sentence."
    )
    must_show: list[str] = Field(default_factory=list)


class VisualStrategySpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    subject: str = Field(
        description="What the visual depicts. One sentence.",
    )
    visual_job: str = Field(
        description=(
            "What this visual is FOR - pedagogical purpose. "
            "E.g. 'introduce the anchor visually', "
            "'summarize the section explanation as a labeled diagram', "
            "'support practice question q-practice-2 with an unlabeled figure'. "
            "Describes intent, not timing."
        ),
    )
    type_hint: Literal["diagram", "chart", "illustration", "comparison"]
    anchor_link: str = Field(
        description="How this visual connects to the anchor example.",
    )
    visual_style: VisualStyle | None = Field(
        default=None,
        description=(
            "Use diagram_precision for label-heavy diagrams, charts, comparisons, "
            "or visuals that must be inspected. Use illustration for explanatory "
            "scene-style artwork."
        ),
    )
    must_show: list[str] = Field(
        default_factory=list,
        description="Two to five short required visual elements or labels.",
    )
    must_not_show: list[str] = Field(
        default_factory=list,
        description="Two to five short exclusions that would distract or mislead.",
    )
    source_question_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Question IDs this visual supports. "
            "Populate when the visual must match exact question content."
        ),
    )
    frames: list[VisualFrameBrief] = Field(
        default_factory=list,
        description=(
            "Frame descriptions for diagram-series components. "
            "Must have >= 2 entries when the section's visual-capable "
            "component is diagram-series."
        ),
    )

    @field_validator("visual_style", mode="before")
    @classmethod
    def normalize_visual_style(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value in _VISUAL_STYLES:
            return value
        return None


class ComponentBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    component_id: str = Field(
        description="Planned component IDs must match StructuralPlan slugs."
    )
    content_intent: str = Field(
        description="Precise, actionable writer brief. Prefer concise wording, "
        "but preserve all instructions needed for correct downstream generation.",
    )


class QuestionBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question_id: str = Field(
        description="Must match question_id from question_plan."
    )
    prompt_text: str = Field(
        description="The exact question the student sees."
    )
    expected_answer: str = Field(
        description="Concise correct answer for the answer key."
    )


class SectionBrief(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section_id: str = Field(
        description="Must match the section assigned to this call."
    )
    components: list[ComponentBrief]
    question_briefs: list[QuestionBrief] = Field(default_factory=list)
    visual_strategy: VisualStrategySpec | None = None

    # Internal flags — not emitted by LLM, set by retry logic on failure
    _failed: bool = PrivateAttr(default=False)
    _errors: list[str] = PrivateAttr(default_factory=list)


def stage2_brief_preview_payload(brief: SectionBrief) -> dict[str, object]:
    return {
        "components": [
            {
                "component_id": component.component_id,
                "content_intent": component.content_intent,
            }
            for component in brief.components
        ],
        "question_prompts": [question.prompt_text for question in brief.question_briefs],
        "visual_subject": brief.visual_strategy.subject if brief.visual_strategy else None,
    }


# ── Stage 2 error types ───────────────────────────────────────────────────


class BlueprintAssemblyBlocked(Exception):
    def __init__(self, failed_sections: list[str]):
        self.failed_sections = failed_sections
        super().__init__(
            f"Assembly blocked — sections failed: {failed_sections}"
        )
