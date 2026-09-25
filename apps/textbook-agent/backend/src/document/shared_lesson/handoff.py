"""Pure handoff from accepted section work to a SharedLessonDocument.

The handoff is the trust boundary between section composition/writing and
durable document readiness.  It accepts only an approved Teaching Plan source,
revalidates every composer output against that source, assembles the accepted
sections deterministically, and then runs the existing deterministic-first
document semantic QA gate.  It deliberately has no persistence or media
side-effects; a caller can persist the returned evidence only after the
separate media and repository gates have passed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.assembly import (
    SharedLessonAssemblyError,
    assemble_shared_lesson_document,
)
from document.shared_lesson.composer import (
    CompositionValidationError,
    SectionCompositionPlan,
    validate_composition_plan,
)
from document.shared_lesson.continuity import ExpectedNodeShape
from document.shared_lesson.document_semantic import (
    DocumentSemanticQAResult,
    DocumentSemanticValidator,
    qa_shared_lesson_document_semantics,
)
from document.shared_lesson.models import SharedLessonDocument, SharedProvenance, SharedSection
from document.shared_lesson.qa import DocumentQAResult
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    verify_teaching_plan_source,
)


class SharedLessonHandoffError(ValueError):
    """Accepted handoff inputs cannot form a trusted document boundary."""


class _FrozenShapes(dict[str, tuple[ExpectedNodeShape, ...]]):
    """Small immutable mapping used inside the closed evidence model."""

    def _immutable(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("shared lesson handoff evidence is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class SharedLessonHandoffEvidence(BaseModel):
    """Closed, lineage-bound output for the later READY promotion gate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    status: Literal["ready", "blocked"]
    document: SharedLessonDocument
    deterministic_qa: DocumentQAResult
    semantic_qa: DocumentSemanticQAResult
    expected_shapes: dict[str, tuple[ExpectedNodeShape, ...]]
    teaching_plan_id: str = Field(min_length=1)
    teaching_plan_revision: int = Field(ge=1)
    teaching_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_evidence(self) -> SharedLessonHandoffEvidence:
        if self.document.teaching_plan_id != self.teaching_plan_id:
            raise ValueError("handoff source ID does not match the document")
        if self.document.teaching_plan_revision != self.teaching_plan_revision:
            raise ValueError("handoff source revision does not match the document")
        if self.document.teaching_plan_hash != self.teaching_plan_hash:
            raise ValueError("handoff source hash does not match the document")
        if self.deterministic_qa.document_id != self.document.id:
            raise ValueError("deterministic QA identity does not match the document")
        if self.deterministic_qa.document_revision != self.document.revision:
            raise ValueError("deterministic QA revision does not match the document")
        if self.semantic_qa.document_id != self.document.id:
            raise ValueError("semantic QA identity does not match the document")
        if self.semantic_qa.document_revision != self.document.revision:
            raise ValueError("semantic QA revision does not match the document")
        if self.semantic_qa.document_hash != self.document.content_hash:
            raise ValueError("semantic QA hash does not match the document")
        expected_ids = {section.id for section in self.document.sections}
        if set(self.expected_shapes) != expected_ids:
            raise ValueError("handoff expected shapes must cover exactly the document sections")
        if self.status == "ready" and not (self.deterministic_qa.ready and self.semantic_qa.passed):
            raise ValueError("a ready handoff requires deterministic and semantic QA to pass")
        if self.status == "blocked" and self.deterministic_qa.ready and self.semantic_qa.passed:
            raise ValueError("a passing handoff cannot be marked blocked")
        object.__setattr__(self, "expected_shapes", _FrozenShapes(self.expected_shapes))
        return self

    @property
    def ready(self) -> bool:
        """Whether this evidence may proceed to the separate READY gate."""
        return self.status == "ready"


