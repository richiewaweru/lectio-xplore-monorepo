from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
from pipeline.types.requests import BlockVisualPlacement, GenerationMode

PlanningTopicType = Literal["concept", "process", "facts", "mixed"]
PlanningLearningOutcome = Literal[
    "understand-why",
    "be-able-to-do",
    "remember-terms",
    "apply-to-new",
]
PlanningClassStyle = Literal[
    "tries-before-told",
    "needs-explanation-first",
    "engages-with-visuals",
    "responds-to-worked-examples",
    "restless-without-activity",
]
PlanningFormat = Literal["printed-booklet", "screen-based", "both"]
PlanningTone = Literal["supportive", "neutral", "rigorous"]
PlanningReadingLevel = Literal["simple", "standard", "advanced"]
PlanningExplanationStyle = Literal["concrete-first", "concept-first", "balanced"]
PlanningExampleStyle = Literal["everyday", "academic", "exam"]
PlanningBrevity = Literal["tight", "balanced", "expanded"]
PlanningScaffoldLevel = Literal["high", "medium", "low"]
PlanningVisualIntent = Literal[
    "explain_structure",
    "show_realism",
    "demonstrate_process",
    "compare_variants",
]
PlanningVisualMode = Literal["image", "svg"]
PlanningSectionRole = Literal[
    "intro",
    "explain",
    "practice",
    "summary",
    "process",
    "compare",
    "timeline",
    "visual",
    "discover",
]
PlanningSpecStatus = Literal["draft", "reviewed", "committed"]


class TeacherSignals(BaseModel):
    topic_type: PlanningTopicType | None = None
    learning_outcome: PlanningLearningOutcome | None = None
    class_style: list[PlanningClassStyle] = Field(default_factory=list)
    format: PlanningFormat | None = None

    @field_validator("class_style")
    @classmethod
    def _limit_class_styles(cls, value: list[PlanningClassStyle]) -> list[PlanningClassStyle]:
        seen = list(dict.fromkeys(value))
        return seen[:3]


class DeliveryPreferences(BaseModel):
    tone: PlanningTone = "supportive"
    reading_level: PlanningReadingLevel = "standard"
    explanation_style: PlanningExplanationStyle = "balanced"
    example_style: PlanningExampleStyle = "everyday"
    brevity: PlanningBrevity = "balanced"


class TeacherConstraints(BaseModel):
    more_practice: bool = False
    keep_short: bool = False
    use_visuals: bool = False
    print_first: bool = False


class StudioBriefRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=200)
    audience: str = Field(min_length=1, max_length=200)
    prior_knowledge: str | None = Field(default="", max_length=1000)
    extra_context: str | None = Field(default="", max_length=1000)
    mode: GenerationMode = Field(default=GenerationMode.BALANCED)
    signals: TeacherSignals = Field(default_factory=TeacherSignals)
    preferences: DeliveryPreferences = Field(default_factory=DeliveryPreferences)
    constraints: TeacherConstraints = Field(default_factory=TeacherConstraints)
    forced_template_id: str | None = None

    @field_validator("intent", "audience", "prior_knowledge", "extra_context")
    @classmethod
    def _trim_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @model_validator(mode="after")
    def _validate_required(self) -> "StudioBriefRequest":
        if not self.intent:
            raise ValueError("intent must not be empty.")
        if not self.audience:
            raise ValueError("audience must not be empty.")
        return self

    def source_brief_id(self) -> str:
        return uuid4().hex


class GenerationDirectives(BaseModel):
    tone_profile: PlanningTone
    reading_level: PlanningReadingLevel
    explanation_style: PlanningExplanationStyle
    example_style: PlanningExampleStyle
    scaffold_level: PlanningScaffoldLevel
    brevity: PlanningBrevity


class NormalizedBrief(BaseModel):
    brief: StudioBriefRequest
    resolved_topic_type: PlanningTopicType
    resolved_learning_outcome: PlanningLearningOutcome
    resolved_format: PlanningFormat
    directives: GenerationDirectives
    scope_warning: str | None = None
    keyword_profile: list[str] = Field(default_factory=list)


class PlanningSignalAffinity(BaseModel):
    topic_type: dict[PlanningTopicType, float] = Field(default_factory=dict)
    learning_outcome: dict[PlanningLearningOutcome, float] = Field(default_factory=dict)
    class_style: dict[PlanningClassStyle, float] = Field(default_factory=dict)
    format: dict[PlanningFormat, float] = Field(default_factory=dict)


