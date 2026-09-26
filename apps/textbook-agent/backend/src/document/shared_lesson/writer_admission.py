"""Admit durable section-writer work onto an existing SharedDocument Run.

Writer admission is a trust boundary between accepted composer output and the
provider worker.  It reloads the approved semantic inputs and current composer
leaves from the Run, derives each writer request from those durable values, and
then uses the generic writer admission primitive without creating another Run.
"""

from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.composer import (
    CompositionValidationError,
    SectionCompositionPlan,
    validate_composition_plan,
)
from document.shared_lesson.runtime import (
    _COMPOSER_DEFINITION,
    _WRITER_DEFINITION,
    TeachingPlanSource,
    _section_payload,
    _section_tasks,
    _stable_hash,
    admit_writer_work_item,
    make_section_writer_request,
    verify_teaching_plan_source,
)
from document.shared_lesson.section_sources import SectionSourceError, build_section_sources
from document.shared_lesson.semantic_inputs import (
    SemanticInputError,
    VerifiedSemanticInputs,
    load_verified_semantic_inputs,
)
from document.shared_lesson.writer import SectionSource, SectionWriterRequest
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.contracts import SourceIdentity
from infra.generation_runtime.repository import (
    SourceVerifier,
    active_work_items,
    get_run_status,
)

_COMPOSER_STAGE = "section_composition"


class WriterAdmissionError(ValueError):
    """Writer admission inputs cannot be proven from durable state."""