def _normalize_by_identity(
    value: Mapping[str, Any] | Sequence[Any],
    *,
    expected_ids: tuple[str, ...],
    value_name: str,
    identity_attribute: str,
) -> dict[str, Any]:
    """Normalize ordered or mapping inputs and reject identity forgery."""
    expected = set(expected_ids)
    if isinstance(value, Mapping):
        supplied: dict[str, Any] = {}
        for key, item in value.items():
            identity = str(key)
            if identity in supplied:
                raise SharedLessonHandoffError(f"duplicate {value_name} identity {identity!r}")
            supplied[identity] = item
    else:
        supplied = {}
        for item in value:
            identity = getattr(item, identity_attribute, None)
            if not isinstance(identity, str) or not identity:
                raise SharedLessonHandoffError(f"{value_name} item has no valid identity")
            if identity in supplied:
                raise SharedLessonHandoffError(f"duplicate {value_name} identity {identity!r}")
            supplied[identity] = item

    missing = expected - set(supplied)
    extra = set(supplied) - expected
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing {value_name}: {sorted(missing)!r}")
        if extra:
            details.append(f"unplanned {value_name}: {sorted(extra)!r}")
        raise SharedLessonHandoffError("; ".join(details))
    if isinstance(value, Mapping):
        for identity in expected_ids:
            item_identity = getattr(supplied[identity], identity_attribute, None)
            if item_identity != identity:
                raise SharedLessonHandoffError(
                    f"{value_name} key {identity!r} does not match item identity {item_identity!r}"
                )
    return {identity: supplied[identity] for identity in expected_ids}


def _section_tasks(
    section: TeachingPlanSection, tasks: Sequence[SharedTaskSpec]
) -> tuple[SharedTaskSpec, ...]:
    block_ids = {block.id for block in section.blocks}
    return tuple(task for task in tasks if task.teaching_block_id in block_ids)


def _expected_shapes(plan: SectionCompositionPlan) -> tuple[ExpectedNodeShape, ...]:
    return tuple(
        ExpectedNodeShape(
            id=item.id,
            kind=item.kind,
            teaching_block_id=item.teaching_block_id,
            semantic_role=item.semantic_role,
            task_spec_id=item.task_spec_id,
        )
        for item in plan.items
    )


def _coerce_composition(value: Any, section_id: str) -> SectionCompositionPlan:
    try:
        plan = (
            value
            if isinstance(value, SectionCompositionPlan)
            else SectionCompositionPlan.model_validate(value)
        )
    except (TypeError, ValueError) as exc:
        raise SharedLessonHandoffError(
            f"composition for section {section_id!r} violates its closed schema"
        ) from exc
    if plan.section_slot_id != section_id:
        raise SharedLessonHandoffError(
            f"composition key {section_id!r} does not match section_slot_id {plan.section_slot_id!r}"
        )
    return plan


def _coerce_section(value: Any, section_id: str) -> SharedSection:
    try:
        section = value if isinstance(value, SharedSection) else SharedSection.model_validate(value)
    except (TypeError, ValueError) as exc:
        raise SharedLessonHandoffError(
            f"accepted section {section_id!r} violates the closed SharedSection schema"
        ) from exc
    if section.id != section_id:
        raise SharedLessonHandoffError(
            f"section key {section_id!r} does not match section id {section.id!r}"
        )
    return section


