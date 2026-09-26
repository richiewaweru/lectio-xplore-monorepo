"""Durable sourcebook and shared-task inputs for SharedDocument generation.

Sourcebook content is the first semantic artifact in a SharedDocument run.
Shared tasks depend on the exact accepted sourcebook output, so a task item is
never admitted or loaded against a caller-supplied sourcebook snapshot.  This
module is deliberately a trust boundary: it validates the approved Teaching
Plan lineage, generic WorkItem identity, and closed semantic contracts before
the finalizer can use either output.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from curriculum.lesson_sourcebook import (
    LessonSourcebook,
    validate_sourcebook,
)
from curriculum.shared_tasks import SharedTaskSpec, finalize_shared_tasks
from curriculum.teaching_plan.compatibility import response_bearing_action
from document.shared_lesson.runtime import (
    SectionRuntimeError,
    TeachingPlanSource,
    _stable_hash,
    verify_teaching_plan_source,
)
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    AdmissionResult,
    SourceIdentity,
    WorkItemAdmission,
    active_work_items,
    add_work_item,
    get_run_status,
)

SOURCEBOOK_ITEM_KEY = "sourcebook"
TASK_ITEM_KEY = "shared_tasks"
SOURCEBOOK_STAGE = "sourcebook_generation"
TASK_STAGE = "shared_task_generation"
SOURCEBOOK_DEFINITION = "shared-lesson-sourcebook:v1"
TASK_DEFINITION = "shared-lesson-shared-tasks:v1"


class SemanticInputError(ValueError):
    """A semantic input is missing, stale, forged, or out of contract."""


class _FrozenMap(dict[str, str]):
    def _immutable(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("verified semantic inputs are immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class VerifiedSemanticInputs(BaseModel):
    """Closed, lineage-bound sourcebook and task outputs for finalization."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    source: TeachingPlanSource
    sourcebook: LessonSourcebook
    tasks: tuple[SharedTaskSpec, ...]
    sourcebook_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_item_ids: dict[str, str]

    def model_post_init(self, __context: Any, /) -> None:
        object.__setattr__(self, "work_item_ids", _FrozenMap(self.work_item_ids))


