import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


JSON_DOCUMENT_TYPE = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class UserModel(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    picture_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    profile = relationship("StudentProfileModel", back_populates="user", uselist=False)
    generations = relationship("GenerationModel", back_populates="user")
    packs = relationship("LearningPackModel", back_populates="user")
    llm_calls = relationship("LLMCallModel", back_populates="user")
    editable_lessons = relationship("EditableLessonModel", back_populates="user")
    concepts = relationship("ConceptModel", back_populates="created_by_user")
    units = relationship("UnitModel", back_populates="owner")


class StudentProfileModel(Base):
    # Production note: this legacy table name is intentionally retained for now.
    # It currently stores teacher-profile data, and the old learner columns are
    # only kept for external DB compatibility during the rollout period.
    __tablename__ = "student_profiles"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    age = Column(Integer, nullable=True)
    education_level = Column(String, nullable=True)
    interests = Column(Text, nullable=True)
    learning_style = Column(String, nullable=True)
    preferred_notation = Column(String, nullable=True)
    prior_knowledge = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)
    preferred_depth = Column(String, nullable=True)
    learner_description = Column(Text, nullable=True)
    teacher_role = Column(String, nullable=False, default="teacher")
    subjects = Column(Text, default="[]")
    default_grade_band = Column(String, nullable=False, default="high_school")
    default_audience_description = Column(Text, default="")
    curriculum_framework = Column(Text, default="")
    classroom_context = Column(Text, default="")
    planning_goals = Column(Text, default="")
    school_or_org_name = Column(String, default="")
    delivery_preferences = Column(Text, default="{}")
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("UserModel", back_populates="profile")

    def get_subjects_list(self) -> list[str]:
        return json.loads(self.subjects) if self.subjects else []

    def set_subjects_list(self, values: list[str]) -> None:
        self.subjects = json.dumps(values)

    def get_delivery_preferences(self) -> dict:
        return json.loads(self.delivery_preferences) if self.delivery_preferences else {}

    def set_delivery_preferences(self, values: dict) -> None:
        self.delivery_preferences = json.dumps(values)


