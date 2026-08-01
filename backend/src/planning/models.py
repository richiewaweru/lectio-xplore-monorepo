from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


KnowledgeType = Literal["procedural", "conceptual", "factual", "evaluative"]
GroupProfile = Literal["support", "core", "extension"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScopeContract(StrictModel):
    must_establish: list[str] = Field(min_length=1)
    may_include: list[str] = Field(default_factory=list)
    must_not_introduce: list[str] = Field(min_length=1)
    assumed_prerequisites: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    notation: str | None = None


class ConceptCandidate(StrictModel):
    slug: str = Field(pattern=r"^[a-z0-9.-]+$")
    title: str


class PlannedLesson(StrictModel):
    concept_candidate: ConceptCandidate
    objective: str = Field(min_length=3)
    prerequisites: list[str] = Field(default_factory=list)
    external_prerequisites: list[str] = Field(default_factory=list)
    must_establish: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    primary_knowledge_type: KnowledgeType
    secondary_demand: KnowledgeType | None = None
    merge_warning: bool = False


class PathModule(StrictModel):
    title: str
    lessons: list[PlannedLesson] = Field(min_length=1)


class AdjacentMergeReview(StrictModel):
    lesson_a: str
    lesson_b: str
    reason: str


class PrerequisiteRisk(StrictModel):
    missing: str
    needed_by: str
    note: str


class PathCompleteness(StrictModel):
    forward_verified: bool
    reaches_destination: bool
    note: str | None = None


class PathPlan(StrictModel):
    unit: str | None = None
    subject: str | None = None
    grade_level: str | None = None
    destination_objective: str | None = None
    starting_knowledge: list[str] = Field(default_factory=list)
    scope_contract: ScopeContract
    modules: list[PathModule] = Field(min_length=1)
    adjacent_merge_reviews: list[AdjacentMergeReview]
    prerequisite_risks: list[PrerequisiteRisk]
    completeness: PathCompleteness

    @property
    def lessons(self) -> list[PlannedLesson]:
        return [lesson for module in self.modules for lesson in module.lessons]

    @property
    def concept_slugs(self) -> set[str]:
        return {lesson.concept_candidate.slug for lesson in self.lessons}


class PathPlannerRequest(StrictModel):
    topic: str
    subject: str
    grade_level: str
    destination_objective: str
    starting_knowledge: list[str]
    curriculum_context: str | None = None
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    terminology: list[str] = Field(default_factory=list)
    notation: str | None = None
    assessment_context: str | None = None
    known_difficulties: list[str] = Field(default_factory=list)


class PathReplanRequest(PathPlannerRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)


class UnitCreate(StrictModel):
    title: str
    topic: str
    subject: str
    grade_level: str
    destination_objective: str
    starting_knowledge: list[str]
    curriculum_context: str | None = None


class UnitUpdate(StrictModel):
    title: str | None = None
    curriculum_context: str | None = None
    destination_objective: str | None = None
    starting_knowledge: list[str] | None = None


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


class LessonPart(StrictModel):
    concept_candidate: ConceptCandidate
    objective: str = Field(min_length=3)
    must_establish: list[str] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    primary_knowledge_type: KnowledgeType
    secondary_demand: KnowledgeType | None = None


class SplitPathLessonRequest(StrictModel):
    parts: list[LessonPart] = Field(min_length=2)


class GuardedSplitPathLessonRequest(SplitPathLessonRequest):
    path_version_id: str
    path_revision: int = Field(ge=1)
    lesson_revision: int = Field(ge=1)


class MergePathLessonsRequest(StrictModel):
    lesson_ids: list[str] = Field(min_length=2)
    merged: LessonPart


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


class PathStructuralPlan(StrictModel):
    anchor: PathAnchor
    cards: list[dict]
    sections: list[dict]
    deviation_request: PathDeviationRequest | None
    objective_concern: str | None
