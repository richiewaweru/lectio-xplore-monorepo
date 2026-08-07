from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


KnowledgeType = Literal["procedural", "conceptual", "factual", "evaluative"]
GroupProfile = Literal["support", "core", "extension"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TolerantModel(BaseModel):
    """Prompt-facing draft: tolerate stray LLM keys without failing the plan."""

    model_config = ConfigDict(extra="ignore")


# ── Active minimal path-planner contract ───────────────────────────────────


class PathScopeDraft(TolerantModel):
    must_cover: list[str] = Field(default_factory=list)
    do_not_cover: list[str] = Field(default_factory=list)


class PathLessonDraft(TolerantModel):
    key: str = ""
    title: str = ""
    objective: str = ""
    requires: list[str] = Field(default_factory=list)
    must_establish: list[str] = Field(default_factory=list)
    knowledge_type: str = ""


class PathPlanDraft(TolerantModel):
    scope: PathScopeDraft = Field(default_factory=PathScopeDraft)
    lessons: list[PathLessonDraft] = Field(default_factory=list)


class CanonicalPathScope(StrictModel):
    must_cover: list[str] = Field(min_length=1)
    do_not_cover: list[str] = Field(default_factory=list)


class CanonicalPathLesson(StrictModel):
    key: str
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    requires: list[str] = Field(default_factory=list)
    must_establish: list[str] = Field(min_length=1)
    knowledge_type: KnowledgeType


class CanonicalPathPlan(StrictModel):
    scope: CanonicalPathScope
    lessons: list[CanonicalPathLesson] = Field(min_length=1)


class CanonicalLessonPart(StrictModel):
    title: str = Field(min_length=1)
    objective: str = Field(min_length=3)
    must_establish: list[str] = Field(min_length=1)
    knowledge_type: KnowledgeType


class PathPlannerRequest(StrictModel):
    topic: str
    subject: str
    grade_level: str
    destination_objective: str
    starting_knowledge: list[str]
    curriculum_context: str | None = None
    class_notes: str | None = None


class PathReplanRequest(PathPlannerRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)


class ConstructorOutput(StrictModel):
    title: str
    topic: str
    destination_objective: str
    starting_knowledge: list[str]
    curriculum_context: str | None = None
    class_notes: str | None = None
    clarifying_question: str | None = None


class ConstructorReadbackRequest(StrictModel):
    subject: str
    grade_level: str
    raw_text: str = Field(min_length=1)
    correction: str | None = None
    clarifying_answer: str | None = None


class UnitCreate(StrictModel):
    title: str
    topic: str
    subject: str
    grade_level: str
    destination_objective: str
    starting_knowledge: list[str]
    curriculum_context: str | None = None
    class_notes: str | None = None


class UnitUpdate(StrictModel):
    title: str | None = None
    curriculum_context: str | None = None
    destination_objective: str | None = None
    starting_knowledge: list[str] | None = None
    class_notes: str | None = None


class PathLessonPatch(StrictModel):
    title: str | None = None
    objective: str | None = Field(default=None, min_length=3)
    exclusions: list[str] | None = None
    must_establish: list[str] | None = None
    primary_knowledge_type: KnowledgeType | None = None
    secondary_demand: KnowledgeType | None = None


class GuardedPathLessonPatch(PathLessonPatch):
    path_version_id: str
    path_revision: int = Field(ge=1)
    lesson_revision: int = Field(ge=1)


class SplitPathLessonRequest(StrictModel):
    parts: list[CanonicalLessonPart] = Field(min_length=2)


class GuardedSplitPathLessonRequest(SplitPathLessonRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)
    lesson_revision: int = Field(ge=1)


class MergePathLessonsRequest(StrictModel):
    lesson_ids: list[str] = Field(min_length=2)
    merged: CanonicalLessonPart


class GuardedMergePathLessonsRequest(MergePathLessonsRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)
    lesson_revisions: dict[str, int] = Field(min_length=2)


class ReorderPathLessonsRequest(StrictModel):
    lesson_ids: list[str] = Field(min_length=1)


class GuardedReorderPathLessonsRequest(ReorderPathLessonsRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)


class PathVersionMutationRequest(StrictModel):
    path_version_id: str
    path_revision: int = Field(ge=1)


class PathLessonMutationRequest(PathVersionMutationRequest):
    lesson_revision: int = Field(ge=1)


class RestorePathVersionRequest(PathVersionMutationRequest):
    reason: str = Field(min_length=3, max_length=500)


class PathChatEditRequest(PathVersionMutationRequest):
    message: str = Field(min_length=1, max_length=2000)


class InsertFoundationLessonRequest(PathVersionMutationRequest):
    before_lesson_id: str
    lesson: CanonicalLessonPart


class MarkStartingKnowledgeRequest(PathVersionMutationRequest):
    knowledge: str = Field(min_length=1)


class GroupVoice(StrictModel):
    register_name: Literal["simple", "balanced", "formal"]
    tone: Literal["encouraging", "neutral", "direct"]
    notation: str | None = Field(default=None, max_length=120)


class UnitGroupInput(StrictModel):
    id: str | None = None
    label: str = Field(min_length=1, max_length=80)
    profile: GroupProfile
    description: str = Field(min_length=3, max_length=500)
    voice: GroupVoice


class UnitGroupsWriteRequest(StrictModel):
    groups_revision: int = Field(ge=1)
    groups: list[UnitGroupInput] = Field(max_length=3)


class TeachingPeriodInput(StrictModel):
    id: str | None = None
    title: str = Field(min_length=1, max_length=120)
    lesson_ids: list[str] = Field(min_length=1)
    planned_minutes: int | None = Field(default=None, ge=10, le=240)
    teacher_note: str | None = Field(default=None, max_length=1000)


class ScheduleWriteRequest(PathVersionMutationRequest):
    schedule_revision: int = Field(ge=1)
    periods: list[TeachingPeriodInput] = Field(min_length=1, max_length=40)


class ScheduleSuggestRequest(PathVersionMutationRequest):
    period_count: int = Field(ge=1, le=40)
    minutes_per_period: int = Field(ge=10, le=240)


class ShapeDeviationCreateRequest(PathLessonMutationRequest):
    lesson_mode: Literal[
        "first_exposure", "consolidation", "repair", "retrieval", "transfer"
    ]
    operation: Literal["insert", "remove", "replace", "reorder"]
    target_slot: str = Field(min_length=1, max_length=80)
    replacement_slot: str | None = Field(default=None, max_length=80)
    reason: str = Field(min_length=3, max_length=500)


class ShapeDeviationDecisionRequest(PathLessonMutationRequest):
    pass


ProjectionType = Literal[
    "full_lesson",
    "homework",
    "revision_sheet",
    "flashcards",
    "quiz",
    "answer_key",
    "unit_exam",
]


class ResourceComposeRequest(PathVersionMutationRequest):
    projection: ProjectionType
    path_lesson_ids: list[str] = Field(default_factory=list)
    period_ids: list[str] = Field(default_factory=list)
    group_ids: list[str] = Field(default_factory=list)
    component_refs: list[str] = Field(default_factory=list)
    item_ids: list[str] = Field(default_factory=list)
    include_keys: bool = False
    include_support_notes: bool = False


class LessonActualWriteRequest(PathLessonMutationRequest):
    actual_revision: int = Field(default=0, ge=0)
    status: Literal["established", "partial", "recovery_needed", "not_taught"]
    pace: Literal["faster", "as_planned", "slower", "not_recorded"] = "not_recorded"
    established_concepts: list[str] = Field(default_factory=list, max_length=100)
    unresolved_misconceptions: list[str] = Field(default_factory=list, max_length=100)
    anchor_used: str | None = Field(default=None, max_length=500)
    teacher_note: str | None = Field(default=None, max_length=2000)


class MarksItemCount(StrictModel):
    item_id: str = Field(min_length=1)
    option_counts: dict[str, int] = Field(min_length=1)


class MarksWriteRequest(PathLessonMutationRequest):
    marks_revision: int = Field(default=0, ge=0)
    group_id: str | None = None
    items: list[MarksItemCount] = Field(min_length=1, max_length=100)


class PrepareLessonRequest(StrictModel):
    group_ids: list[str] = Field(default_factory=list)
    lesson_mode: Literal["first_exposure", "consolidation", "repair", "retrieval", "transfer"]


class GuardedPrepareLessonRequest(PrepareLessonRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)
    lesson_revision: int = Field(ge=1)


class RegenerateLessonRequest(GuardedPrepareLessonRequest):
    reason: str = Field(min_length=3, max_length=500)


class PreparedLessonResponse(StrictModel):
    generation_id: str
    path_lesson_id: str
    objective: str
    objective_hash: str
    skeleton_id: str
    skeleton_version: int
    slots: list[str]
    section_roles: list[str]
    status: Literal["awaiting_review"]
    reused: bool


class PreparedLessonStatusResponse(StrictModel):
    path_lesson_id: str
    lesson_revision: int
    generation_id: str | None
    generation_status: str
    workflow_stage: str
    objective_hash: str
    stale: bool
    can_prepare: bool
    can_regenerate: bool


class MergeCriticResult(StrictModel):
    verdict: Literal["keep_separate", "merge_suggested", "teacher_decision"]
    reason: str
    merged_objective: str | None
    diagnostic_cost: str | None


class SelectedComponent(StrictModel):
    slug: str
    purpose: str
    reason: str


class ComponentSelection(StrictModel):
    components: list[SelectedComponent]
    budget_pressure: str | None


class PathAnchor(StrictModel):
    description: str
    source: Literal["carried", "new"]


class PathDeviationRequest(StrictModel):
    operation: Literal["insert", "remove", "replace", "reorder"]
    target_slot: str
    replacement_slot: str | None
    reason: str


# ── Structural planner prompt-facing contract ─────────────────────────────
#
# These models are the JSON schema the structural planner sees. They are
# deliberately NOT the canonical execution contracts:
#
#   * They are prompt-facing. On DeepSeek the schema is rendered into the prompt
#     text (see v3_execution.llm_helpers.structured_output_type_for_model), not
#     enforced by constrained decoding, so ``extra="forbid"`` here would not stop
#     the model emitting stray keys — it would only turn drift that
#     planning.bridge._normalize_page_concept_card_payload already absorbs into
#     hard failures. Hence ``extra="ignore"`` on every nested model.
#   * The canonical ConceptCard is an execution/storage contract whose ``id`` and
#     ``objective`` the bridge ASSIGNS rather than reads. The two must stay free
#     to diverge.
#
# Field descriptions are the only steering available on the prompted path, so
# they carry the contract that the schema itself cannot enforce.


class PathStructuralComponentSlot(BaseModel):
    """Legacy component-selector shape. Ignored entirely on the native page path."""

    model_config = ConfigDict(extra="ignore")

    slug: str
    purpose: str = ""
    # Declared so the advisory-stripping pass in the bridge still sees it.
    reason: str | None = None


class PathStructuralMisconception(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    description: str | None = Field(
        default=None,
        description="The wrong belief, stated the way a learner would state it.",
    )
    # The planner sometimes names this field 'statement'. Declared so the bridge's
    # statement -> description rename still has something to rename.
    statement: str | None = None
    # Deliberately not a Literal: unrecognised sources are dropped downstream
    # rather than failing the whole plan.
    source: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_bare_string(cls, value: object) -> object:
        if isinstance(value, str):
            return {"description": value}
        return value


class PathStructuralCard(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = Field(
        default=None,
        description="Echo concept_id verbatim. The path layer owns this value.",
    )
    title: str | None = None
    objective: str | None = Field(
        default=None,
        description="Echo the supplied objective verbatim. Never rewrite it.",
    )
    prereqs: list[str] = Field(default_factory=list)
    misconceptions: list[PathStructuralMisconception] = Field(default_factory=list)
    no_known_misconceptions: bool = False
    opens_by: str | None = None


class PathStructuralSection(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(
        description=(
            "Must equal slots[i].slot_id verbatim, in the supplied order. "
            "The field is named 'id' — do not emit a key called 'slot_id'."
        ),
    )
    role: str = Field(
        description=(
            "Must ALSO equal slots[i].slot_id verbatim — not slots[i].role."
        ),
    )
    title: str = Field(description="Concise section title. Aim for ~80 chars (advisory).")
    card_id: str | None = Field(
        default=None,
        description="concept_id for teaching sections; null for plain sections.",
    )
    visual_required: bool = False
    transition_note: str | None = Field(
        default=None,
        description=(
            "Why this section follows the previous one. Null for the first "
            "section only. Aim for ~120 chars (advisory)."
        ),
    )
    components: list[PathStructuralComponentSlot] | None = None


class PathStructuralPlan(StrictModel):
    anchor: PathAnchor
    # max_length only. The lower bound lives in
    # planning.structural_validation.validate_path_structural_result, which runs
    # AFTER the deviation_request / objective_concern escape hatches — a
    # legitimate "this objective does not fit" response carries no cards, and
    # must keep its readable message instead of becoming a schema error.
    cards: list[PathStructuralCard] = Field(
        default_factory=list,
        max_length=1,
        description="Exactly one concept card, unless emitting objective_concern.",
    )
    sections: list[PathStructuralSection] = Field(default_factory=list)
    deviation_request: PathDeviationRequest | None = None
    objective_concern: str | None = None
