"""Admit durable section-composer work from verified semantic inputs.

This adapter continues an already admitted SharedDocument Run.  It derives
every composer payload from the approved Teaching Plan and the active,
revision-bound sourcebook/task WorkItems; callers cannot substitute task or
source projections.
"""

from __future__ import annotations

import inspect

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.shared_tasks.models import SharedTaskSpec
from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.runtime import (
    _COMPOSER_DEFINITION,
    TeachingPlanSource,
    _section_payload,
    _section_tasks,
    _stable_hash,
    verify_teaching_plan_source,
)
from document.shared_lesson.section_sources import SectionSourceError, build_section_sources
from document.shared_lesson.semantic_inputs import (
    SemanticInputError,
    load_verified_semantic_inputs,
)
from document.shared_lesson.writer import SectionSource
from infra.generation_runtime.contracts import SourceIdentity, WorkItemAdmission
from infra.generation_runtime.repository import (
    SourceVerifier,
    add_work_item,
)


class ComposerAdmissionError(ValueError):
    """Composer admission inputs cannot be proven from durable state."""


class ComposerSectionAdmission(BaseModel):
    """Immutable inputs and identity for one admitted composer WorkItem."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: TeachingPlanSection
    tasks: tuple[SharedTaskSpec, ...] = ()
    sources: tuple[SectionSource, ...] = ()
    work_item_id: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


async def _verify_source(
    session: AsyncSession,
    *,
    source: TeachingPlanSource,
    source_verifier: SourceVerifier,
) -> SourceIdentity:
    expected = verify_teaching_plan_source(source)
    try:
        observed = source_verifier(session, expected)
        if inspect.isawaitable(observed):
            observed = await observed
    except Exception as exc:
        raise ComposerAdmissionError("approved Teaching Plan source could not be verified") from exc
    if not isinstance(observed, SourceIdentity) or observed != expected:
        raise ComposerAdmissionError(
            "approved Teaching Plan source verifier did not return the exact admitted identity"
        )
    return expected


async def admit_composer_work_items(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    source_verifier: SourceVerifier,
    max_attempts: int = 3,
) -> tuple[ComposerSectionAdmission, ...]:
    """Admit one composer WorkItem per approved section onto ``run_id``.

    The function never creates a Run and never accepts caller-supplied task or
    source projections.  Repeated admission is idempotent through the generic
    WorkItem identity check; changed payload identity remains a conflict.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if not owner_user_id.strip() or not run_id.strip():
        raise ValueError("run_id and owner_user_id must be non-empty")

    await _verify_source(
        session,
        source=source,
        source_verifier=source_verifier,
    )
    try:
        semantic_inputs = await load_verified_semantic_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
    except SemanticInputError as exc:
        raise ComposerAdmissionError(
            "durable sourcebook and shared-task inputs could not be verified"
        ) from exc

    if semantic_inputs.source != source:
        raise ComposerAdmissionError("durable semantic inputs differ from the admitted source")
    definition_hash = _stable_hash(_COMPOSER_DEFINITION)
    admitted: list[ComposerSectionAdmission] = []
    for section in source.plan.sections:
        task_slice = _section_tasks(section, semantic_inputs.tasks)
        try:
            sources = build_section_sources(semantic_inputs, section)
        except SectionSourceError as exc:
            raise ComposerAdmissionError(
                f"section {section.slot_id!r} source projection could not be verified"
            ) from exc
        payload = _section_payload(section=section, tasks=task_slice, sources=sources)
        input_hash = _stable_hash(payload)
        item = await add_work_item(
            session,
            WorkItemAdmission(
                run_id=run_id,
                item_key=f"compose:{section.slot_id}",
                stage="section_composition",
                input_hash=input_hash,
                definition_hash=definition_hash,
                max_attempts=max_attempts,
            ),
        )
        admitted.append(
            ComposerSectionAdmission(
                section=section,
                tasks=task_slice,
                sources=sources,
                work_item_id=item.record.id,
                input_hash=input_hash,
                definition_hash=definition_hash,
            )
        )
    return tuple(admitted)


__all__ = ["ComposerAdmissionError", "ComposerSectionAdmission", "admit_composer_work_items"]