class PlanningTemplateContract(BaseModel):
    id: str
    name: str
    family: str
    intent: str
    tagline: str
    reading_style: str | None = None
    tags: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)
    not_ideal_for: list[str] = Field(default_factory=list)
    learner_fit: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    interaction_level: str
    lesson_flow: list[str] = Field(default_factory=list)
    required_components: list[str] = Field(default_factory=list)
    optional_components: list[str] = Field(default_factory=list)
    always_present: list[str] = Field(default_factory=list)
    available_components: list[str] = Field(default_factory=list)
    component_budget: dict[str, int] = Field(default_factory=dict)
    max_per_section: dict[str, int] = Field(default_factory=dict)
    default_behaviours: dict[str, str] = Field(default_factory=dict)
    section_role_defaults: dict[PlanningSectionRole, list[str]] = Field(default_factory=dict)
    signal_affinity: PlanningSignalAffinity = Field(default_factory=PlanningSignalAffinity)
    layout_notes: list[str] = Field(default_factory=list)
    responsive_rules: list[str] = Field(default_factory=list)
    print_rules: list[str] = Field(default_factory=list)
    allowed_presets: list[str] = Field(default_factory=list)
    why_this_template_exists: str = ""
    generation_guidance: dict[str, str | list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _hydrate_legacy_fields(self) -> "PlanningTemplateContract":
        if not self.always_present and self.required_components:
            self.always_present = list(dict.fromkeys(self.required_components))
        if not self.available_components:
            self.available_components = list(
                dict.fromkeys([*self.required_components, *self.optional_components])
            )
        return self


class TemplateAlternative(BaseModel):
    template_id: str
    template_name: str
    fit_score: float = Field(ge=0, le=1)
    why_not_chosen: str


class TemplateDecision(BaseModel):
    chosen_id: str
    chosen_name: str
    rationale: str
    fit_score: float = Field(ge=0, le=1)
    alternatives: list[TemplateAlternative] = Field(default_factory=list)


class VisualPolicy(BaseModel):
    required: bool = False
    intent: PlanningVisualIntent | None = None
    mode: PlanningVisualMode | None = None
    goal: str | None = None
    style_notes: str | None = None

    @model_validator(mode="after")
    def _mode_required_when_visual_required(self) -> "VisualPolicy":
        if self.required and (self.mode is None or self.intent is None):
            raise ValueError("VisualPolicy: mode and intent must be set when required=True")
        return self


class SectionGenerationNotes(BaseModel):
    tone_override: str | None = None
    brevity_override: PlanningBrevity | None = None
    explanation_override: str | None = None


class PlanningSectionPlan(BaseModel):
    id: str
    order: int
    role: PlanningSectionRole
    title: str
    objective: str | None = None
    focus_note: str | None = None
    transition_note: str | None = None
    selected_components: list[str] = Field(default_factory=list)
    visual_policy: VisualPolicy | None = None
    generation_notes: SectionGenerationNotes | None = None
    rationale: str
    terms_to_define: list[str] = Field(default_factory=list)
    terms_assumed: list[str] = Field(default_factory=list)
    practice_target: str | None = None
    visual_placements: list[BlockVisualPlacement] = Field(default_factory=list)

    @field_validator("title", "objective", "focus_note", "transition_note", "rationale")
    @classmethod
    def _trim_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PlanningGenerationSpec(BaseModel):
    id: str
    template_id: str
    preset_id: str = "blue-classroom"
    mode: GenerationMode = GenerationMode.BALANCED
    template_decision: TemplateDecision
    lesson_rationale: str
    directives: GenerationDirectives
    committed_budgets: dict[str, int] = Field(default_factory=dict)
    sections: list[PlanningSectionPlan]
    warning: str | None = None
    source_brief_id: str
    source_brief: StudioBriefRequest
    status: PlanningSpecStatus = "draft"

    @model_validator(mode="after")
    def _validate_sections(self) -> "PlanningGenerationSpec":
        expected = list(range(1, len(self.sections) + 1))
        actual = [section.order for section in self.sections]
        if actual != expected:
            raise ValueError("Section order must be sequential starting at 1.")
        return self


class PlanningRefinedSection(BaseModel):
    title: str
    rationale: str
    transition_note: str | None = None
    terms_to_define: list[str] = Field(default_factory=list)
    terms_assumed: list[str] = Field(default_factory=list)
    practice_target: str | None = None


class PlanningRefinementOutput(BaseModel):
    lesson_rationale: str
    warning: str | None = None
    sections: list[PlanningRefinedSection]
