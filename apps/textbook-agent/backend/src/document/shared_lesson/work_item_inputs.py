"""Read-only trust boundary for accepted SharedDocument section work.

The generic runtime persists composer and writer outputs as JSON work-item
results.  This module turns one owner-scoped run back into the closed inputs
needed by the pure handoff function.  It deliberately performs no writes and
does not accept caller supplied expected shapes: the approved Teaching Plan
and the durable work-item keys are the authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.shared_tasks.models import SharedTaskSpec
from document.shared_lesson.composer import (
    CompositionValidationError,
    SectionCompositionPlan,
    validate_composition_plan,
)
from document.shared_lesson.models import SharedSection
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    _stable_hash,
    make_section_writer_request,
    verify_teaching_plan_source,
)
from document.shared_lesson.writer import (
    SectionSource,
    ordinary_nodes_as_draft,
    SectionWriteResult,
    SectionWriteValidationError,
    validate_and_build_section,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime.repository import active_work_items, get_run_status


class SharedLessonInputError(ValueError):
    """Durable section inputs cannot be trusted for a handoff."""


class _FrozenMap(dict[str, str]):
    """Keep hash and work-item identity maps immutable after validation."""

    def _immutable(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("verified shared lesson inputs are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class VerifiedSharedLessonInputs(BaseModel):
    """Closed, lineage-bound section inputs for pure document handoff."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    source: TeachingPlanSource
    source_artifact_type: Literal["teaching_plan"] = "teaching_plan"
    source_artifact_id: str = Field(min_length=1)
    source_revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    compositions: tuple[SectionCompositionPlan, ...] = Field(min_length=1)
    sections: tuple[SharedSection, ...] = Field(min_length=1)
    composition_hashes: dict[str, str]
    section_hashes: dict[str, str]
    work_item_ids: dict[str, str]
    #: Soft-issue (code, sanitized path) warnings the writer accepted on its
    #: final bounded attempt for each section, keyed by section slot ID. Empty
    #: for a section whose writer output carried no warnings. Never provider
    #: output or learner text -- see ``writer.SOFT_SECTION_WRITE_ISSUE_CODES``.
    section_warnings: dict[str, tuple[tuple[str, str], ...]] = Field(default_factory=dict)
    #: Composer shape findings are persisted independently so they can be
    #: surfaced as advisory quality flags without entering semantic review.
    composition_warnings: dict[str, tuple[tuple[str, str], ...]] = Field(
        default_factory=dict, exclude_if=lambda value: not value
    )

    @model_validator(mode="after")
    def _bind_and_freeze(self) -> VerifiedSharedLessonInputs:
        source_identity = (
            self.source.id,
            self.source.revision,
            self.source.content_hash,
        )
        if (
            self.source_artifact_id,
            self.source_revision,
            self.source_hash,
        ) != source_identity:
            raise ValueError("verified input source identity differs from its approved source")
        section_ids = tuple(section.slot_id for section in self.source.plan.sections)
        if tuple(composition.section_slot_id for composition in self.compositions) != section_ids:
            raise ValueError("verified compositions must follow approved Teaching Plan order")
        if tuple(section.id for section in self.sections) != section_ids:
            raise ValueError("verified sections must follow approved Teaching Plan order")
        expected_keys = {
            key
            for section_id in section_ids
            for key in (f"compose:{section_id}", f"write:{section_id}")
        }
        for name, value in (
            ("composition_hashes", self.composition_hashes),
            ("section_hashes", self.section_hashes),
        ):
            if set(value) != set(section_ids):
                raise ValueError(f"{name} must cover every approved section exactly once")
        if set(self.work_item_ids) != expected_keys:
            raise ValueError("work_item_ids must cover the exact compose/write work-item keys")
        if set(self.section_warnings) - set(section_ids):
            raise ValueError("section_warnings must only name approved sections")
        if set(self.composition_warnings) - set(section_ids):
            raise ValueError("composition_warnings must only name approved sections")
        object.__setattr__(self, "composition_hashes", _FrozenMap(self.composition_hashes))
        object.__setattr__(self, "section_hashes", _FrozenMap(self.section_hashes))
        object.__setattr__(self, "work_item_ids", _FrozenMap(self.work_item_ids))
        object.__setattr__(self, "section_warnings", _FrozenMap(self.section_warnings))
        object.__setattr__(self, "composition_warnings", _FrozenMap(self.composition_warnings))
        return self