async def handoff_accepted_sections_to_document(
    *,
    source: TeachingPlanSource,
    compositions: Mapping[str, SectionCompositionPlan] | Sequence[SectionCompositionPlan],
    sections: Mapping[str, SharedSection] | Sequence[SharedSection],
    tasks: Sequence[SharedTaskSpec] = (),
    document_id: str,
    document_revision: int,
    created_at: datetime | str,
    provenance: SharedProvenance | Mapping[str, Any] | None = None,
    approved_source_ids: Sequence[str] = (),
    source_facts_by_section: Mapping[str, Sequence[str]] | None = None,
    required_media_by_section: Mapping[str, Sequence[str]] | None = None,
    available_media_ids: Sequence[str] = (),
    expected_title: str | None = None,
    expected_content_hash: str | None = None,
    semantic_validator: DocumentSemanticValidator | None = None,
) -> SharedLessonHandoffEvidence:
    """Validate accepted section contracts, assemble, and run semantic QA.

    Composer and writer outputs are never repaired here.  A forged or
    incomplete composer plan is an input contract failure; a semantic issue
    produces blocked evidence while preserving the immutable accepted document
    for a targeted correction at the owning work item.
    """
    try:
        identity = verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SharedLessonHandoffError(str(exc)) from exc

    plan_sections = tuple(source.plan.sections)
    section_ids = tuple(section.slot_id for section in plan_sections)
    if not section_ids:
        raise SharedLessonHandoffError("approved Teaching Plan has no sections")

    raw_compositions = _normalize_by_identity(
        compositions,
        expected_ids=section_ids,
        value_name="composition",
        identity_attribute="section_slot_id",
    )
    raw_sections = _normalize_by_identity(
        sections,
        expected_ids=section_ids,
        value_name="accepted section",
        identity_attribute="id",
    )
    try:
        composition_by_section = {
            section_id: _coerce_composition(raw_compositions[section_id], section_id)
            for section_id in section_ids
        }
        section_by_id = {
            section_id: _coerce_section(raw_sections[section_id], section_id)
            for section_id in section_ids
        }
    except SharedLessonHandoffError:
        raise

    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise SharedLessonHandoffError("SharedTaskSpec IDs must be unique")
    planned_blocks = {block.id for section in plan_sections for block in section.blocks}
    unknown_tasks = sorted(
        task.id for task in tasks if task.teaching_block_id not in planned_blocks
    )
    if unknown_tasks:
        raise SharedLessonHandoffError(
            f"SharedTaskSpec items belong to unplanned Teaching Plan blocks: {unknown_tasks!r}"
        )

    expected_shapes: dict[str, tuple[ExpectedNodeShape, ...]] = {}
    for plan_section in plan_sections:
        section_tasks = _section_tasks(plan_section, tasks)
        try:
            validate_composition_plan(
                plan=composition_by_section[plan_section.slot_id],
                section=plan_section,
                tasks=section_tasks,
            )
        except CompositionValidationError as exc:
            raise SharedLessonHandoffError(
                f"accepted composition for section {plan_section.slot_id!r} is not valid: {exc}"
            ) from exc
        expected_shapes[plan_section.slot_id] = _expected_shapes(
            composition_by_section[plan_section.slot_id]
        )

    try:
        assembly = assemble_shared_lesson_document(
            document_id=document_id,
            revision=document_revision,
            source=source,
            accepted_sections=section_by_id,
            tasks=tasks,
            provenance=provenance,
            created_at=created_at,
            expected_shapes=expected_shapes,
            expected_title=expected_title,
            approved_source_ids=approved_source_ids,
            source_facts_by_section=source_facts_by_section,
            required_media_by_section=required_media_by_section,
            available_media_ids=available_media_ids,
            expected_content_hash=expected_content_hash,
        )
    except SharedLessonAssemblyError as exc:
        raise SharedLessonHandoffError(str(exc)) from exc

    semantic = await qa_shared_lesson_document_semantics(
        document=assembly.document,
        teaching_plan_sections=plan_sections,
        deterministic=assembly.qa,
        semantic_validator=semantic_validator,
    )
    if (
        semantic.document_id != assembly.document.id
        or semantic.document_revision != assembly.document.revision
        or semantic.document_hash != assembly.document.content_hash
    ):
        raise SharedLessonHandoffError("semantic QA evidence is stale for the assembled document")

    status: Literal["ready", "blocked"] = (
        "ready" if assembly.ready and semantic.passed else "blocked"
    )
    return SharedLessonHandoffEvidence(
        status=status,
        document=assembly.document,
        deterministic_qa=assembly.qa,
        semantic_qa=semantic,
        expected_shapes=expected_shapes,
        teaching_plan_id=identity.source_artifact_id,
        teaching_plan_revision=identity.source_revision,
        teaching_plan_hash=identity.source_hash,
    )


__all__ = [
    "SharedLessonHandoffError",
    "SharedLessonHandoffEvidence",
    "handoff_accepted_sections_to_document",
]