class VerifiedSourcebookInput(BaseModel):
    """Closed, lineage-bound sourcebook input for downstream authoring."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    owner_user_id: str = Field(min_length=1)
    source: TeachingPlanSource
    sourcebook: LessonSourcebook
    sourcebook_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    work_item_id: str = Field(min_length=1)


def _source_identity(source: TeachingPlanSource) -> SourceIdentity:
    try:
        return verify_teaching_plan_source(source)
    except SectionRuntimeError as exc:
        raise SemanticInputError("approved Teaching Plan source is invalid") from exc


def _approved_sourcebook_ids(source: TeachingPlanSource) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for section in source.plan.sections:
        for block in section.blocks:
            for ref in block.sourcebook_refs:
                if not isinstance(ref, str) or not ref.strip():
                    raise SemanticInputError("approved sourcebook refs must be non-empty")
                # A single approved source may support several blocks. Keep
                # the first-use order while requiring the generated sourcebook
                # to contain exactly one entry for each approved ID.
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
    return tuple(refs)


def _sourcebook_input_hash(source: TeachingPlanSource) -> str:
    return _stable_hash(
        {
            "source": {
                "type": "teaching_plan",
                "id": source.id,
                "revision": source.revision,
                "hash": source.content_hash,
            },
            "approved_sourcebook_refs": list(_approved_sourcebook_ids(source)),
        }
    )


def _task_input_hash(source: TeachingPlanSource, sourcebook_output_hash: str) -> str:
    return _stable_hash(
        {
            "source": {
                "type": "teaching_plan",
                "id": source.id,
                "revision": source.revision,
                "hash": source.content_hash,
            },
            "sourcebook_output_hash": sourcebook_output_hash,
        }
    )


async def _lock_owned_run(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: SourceIdentity,
) -> GenerationRunModel:
    run = await session.scalar(
        select(GenerationRunModel).where(GenerationRunModel.id == run_id).with_for_update()
    )
    if run is None or run.owner_user_id != owner_user_id:
        raise SemanticInputError("SharedDocument Run is unavailable to this owner")
    if run.run_type != "shared_document":
        raise SemanticInputError("semantic inputs require a SharedDocument Run")
    observed = (
        source.source_artifact_type,
        source.source_artifact_id,
        source.source_revision,
        source.source_hash,
    )
    persisted = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    if observed != persisted:
        raise SemanticInputError("semantic input source differs from the admitted Run")
    return run


def _root_key(item: GenerationWorkItemModel, by_id: Mapping[str, GenerationWorkItemModel]) -> str:
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise SemanticInputError("semantic WorkItem replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            raise SemanticInputError("semantic WorkItem replacement predecessor is missing")
        current = predecessor
    return current.item_key


def _active_semantic_items(
    items: Iterable[GenerationWorkItemModel],
) -> dict[str, GenerationWorkItemModel]:
    materialized = tuple(items)
    by_id = {item.id: item for item in materialized}
    if len(by_id) != len(materialized):
        raise SemanticInputError("semantic WorkItem identities are not unique")
    active = active_work_items(materialized)
    selected: dict[str, GenerationWorkItemModel] = {}
    for item in active:
        root = _root_key(item, by_id)
        if root not in {SOURCEBOOK_ITEM_KEY, TASK_ITEM_KEY}:
            continue
        if root in selected:
            raise SemanticInputError(f"duplicate active semantic WorkItem {root!r}")
        selected[root] = item
    return selected


def _assert_active_sourcebook_chain(
    items: Iterable[GenerationWorkItemModel],
    *,
    run_id: str,
) -> GenerationWorkItemModel:
    """Select exactly one current sourcebook leaf after validating all chains."""
    materialized = tuple(items)
    by_id = {item.id: item for item in materialized}
    if len(by_id) != len(materialized):
        raise SemanticInputError("semantic WorkItem identities are not unique")
    for item in materialized:
        if item.run_id != run_id:
            raise SemanticInputError("semantic WorkItem belongs to a different Run")

    active = active_work_items(materialized)
    if len({item.id for item in active}) != len(active):
        raise SemanticInputError("semantic WorkItem identities are not unique")
    active_keys = [item.item_key for item in active]
    if len(active_keys) != len(set(active_keys)):
        raise SemanticInputError("duplicate active semantic WorkItem")

    # Resolve every row so a malformed historical replacement cannot be hidden
    # behind an otherwise valid leaf.
    logical_keys = {item.id: _root_key(item, by_id) for item in materialized}
    sourcebook_leaves = [item for item in active if logical_keys[item.id] == SOURCEBOOK_ITEM_KEY]
    if not sourcebook_leaves:
        raise SemanticInputError("missing active semantic WorkItems: ['sourcebook']")
    if len(sourcebook_leaves) != 1:
        raise SemanticInputError("duplicate active semantic WorkItem 'sourcebook'")
    return sourcebook_leaves[0]


def _verify_work_item_output(
    item: GenerationWorkItemModel,
    *,
    expected_key: str,
) -> tuple[Any, str]:
    if item.item_key == "":
        raise SemanticInputError(f"{expected_key} WorkItem has no stable identity")
    if item.status != "ready":
        raise SemanticInputError(f"{expected_key} WorkItem is not ready")
    if item.output_json is None or not item.output_hash:
        raise SemanticInputError(f"{expected_key} WorkItem has no complete output")
    observed = content_hash(item.output_json)
    if observed != item.output_hash:
        raise SemanticInputError(f"{expected_key} WorkItem output hash does not match output")
    return item.output_json, observed


def _verify_sourcebook_work_item(
    item: GenerationWorkItemModel,
    *,
    source: TeachingPlanSource,
) -> tuple[LessonSourcebook, str]:
    raw, output_hash = _verify_work_item_output(item, expected_key=SOURCEBOOK_ITEM_KEY)
    if item.stage != SOURCEBOOK_STAGE:
        raise SemanticInputError("sourcebook WorkItem has an invalid stage")
    if item.input_hash != _sourcebook_input_hash(source):
        raise SemanticInputError("sourcebook WorkItem input identity is stale")
    if item.definition_hash != _stable_hash(SOURCEBOOK_DEFINITION):
        raise SemanticInputError("sourcebook WorkItem definition identity is stale")
    if item.composition_identity is not None:
        raise SemanticInputError("sourcebook WorkItem has an invalid composition identity")
    try:
        sourcebook = LessonSourcebook.model_validate(raw)
    except (TypeError, ValueError) as exc:
        raise SemanticInputError("sourcebook WorkItem output is malformed") from exc
    _validate_sourcebook(source, sourcebook)
    return sourcebook, output_hash


def _validate_sourcebook(
    source: TeachingPlanSource,
    sourcebook: LessonSourcebook,
) -> LessonSourcebook:
    approved_ids = _approved_sourcebook_ids(source)
    if (
        sourcebook.teaching_plan_id,
        sourcebook.teaching_plan_revision,
        sourcebook.teaching_plan_hash,
    ) != (source.id, source.revision, source.content_hash):
        raise SemanticInputError("sourcebook is bound to a different approved Teaching Plan")
    entry_ids = [entry.id for entry in sourcebook.entries]
    if len(entry_ids) != len(set(entry_ids)):
        raise SemanticInputError("sourcebook entry IDs must be unique")
    if tuple(entry_ids) != approved_ids:
        missing = sorted(set(approved_ids) - set(entry_ids))
        extra = sorted(set(entry_ids) - set(approved_ids))
        raise SemanticInputError(
            f"sourcebook entries do not match approved refs; missing={missing!r}, extra={extra!r}"
        )
    errors = validate_sourcebook(sourcebook)
    if errors:
        raise SemanticInputError("sourcebook validation failed: " + "; ".join(errors))
    return sourcebook


def _validate_tasks(
    source: TeachingPlanSource,
    sourcebook: LessonSourcebook,
    raw: Any,
) -> tuple[SharedTaskSpec, ...]:
    if not isinstance(raw, list):
        raise SemanticInputError("shared-task WorkItem output must be a JSON array")
    try:
        tasks = tuple(TypeAdapter(list[SharedTaskSpec]).validate_python(raw))
    except (TypeError, ValueError) as exc:
        raise SemanticInputError(
            "shared-task WorkItem output is not valid SharedTaskSpec JSON"
        ) from exc
    task_ids = [task.id for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise SemanticInputError("shared-task IDs must be unique")
    try:
        finalized = tuple(finalize_shared_tasks(source.plan, tasks, sourcebook=sourcebook))
    except (TypeError, ValueError) as exc:
        raise SemanticInputError("shared-task output failed final semantic validation") from exc
    expected_ids = [
        f"task-{block.id}"
        for section in source.plan.sections
        for block in section.blocks
        if block.learner_action is not None and response_bearing_action(block.learner_action.action)
    ]
    if task_ids != expected_ids:
        missing = sorted(set(expected_ids) - set(task_ids))
        extra = sorted(set(task_ids) - set(expected_ids))
        raise SemanticInputError(
            f"shared-task output does not match approved blocks; missing={missing!r}, extra={extra!r}"
        )
    return finalized


async def admit_sourcebook_work_item(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    max_attempts: int = 3,
) -> AdmissionResult:
    """Admit the first semantic WorkItem against the exact approved plan."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _source_identity(source)
    _approved_sourcebook_ids(source)
    await _lock_owned_run(session, run_id=run_id, owner_user_id=owner_user_id, source=identity)
    return await add_work_item(
        session,
        WorkItemAdmission(
            run_id=run_id,
            item_key=SOURCEBOOK_ITEM_KEY,
            stage=SOURCEBOOK_STAGE,
            input_hash=_sourcebook_input_hash(source),
            definition_hash=_stable_hash(SOURCEBOOK_DEFINITION),
            max_attempts=max_attempts,
        ),
    )