def _fail(message: str) -> None:
    raise SharedLessonInputError(message)


def _section_tasks(
    section: Any,
    tasks: Sequence[SharedTaskSpec],
) -> tuple[SharedTaskSpec, ...]:
    block_ids = {block.id for block in section.blocks}
    return tuple(task for task in tasks if task.teaching_block_id in block_ids)


def _assert_active_chain(items: Sequence[Any], active: Sequence[Any], run_id: str) -> None:
    """Reject malformed replacement chains before interpreting any output."""
    all_ids = {item.id for item in items}
    active_ids = {item.id for item in active}
    if len(active_ids) != len(active):
        _fail("shared lesson run has duplicate active work-item identities")
    active_keys = [item.item_key for item in active]
    if len(active_keys) != len(set(active_keys)):
        _fail("shared lesson run has duplicate active work-item keys")
    for item in items:
        if item.run_id != run_id:
            _fail("shared lesson work item belongs to a different run")
        predecessor_id = item.replaces_work_item_id
        if predecessor_id is None:
            continue
        if predecessor_id not in all_ids:
            _fail("shared lesson work item replaces a missing predecessor")
        if predecessor_id == item.id or predecessor_id in active_ids:
            _fail("shared lesson work item has an invalid active replacement chain")


def _logical_item_key(item: Any, by_id: Mapping[str, Any]) -> str:
    """Resolve a replacement leaf to the stable logical key it supersedes."""
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            _fail("shared lesson work-item replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            _fail("shared lesson work item replaces a missing predecessor")
        current = predecessor
    return current.item_key


def _parse_output(item: Any, *, expected_key: str) -> tuple[Any, str]:
    if item.status != "ready":
        _fail(f"work item {expected_key!r} is not ready")
    if item.output_json is None or not item.output_hash:
        _fail(f"work item {expected_key!r} has no complete output")
    actual_hash = content_hash(item.output_json)
    if actual_hash != item.output_hash:
        _fail(f"work item {expected_key!r} output hash does not match its stored output")
    return item.output_json, actual_hash


def _parse_composition(
    item: Any,
    *,
    section: Any,
    tasks: Sequence[SharedTaskSpec],
) -> tuple[SectionCompositionPlan, str]:
    raw, output_hash = _parse_output(item, expected_key=f"compose:{section.slot_id}")
    try:
        composition = SectionCompositionPlan.model_validate(raw)
        validate_composition_plan(
            plan=composition,
            section=section,
            tasks=_section_tasks(section, tasks),
        )
    except (TypeError, ValueError, CompositionValidationError) as exc:
        raise SharedLessonInputError(
            f"composer output for section {section.slot_id!r} is stale or invalid"
        ) from exc
    if composition.section_slot_id != section.slot_id:
        _fail(f"composer output belongs to the wrong section {section.slot_id!r}")
    return composition, output_hash


def _parse_writer(
    item: Any,
    *,
    section: Any,
    composition: SectionCompositionPlan,
    tasks: Sequence[SharedTaskSpec],
    sources: Sequence[SectionSource],
    position: int,
) -> tuple[SharedSection, str, tuple[tuple[str, str], ...]]:
    raw, output_hash = _parse_output(item, expected_key=f"write:{section.slot_id}")
    # Writer admission hashes the closed composition with the runtime's
    # ensure_ascii=False canonicalizer; this is distinct from the persisted
    # output hash, which uses infra.execution.checkpoints.content_hash.
    expected_composition_hash = _stable_hash(composition.model_dump(mode="json"))
    if item.composition_identity != expected_composition_hash:
        _fail(f"writer output for section {section.slot_id!r} uses a stale composition")
    try:
        result = SectionWriteResult.model_validate(raw)
        request = make_section_writer_request(
            section=section,
            composition=composition,
            tasks=_section_tasks(section, tasks),
            sources=sources,
        )
        # ``accept_soft_issues=True`` reproduces an already-accepted section
        # deterministically: a HARD issue still fails this reload, but a SOFT
        # issue the writer's final attempt already accepted (and recorded as
        # a warning) must not fail durable reloads of that exact content.
        verified = validate_and_build_section(
            request=request,
            draft=ordinary_nodes_as_draft(result.nodes),
            accept_soft_issues=True,
        )
    except (TypeError, ValueError, SectionRuntimeError, SectionWriteValidationError) as exc:
        raise SharedLessonInputError(
            f"writer output for section {section.slot_id!r} is stale or invalid"
        ) from exc
    # Older accepted writer rows predate advisory shape warnings and may omit
    # ``warnings``. Preserve those rows while requiring every persisted
    # warning to be reproducible from the same immutable nodes.
    if (
        verified.section_slot_id != result.section_slot_id
        or verified.title != result.title
        or verified.nodes != result.nodes
        or any(warning not in verified.warnings for warning in result.warnings)
    ):
        _fail(f"writer output for section {section.slot_id!r} differs from its verified shape")
    return (
        result.as_shared_section(section_id=section.slot_id, position=position),
        output_hash,
        result.warnings,
    )


def _partition_section_sources(
    source: TeachingPlanSource,
    sources: Sequence[SectionSource],
) -> dict[str, tuple[SectionSource, ...]]:
    """Partition a verified source union into approved per-section slices."""

    by_id: dict[str, SectionSource] = {}
    for projected in sources:
        if projected.id in by_id:
            previous = by_id[projected.id]
            if previous != projected:
                _fail(f"sourcebook source {projected.id!r} has conflicting projections")
            _fail(f"sourcebook source {projected.id!r} is duplicated")
        by_id[projected.id] = projected

    section_refs: dict[str, tuple[str, ...]] = {}
    ordered_refs: list[str] = []
    for section in source.plan.sections:
        refs: list[str] = []
        seen: set[str] = set()
        for block in section.blocks:
            for ref in block.sourcebook_refs:
                if not isinstance(ref, str) or not ref.strip():
                    _fail(f"section {section.slot_id!r} contains an empty sourcebook reference")
                if ref in seen:
                    continue
                seen.add(ref)
                refs.append(ref)
                if ref not in ordered_refs:
                    ordered_refs.append(ref)
        section_refs[section.slot_id] = tuple(refs)

    missing = [ref for ref in ordered_refs if ref not in by_id]
    if missing:
        _fail(f"verified source union is missing sourcebook refs {missing!r}")
    expected = set(ordered_refs)
    unreferenced = [source_id for source_id in by_id if source_id not in expected]
    if unreferenced:
        _fail(f"verified source union has unreferenced source entries {unreferenced!r}")

    return {
        section_id: tuple(by_id[ref] for ref in refs) for section_id, refs in section_refs.items()
    }


async def load_verified_shared_lesson_inputs(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    tasks: Sequence[SharedTaskSpec] = (),
    sources: Sequence[SectionSource] = (),
) -> VerifiedSharedLessonInputs:
    """Load and verify accepted composer/writer leaves for one owner-scoped run.

    This is intentionally read-only.  It uses the approved source to derive
    expected section identities and deterministic shapes, then parses only the
    current active replacement leaves.  A replaced predecessor is retained as
    history and can never be mistaken for the accepted current output.
    """
    run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
    if run is None:
        _fail("shared lesson run is unavailable for this owner")
    try:
        source_identity = verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SharedLessonInputError("approved Teaching Plan source is invalid") from exc
    if run.run_type != "shared_document":
        _fail("run is not a SharedDocument generation run")
    if run.owner_user_id != owner_user_id:
        _fail("shared lesson run owner does not match the caller")
    persisted_identity = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    observed_identity = (
        source_identity.source_artifact_type,
        source_identity.source_artifact_id,
        source_identity.source_revision,
        source_identity.source_hash,
    )
    if persisted_identity != observed_identity:
        _fail("SharedDocument run source identity differs from the approved source")

    plan_sections = tuple(source.plan.sections)
    section_ids = tuple(section.slot_id for section in plan_sections)
    if not section_ids or len(section_ids) != len(set(section_ids)):
        _fail("approved Teaching Plan has invalid section identities")
    all_items = tuple(run.work_items)
    active = active_work_items(all_items)
    _assert_active_chain(all_items, active, run.id)
    all_items_by_id = {item.id: item for item in all_items}
    active_by_key: dict[str, Any] = {}
    for item in active:
        logical_key = _logical_item_key(item, all_items_by_id)
        # A SharedDocument run may also carry media, continuity, or QA work.
        # This loader owns only the compose/write leaves; the later finalizer
        # owns those other stages.
        if not logical_key.startswith(("compose:", "write:")):
            continue
        if logical_key in active_by_key:
            _fail(f"duplicate active work-item identity {logical_key!r}")
        active_by_key[logical_key] = item
    expected_keys = {
        key
        for section_id in section_ids
        for key in (f"compose:{section_id}", f"write:{section_id}")
    }
    if set(active_by_key) != expected_keys:
        missing = sorted(expected_keys - set(active_by_key))
        extra = sorted(set(active_by_key) - expected_keys)
        _fail(f"shared lesson work-item set mismatch; missing={missing!r}, extra={extra!r}")

    sources_by_section = _partition_section_sources(source, sources)

    compositions: list[SectionCompositionPlan] = []
    sections: list[SharedSection] = []
    composition_hashes: dict[str, str] = {}
    section_hashes: dict[str, str] = {}
    work_item_ids: dict[str, str] = {}
    section_warnings: dict[str, tuple[tuple[str, str], ...]] = {}
    composition_warnings: dict[str, tuple[tuple[str, str], ...]] = {}
    for position, section in enumerate(plan_sections):
        compose_item = active_by_key[f"compose:{section.slot_id}"]
        write_item = active_by_key[f"write:{section.slot_id}"]
        composition, composition_hash = _parse_composition(
            compose_item,
            section=section,
            tasks=tasks,
        )
        accepted_section, section_hash, warnings = _parse_writer(
            write_item,
            section=section,
            composition=composition,
            tasks=tasks,
            sources=sources_by_section[section.slot_id],
            position=position,
        )
        compositions.append(composition)
        sections.append(accepted_section)
        composition_hashes[section.slot_id] = composition_hash
        section_hashes[section.slot_id] = section_hash
        work_item_ids[f"compose:{section.slot_id}"] = compose_item.id
        work_item_ids[f"write:{section.slot_id}"] = write_item.id
        if warnings:
            section_warnings[section.slot_id] = warnings
        if composition.warnings:
            composition_warnings[section.slot_id] = composition.warnings

    return VerifiedSharedLessonInputs(
        run_id=run.id,
        owner_user_id=owner_user_id,
        source=source,
        source_artifact_id=source_identity.source_artifact_id,
        source_revision=source_identity.source_revision,
        source_hash=source_identity.source_hash,
        compositions=tuple(compositions),
        sections=tuple(sections),
        composition_hashes=composition_hashes,
        section_hashes=section_hashes,
        work_item_ids=work_item_ids,
        section_warnings=section_warnings,
        composition_warnings=composition_warnings,
    )


__all__ = [
    "SharedLessonInputError",
    "VerifiedSharedLessonInputs",
    "load_verified_shared_lesson_inputs",
]