class LearningPackModel(Base):
    __tablename__ = "learning_packs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    learning_job_type = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    pack_plan_json = Column(Text, nullable=False)
    status = Column(String, default="pending", nullable=False, index=True)
    resource_count = Column(Integer, nullable=False)
    completed_count = Column(Integer, default=0, nullable=False)
    current_resource_label = Column(String, nullable=True)
    current_phase = Column(String, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    generations = relationship("GenerationModel", back_populates="pack")
    user = relationship("UserModel", back_populates="packs")


class GenerationModel(Base):
    __tablename__ = "generations"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    subject = Column(String, nullable=False)
    context = Column(Text, default="")
    mode = Column(String, default="balanced", nullable=False, server_default="balanced")
    status = Column(String, default="pending")
    document_path = Column(String, nullable=True)
    document_json = Column(JSON_DOCUMENT_TYPE, nullable=True)
    error = Column(Text, nullable=True)
    error_type = Column(String, nullable=True, index=True)
    error_code = Column(String, nullable=True, index=True)
    requested_template_id = Column(String, nullable=False, index=True)
    resolved_template_id = Column(String, nullable=True, index=True)
    requested_preset_id = Column(String, nullable=False, index=True)
    resolved_preset_id = Column(String, nullable=True, index=True)
    section_count = Column(Integer, nullable=True)
    quality_passed = Column(Boolean, nullable=True)
    generation_time_seconds = Column(Float, nullable=True)
    planning_spec_json = Column(Text, nullable=True)
    chunked_state_json = Column(JSON_DOCUMENT_TYPE, nullable=True)
    report_json = Column(JSON_DOCUMENT_TYPE, nullable=True)
    pack_id = Column(String, ForeignKey("learning_packs.id"), nullable=True, index=True)
    pack_resource_id = Column(String, nullable=True, index=True)
    pack_resource_label = Column(String, nullable=True)
    variant_label = Column(String, nullable=True)
    variant_spec = Column(JSON_DOCUMENT_TYPE, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    last_heartbeat = Column(DateTime, nullable=True, index=True)

    user = relationship("UserModel", back_populates="generations")
    pack = relationship("LearningPackModel", back_populates="generations")


class ConceptModel(Base):
    __tablename__ = "concepts"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    canonical_slug = Column(String, unique=True, nullable=False, index=True)
    subject = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    canonical_description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft", server_default="draft")
    created_by = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    created_by_user = relationship("UserModel", back_populates="concepts")
    cards = relationship("ConceptCardModel", back_populates="canonical_concept")
    lesson_provenance = relationship("LessonProvenanceModel", back_populates="concept")
    path_lessons = relationship("PathLessonModel", back_populates="concept")


class ConceptCardModel(Base):
    __tablename__ = "concept_cards"

    id = Column(String, primary_key=True)
    pack_id = Column(String, nullable=False, index=True)
    slug = Column(String, nullable=False)
    title = Column(String, nullable=False)
    objective = Column(Text, nullable=False)
    prereqs = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    misconceptions = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    teacher_edited = Column(Boolean, nullable=False, default=False)
    source_card_id = Column(String, nullable=True, index=True)
    source_pack_id = Column(String, nullable=True, index=True)
    canonical_concept_id = Column(
        String,
        ForeignKey("concepts.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    items = relationship("PackItemModel", back_populates="card")
    canonical_concept = relationship("ConceptModel", back_populates="cards")


class LessonProvenanceModel(Base):
    __tablename__ = "lesson_provenance"

    pack_id = Column(String, primary_key=True)
    concept_id = Column(String, ForeignKey("concepts.id"), nullable=True, index=True)
    path_version_id = Column(String, nullable=True, index=True)
    path_lesson_id = Column(String, nullable=True, index=True)
    objective_hash = Column(String, nullable=True)
    skeleton_id = Column(String, nullable=True)
    skeleton_version = Column(Integer, nullable=True)
    knowledge_type = Column(String, nullable=True)
    knowledge_type_source = Column(String, nullable=True)
    toggles_applied = Column(JSON_DOCUMENT_TYPE, nullable=True)
    deviations_applied = Column(JSON_DOCUMENT_TYPE, nullable=True)
    path_lesson_revision = Column(Integer, nullable=True)
    lesson_mode = Column(String, nullable=True)
    group_ids = Column(JSON_DOCUMENT_TYPE, nullable=True)
    preparation_key = Column(String, nullable=True, index=True)
    supersedes_pack_id = Column(String, nullable=True, index=True)
    regeneration_reason = Column(Text, nullable=True)
    invalidated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    concept = relationship("ConceptModel", back_populates="lesson_provenance")


class SkeletonShadowRecordModel(Base):
    __tablename__ = "skeleton_shadow_records"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    generation_id = Column(String, nullable=False, unique=True, index=True)
    subject = Column(String, nullable=False, index=True)
    grade = Column(String, nullable=False, index=True)
    objective = Column(Text, nullable=False)
    current_roles = Column(JSON_DOCUMENT_TYPE, nullable=False)
    classifier_type = Column(String, nullable=False, index=True)
    classifier_confidence = Column(String, nullable=False, index=True)
    classifier_success_test = Column(Text, nullable=False)
    classifier_note = Column(Text, nullable=True)
    skeleton_id = Column(String, nullable=False, index=True)
    skeleton_version = Column(Integer, nullable=False)
    expanded_slots = Column(JSON_DOCUMENT_TYPE, nullable=False)
    toggles_applied = Column(JSON_DOCUMENT_TYPE, nullable=False)
    expansion_warnings = Column(JSON_DOCUMENT_TYPE, nullable=False)
    structural_match_score = Column(Float, nullable=False)
    reviewer_preference = Column(String, nullable=True)
    wrong_classification = Column(Boolean, nullable=True)
    deviation_required = Column(Boolean, nullable=True)
    severity = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class UnitModel(Base):
    __tablename__ = "units"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    subject = Column(String, nullable=False, index=True)
    grade_level = Column(String, nullable=False, index=True)
    curriculum_context = Column(Text, nullable=True)
    destination_objective = Column(Text, nullable=False)
    starting_knowledge = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    status = Column(String, nullable=False, default="draft", server_default="draft")
    active_path_version_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    owner = relationship("UserModel", back_populates="units")
    scope_contract = relationship(
        "UnitScopeContractModel",
        back_populates="unit",
        uselist=False,
        cascade="all, delete-orphan",
    )
    path_versions = relationship(
        "PathVersionModel",
        back_populates="unit",
        cascade="all, delete-orphan",
    )


class UnitScopeContractModel(Base):
    __tablename__ = "unit_scope_contracts"

    unit_id = Column(String, ForeignKey("units.id"), primary_key=True)
    must_establish = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    may_include = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    must_not_introduce = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    assumed_prerequisites = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    terminology = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    notation = Column(Text, nullable=True)

    unit = relationship("UnitModel", back_populates="scope_contract")


class PathVersionModel(Base):
    __tablename__ = "path_versions"
    __table_args__ = (UniqueConstraint("unit_id", "version", name="uq_path_version_unit_version"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    unit_id = Column(String, ForeignKey("units.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="draft", server_default="draft")
    generated_by = Column(String, nullable=False, default="path_planner")
    source_plan_json = Column(JSON_DOCUMENT_TYPE, nullable=False)
    merge_critic_results = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    prerequisite_risks = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    forward_verified = Column(Boolean, nullable=False, default=False)
    reaches_destination = Column(Boolean, nullable=False, default=False)
    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    unit = relationship("UnitModel", back_populates="path_versions")
    lessons = relationship(
        "PathLessonModel",
        back_populates="path_version",
        cascade="all, delete-orphan",
        order_by="PathLessonModel.position",
    )


class PathLessonModel(Base):
    __tablename__ = "path_lessons"
    __table_args__ = (
        UniqueConstraint("path_version_id", "position", name="uq_path_lesson_version_position"),
    )

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    path_version_id = Column(String, ForeignKey("path_versions.id"), nullable=False, index=True)
    concept_id = Column(String, ForeignKey("concepts.id"), nullable=False, index=True)
    concept_slug = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    objective = Column(Text, nullable=False)
    objective_hash = Column(String, nullable=False)
    external_prerequisites = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    opens_from = Column(Text, nullable=True)
    must_establish = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    exclusions = Column(JSON_DOCUMENT_TYPE, nullable=False, default=list)
    primary_knowledge_type = Column(String, nullable=False)
    secondary_demand = Column(String, nullable=True)
    knowledge_type_source = Column(String, nullable=False, default="path_planner")
    merge_warning = Column(Boolean, nullable=False, default=False)
    position = Column(Integer, nullable=False)
    source = Column(String, nullable=False, default="path_planner")
    teacher_edited = Column(Boolean, nullable=False, default=False)
    skipped = Column(Boolean, nullable=False, default=False)
    revision = Column(Integer, nullable=False, default=1)
    pack_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    path_version = relationship("PathVersionModel", back_populates="lessons")
    concept = relationship("ConceptModel", back_populates="path_lessons")
    prerequisite_links = relationship(
        "PathLessonPrerequisiteModel",
        foreign_keys="PathLessonPrerequisiteModel.path_lesson_id",
        cascade="all, delete-orphan",
    )


class PathLessonPrerequisiteModel(Base):
    __tablename__ = "path_lesson_prerequisites"

    path_lesson_id = Column(
        String,
        ForeignKey("path_lessons.id"),
        primary_key=True,
    )
    prerequisite_lesson_id = Column(
        String,
        ForeignKey("path_lessons.id"),
        primary_key=True,
    )


class PackItemModel(Base):
    __tablename__ = "pack_items"

    id = Column(String, primary_key=True)
    pack_id = Column(String, nullable=False, index=True)
    card_id = Column(String, ForeignKey("concept_cards.id"), nullable=False, index=True)
    stem = Column(Text, nullable=False)
    options = Column(JSON_DOCUMENT_TYPE, nullable=False)
    correct_key = Column(String, nullable=False)
    diagnoses = Column(JSON_DOCUMENT_TYPE, nullable=False, default=dict)
    stale = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    card = relationship("ConceptCardModel", back_populates="items")


class LLMCallModel(Base):
    __tablename__ = "llm_calls"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    trace_id = Column(String, nullable=False, index=True)
    generation_id = Column(String, nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    caller = Column(String, nullable=False, index=True)
    node = Column(String, nullable=False, index=True)
    slot = Column(String, nullable=False, index=True)
    family = Column(String, nullable=True, index=True)
    model_name = Column(String, nullable=True, index=True)
    endpoint_host = Column(String, nullable=True, index=True)
    section_id = Column(String, nullable=True, index=True)
    attempt = Column(Integer, nullable=False)
    status = Column(String, nullable=False, index=True)
    retryable = Column(Boolean, nullable=True)
    latency_ms = Column(Float, nullable=True)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    thinking_tokens = Column(Integer, nullable=True)
    cost_usd = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    user = relationship("UserModel", back_populates="llm_calls")


class LessonShareModel(Base):
    """Read-only public share of a Lesson Builder document (Phase 7)."""

    __tablename__ = "lesson_shares"

    id = Column(String, primary_key=True)
    document_json = Column(JSON_DOCUMENT_TYPE, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)
    allow_download = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)


class EditableLessonModel(Base):
    """Teacher-owned lesson workspace persisted for the Builder."""

    __tablename__ = "editable_lessons"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    source_generation_id = Column(String, nullable=True)
    source_type = Column(String, nullable=False, default="manual", server_default="manual")
    title = Column(String, nullable=False, default="Untitled lesson", server_default="Untitled lesson")
    class_label = Column(String, nullable=True)
    document_json = Column(JSON_DOCUMENT_TYPE, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    user = relationship("UserModel", back_populates="editable_lessons")


class V3TraceRunModel(Base):
    """One row per V3 studio session. Bound to generation_id once started."""

    __tablename__ = "v3_trace_runs"

    trace_id = Column(String, primary_key=True)
    generation_id = Column(String, nullable=True, index=True, unique=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    template_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending", index=True)
    report_json = Column(JSON_DOCUMENT_TYPE, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    events = relationship(
        "V3TraceEventModel",
        back_populates="run",
        order_by="V3TraceEventModel.sequence",
    )


class V3TraceEventModel(Base):
    """Append-only actionable events for a V3 trace run."""

    __tablename__ = "v3_trace_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String, ForeignKey("v3_trace_runs.trace_id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    phase = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    payload = Column(JSON_DOCUMENT_TYPE, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    run = relationship("V3TraceRunModel", back_populates="events")