async def admit_shared_task_work_item(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    sourcebook_output_hash: str,
    max_attempts: int = 3,
) -> AdmissionResult:
    """Admit tasks only after the active sourcebook leaf is ready and bound."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    if len(sourcebook_output_hash) != 64 or any(
        char not in "0123456789abcdef" for char in sourcebook_output_hash
    ):
        raise SemanticInputError("sourcebook output hash is not a canonical digest")
    identity = _source_identity(source)
    run = await _lock_owned_run(
        session, run_id=run_id, owner_user_id=owner_user_id, source=identity
    )
    items = list(
        (
            await session.scalars(
                select(GenerationWorkItemModel).where(GenerationWorkItemModel.run_id == run.id)
            )
        ).all()
    )
    selected = _active_semantic_items(items)
    sourcebook_item = selected.get(SOURCEBOOK_ITEM_KEY)
    if sourcebook_item is None:
        raise SemanticInputError("shared tasks require an admitted sourcebook WorkItem")
    _sourcebook, actual_hash = _verify_sourcebook_work_item(sourcebook_item, source=source)
    if actual_hash != sourcebook_output_hash:
        raise SemanticInputError("shared task dependency hash differs from ready sourcebook")
    return await add_work_item(
        session,
        WorkItemAdmission(
            run_id=run_id,
            item_key=TASK_ITEM_KEY,
            stage=TASK_STAGE,
            input_hash=_task_input_hash(source, sourcebook_output_hash),
            definition_hash=_stable_hash(TASK_DEFINITION),
            composition_identity=sourcebook_output_hash,
            max_attempts=max_attempts,
        ),
    )


async def _load_verified_sourcebook_input_from_run(
    run: GenerationRunModel,
    *,
    owner_user_id: str,
    source: TeachingPlanSource,
) -> VerifiedSourcebookInput:
    identity = _source_identity(source)
    if run.run_type != "shared_document":
        raise SemanticInputError("semantic inputs require a SharedDocument Run")
    persisted = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    observed = (
        identity.source_artifact_type,
        identity.source_artifact_id,
        identity.source_revision,
        identity.source_hash,
    )
    if persisted != observed:
        raise SemanticInputError("semantic input source differs from the admitted Run")

    sourcebook_item = _assert_active_sourcebook_chain(run.work_items, run_id=run.id)
    sourcebook, sourcebook_hash = _verify_sourcebook_work_item(sourcebook_item, source=source)
    return VerifiedSourcebookInput(
        run_id=run.id,
        owner_user_id=owner_user_id,
        source=source,
        sourcebook=sourcebook,
        sourcebook_output_hash=sourcebook_hash,
        work_item_id=sourcebook_item.id,
    )


async def load_verified_sourcebook_input(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
) -> VerifiedSourcebookInput:
    """Reload the exact active READY sourcebook leaf without requiring tasks."""
    run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
    if run is None:
        raise SemanticInputError("SharedDocument Run is unavailable to this owner")
    return await _load_verified_sourcebook_input_from_run(
        run,
        owner_user_id=owner_user_id,
        source=source,
    )


async def load_verified_semantic_inputs(
    session: AsyncSession,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
) -> VerifiedSemanticInputs:
    """Reload accepted sourcebook/tasks without mutating durable state."""
    run = await get_run_status(session, run_id=run_id, owner_user_id=owner_user_id)
    if run is None:
        raise SemanticInputError("SharedDocument Run is unavailable to this owner")
    verified_sourcebook = await _load_verified_sourcebook_input_from_run(
        run,
        owner_user_id=owner_user_id,
        source=source,
    )
    selected = _active_semantic_items(run.work_items)
    sourcebook_item = selected.get(SOURCEBOOK_ITEM_KEY)
    task_item = selected.get(TASK_ITEM_KEY)
    if sourcebook_item is None or sourcebook_item.id != verified_sourcebook.work_item_id:
        raise SemanticInputError("active sourcebook WorkItem changed during semantic reload")
    sourcebook = verified_sourcebook.sourcebook
    sourcebook_hash = verified_sourcebook.sourcebook_output_hash
    if task_item is None:
        raise SemanticInputError("missing active semantic WorkItems: ['shared_tasks']")
    task_raw, task_hash = _verify_work_item_output(task_item, expected_key=TASK_ITEM_KEY)
    if task_item.composition_identity != sourcebook_hash:
        raise SemanticInputError("shared-task WorkItem has a stale sourcebook dependency")
    if task_item.input_hash != _task_input_hash(source, sourcebook_hash):
        raise SemanticInputError("shared-task WorkItem input identity is stale")
    tasks = _validate_tasks(source, sourcebook, task_raw)
    return VerifiedSemanticInputs(
        run_id=run.id,
        owner_user_id=owner_user_id,
        source=source,
        sourcebook=sourcebook,
        tasks=tasks,
        sourcebook_output_hash=sourcebook_hash,
        task_output_hash=task_hash,
        work_item_ids={SOURCEBOOK_ITEM_KEY: sourcebook_item.id, TASK_ITEM_KEY: task_item.id},
    )


__all__ = [
    "SOURCEBOOK_DEFINITION",
    "SOURCEBOOK_ITEM_KEY",
    "SOURCEBOOK_STAGE",
    "TASK_DEFINITION",
    "TASK_ITEM_KEY",
    "TASK_STAGE",
    "SemanticInputError",
    "VerifiedSemanticInputs",
    "VerifiedSourcebookInput",
    "admit_shared_task_work_item",
    "admit_sourcebook_work_item",
    "load_verified_semantic_inputs",
    "load_verified_sourcebook_input",
]