class WriterSectionAdmission(BaseModel):
    """Immutable writer request and WorkItem identity for one section."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: TeachingPlanSection
    request: SectionWriterRequest
    work_item_id: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    definition_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    composition_identity: str = Field(pattern=r"^[0-9a-f]{64}$")


async def _verify_source(
    session: AsyncSession,
    *,
    source: TeachingPlanSource,
    source_verifier: SourceVerifier,
) -> SourceIdentity:
    try:
        expected = verify_teaching_plan_source(source)
        observed = source_verifier(session, expected)
        if inspect.isawaitable(observed):
            observed = await observed
    except Exception as exc:
        raise WriterAdmissionError("approved Teaching Plan source could not be verified") from exc
    if not isinstance(observed, SourceIdentity) or observed != expected:
        raise WriterAdmissionError(
            "approved Teaching Plan source verifier did not return the exact admitted identity"
        )
    return expected


def _fail(message: str) -> None:
    raise WriterAdmissionError(message)


def _assert_active_chain(
    items: tuple[Any, ...],
    active: tuple[Any, ...],
    *,
    run_id: str,
) -> None:
    ids = {item.id for item in items}
    active_ids = {item.id for item in active}
    if len(ids) != len(items) or len(active_ids) != len(active):
        _fail("composer WorkItem identities are not unique")
    active_physical_keys = [item.item_key for item in active]
    if len(active_physical_keys) != len(set(active_physical_keys)):
        _fail("duplicate active composer WorkItem key")
    for item in items:
        if item.run_id != run_id:
            _fail("composer WorkItem belongs to a different Run")
        predecessor_id = item.replaces_work_item_id
        if predecessor_id is None:
            continue
        if predecessor_id not in ids:
            _fail("composer WorkItem replacement predecessor is missing")
        if predecessor_id == item.id or predecessor_id in active_ids:
            _fail("composer WorkItem replacement chain is invalid")


def _root_key(item: Any, by_id: Mapping[str, Any]) -> str:
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            _fail("composer WorkItem replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            _fail("composer WorkItem replacement predecessor is missing")
        current = predecessor
    return current.item_key


def _load_composer_leaves(
    run: Any,
    *,
    source: TeachingPlanSource,
    semantic_inputs: VerifiedSemanticInputs,
) -> dict[str, tuple[SectionCompositionPlan, str]]:
    """Validate and return the current accepted composition for each section."""

    all_items = tuple(run.work_items)
    active = tuple(active_work_items(all_items))
    _assert_active_chain(all_items, active, run_id=run.id)
    by_id = {item.id: item for item in all_items}
    composer_by_key: dict[str, Any] = {}
    for item in active:
        logical_key = _root_key(item, by_id)
        if not logical_key.startswith("compose:"):
            continue
        if logical_key in composer_by_key:
            _fail(f"duplicate active composer WorkItem {logical_key!r}")
        composer_by_key[logical_key] = item

    expected_keys = {f"compose:{section.slot_id}" for section in source.plan.sections}
    if set(composer_by_key) != expected_keys:
        missing = sorted(expected_keys - set(composer_by_key))
        extra = sorted(set(composer_by_key) - expected_keys)
        _fail(f"composer WorkItem set mismatch; missing={missing!r}, extra={extra!r}")

    result: dict[str, tuple[SectionCompositionPlan, str]] = {}
    definition_hash = _stable_hash(_COMPOSER_DEFINITION)
    for section in source.plan.sections:
        item = composer_by_key[f"compose:{section.slot_id}"]
        if item.stage != _COMPOSER_STAGE:
            _fail(f"composer WorkItem for {section.slot_id!r} has an invalid stage")
        task_slice = _section_tasks(section, semantic_inputs.tasks)
        try:
            sources = build_section_sources(semantic_inputs, section)
        except SectionSourceError as exc:
            raise WriterAdmissionError(
                f"section {section.slot_id!r} source projection could not be verified"
            ) from exc
        expected_input_hash = _stable_hash(
            _section_payload(section=section, tasks=task_slice, sources=sources)
        )
        if item.input_hash != expected_input_hash:
            _fail(f"composer WorkItem for {section.slot_id!r} has stale input identity")
        if item.definition_hash != definition_hash:
            _fail(f"composer WorkItem for {section.slot_id!r} has a stale definition")
        if item.composition_identity is not None:
            _fail(f"composer WorkItem for {section.slot_id!r} has an invalid composition identity")
        if item.status != "ready":
            _fail(f"composer WorkItem for {section.slot_id!r} is not ready")
        if item.output_json is None or not item.output_hash:
            _fail(f"composer WorkItem for {section.slot_id!r} has no complete output")
        if content_hash(item.output_json) != item.output_hash:
            _fail(f"composer WorkItem for {section.slot_id!r} output hash is invalid")
        try:
            composition = SectionCompositionPlan.model_validate(item.output_json)
            validate_composition_plan(
                plan=composition,
                section=section,
                tasks=task_slice,
            )
        except (CompositionValidationError, TypeError, ValueError) as exc:
            raise WriterAdmissionError(
                f"composer output for section {section.slot_id!r} is invalid"
            ) from exc
        if composition.section_slot_id != section.slot_id:
            _fail(f"composer output for section {section.slot_id!r} has the wrong section")
        result[section.slot_id] = (composition, item.id)
    return result


async def admit_writer_work_items(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    source_verifier: SourceVerifier,
    max_attempts: int = 3,
) -> tuple[WriterSectionAdmission, ...]:
    """Admit one writer WorkItem per approved section onto an existing Run."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if not owner_user_id.strip() or not run_id.strip():
        raise ValueError("run_id and owner_user_id must be non-empty")

    await _verify_source(session, source=source, source_verifier=source_verifier)
    try:
        semantic_inputs = await load_verified_semantic_inputs(
            session,
            run_id=run_id,
            owner_user_id=owner_user_id,
            source=source,
        )
    except SemanticInputError as exc:
        raise WriterAdmissionError(
            "durable sourcebook and shared-task inputs could not be verified"
        ) from exc
    if semantic_inputs.source != source:
        _fail("durable semantic inputs differ from the admitted source")

    run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
    if run is None:
        _fail("SharedDocument Run is unavailable for this owner")
    if run.run_type != "shared_document":
        _fail("writer admission requires a SharedDocument Run")
    compositions = _load_composer_leaves(
        run,
        source=source,
        semantic_inputs=semantic_inputs,
    )
    expected_writer_definition_hash = _stable_hash(_WRITER_DEFINITION)
    admitted: list[WriterSectionAdmission] = []
    for section in source.plan.sections:
        composition, _composer_id = compositions[section.slot_id]
        task_slice = _section_tasks(section, semantic_inputs.tasks)
        try:
            sources: tuple[SectionSource, ...] = tuple(
                build_section_sources(semantic_inputs, section)
            )
            request = make_section_writer_request(
                section=section,
                composition=composition,
                tasks=task_slice,
                sources=sources,
            )
        except (SectionSourceError, TypeError, ValueError) as exc:
            raise WriterAdmissionError(
                f"writer request for section {section.slot_id!r} is invalid"
            ) from exc
        record = await admit_writer_work_item(
            session,
            run_id=run_id,
            section=section,
            request=request,
            max_attempts=max_attempts,
        )
        if record.definition_hash != expected_writer_definition_hash:
            _fail(f"writer WorkItem for {section.slot_id!r} has an invalid definition")
        admitted.append(
            WriterSectionAdmission(
                section=section,
                request=request,
                work_item_id=record.id,
                input_hash=record.input_hash,
                definition_hash=record.definition_hash,
                composition_identity=record.composition_identity,
            )
        )
    return tuple(admitted)


__all__ = ["WriterAdmissionError", "WriterSectionAdmission", "admit_writer_work_items"]
