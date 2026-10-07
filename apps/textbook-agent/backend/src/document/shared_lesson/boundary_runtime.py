"""Durable continuity-boundary work for SharedLessonDocument runs.

The stateless boundary validator owns deterministic checks, one semantic review,
and one targeted revalidation.  This module supplies the durable WorkItem
boundary around it.  A boundary freezes the two accepted writer outputs and
their composition identities before it can be admitted.  A repair is kept out
of the ready boundary artifact: the repaired section is reported as a pending
writer replacement so the existing ready writer row is never overwritten.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import weakref
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.exceptions import UnexpectedModelBehavior
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.boundary import (
    _WriterBoundaryRepairEngine,
    BoundaryRepairEngine,
    BoundarySemanticValidator,
    BoundaryValidationResult,
    default_boundary_semantic_validator,
    validate_and_repair_boundary,
)
from document.shared_lesson.models import SharedSection
from document.shared_lesson.qa import NARRATIVE_CONTINUITY_ISSUE_CODES
from document.shared_lesson.runtime import (
    TeachingPlanSource,
    rollback_for_failure_record,
    verify_teaching_plan_source,
)
from document.shared_lesson.writer import SectionWriteResult, SectionWriterRequest
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.execution.leases import LeaseLostError
from infra.llm.runner import is_provider_request_rejected, is_retryable_provider_error
from infra.generation_runtime import (
    AdmissionResult,
    ErrorClass,
    RecoveryAction,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
    SourceIdentity,
    WorkItemAdmission,
    WorkItemFailure,
    WorkItemReplacement,
    active_work_items,
    add_work_item,
    append_event,
    claim_work_item,
    complete_work_item,
    fail_work_item,
    load_compatible_checkpoint,
    persist_checkpoint,
    replace_work_item,
)

BOUNDARY_STAGE = "continuity_validation"
BOUNDARY_DEFINITION = "shared-boundary-runtime:v1"
MAX_CONCURRENT_BOUNDARIES = 4
BOUNDARY_ADVISORY_MARKER = ":advisory:"
BOUNDARY_PENDING_REPLACEMENT_CODE = "boundary_repair_pending_writer_replacement"
BOUNDARY_VALIDATION_LEASE_FRACTION = 0.8
_BOUNDARY_VALIDATION_SEMAPHORES: weakref.WeakKeyDictionary[
    asyncio.AbstractEventLoop, asyncio.Semaphore
] = weakref.WeakKeyDictionary()


class BoundaryRuntimeError(ValueError):
    """The durable boundary request is invalid or stale."""


class BoundarySourceConflict(BoundaryRuntimeError):
    """A boundary no longer matches its approved source or writer siblings."""


class BoundaryCheckpointError(BoundaryRuntimeError):
    """A persisted boundary checkpoint cannot be safely reused."""


class BoundaryValidationDeadlineExceeded(TimeoutError):
    """Aggregate semantic/repair work exceeded its fenced lease budget."""


def _boundary_validation_semaphore() -> asyncio.Semaphore:
    """Share the provider cap across dispatches for this worker event loop."""
    loop = asyncio.get_running_loop()
    semaphore = _BOUNDARY_VALIDATION_SEMAPHORES.get(loop)
    if semaphore is None:
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_BOUNDARIES)
        _BOUNDARY_VALIDATION_SEMAPHORES[loop] = semaphore
    return semaphore


def _consume_detached_validation_task(task: asyncio.Task[Any]) -> None:
    try:
        task.exception()
    except asyncio.CancelledError:
        pass


def _cancel_detached_validation_task(task: asyncio.Task[Any]) -> None:
    """Cancel provider-only work without awaiting a cancellation-resistant call."""
    if not task.done():
        task.cancel()
        task.add_done_callback(_consume_detached_validation_task)


async def _await_before_boundary_deadline(awaitable: Awaitable[Any], *, deadline: float) -> Any:
    """Reject late provider returns before the validator can start another call."""
    loop = asyncio.get_running_loop()
    if loop.time() >= deadline:
        raise BoundaryValidationDeadlineExceeded
    result = await awaitable
    if loop.time() >= deadline:
        raise BoundaryValidationDeadlineExceeded
    return result


class _DeadlineBoundedBoundaryRepair:
    def __init__(self, engine: BoundaryRepairEngine, *, deadline: float) -> None:
        self._engine = engine
        self._deadline = deadline

    async def repair_section(self, request: Any) -> Any:
        return await _await_before_boundary_deadline(
            self._engine.repair_section(request), deadline=self._deadline
        )


async def _run_boundary_validation_before_deadline(
    validator: Callable[[], Awaitable[BoundaryValidationResult]],
    *,
    deadline: float,
) -> BoundaryValidationResult:
    """Run session-free provider work under the shared cap and an aggregate deadline."""
    loop = asyncio.get_running_loop()
    remaining = deadline - loop.time()
    if remaining <= 0:
        raise BoundaryValidationDeadlineExceeded

    async def run_limited() -> BoundaryValidationResult:
        async with _boundary_validation_semaphore():
            return await validator()

    task = asyncio.create_task(run_limited(), name="shared-boundary-validation")
    try:
        done, _pending = await asyncio.wait({task}, timeout=remaining)
    except BaseException:
        _cancel_detached_validation_task(task)
        raise
    if not done:
        _cancel_detached_validation_task(task)
        raise BoundaryValidationDeadlineExceeded
    return task.result()


class BoundaryWorkOrder(BaseModel):
    """Frozen identity of the two accepted writer outputs at one boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_plan_id: str = Field(min_length=1)
    source_plan_revision: int = Field(ge=1)
    source_plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_section_id: str = Field(min_length=1)
    previous_section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_composition_identity: str = Field(min_length=1)
    next_section_id: str = Field(min_length=1)
    next_section_output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    next_composition_identity: str = Field(min_length=1)


class BoundaryRuntimeOutcome(BaseModel):
    """Safe projection returned after one boundary work-item attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    work_item_id: str
    result: BoundaryValidationResult | None = None
    error_code: str | None = None
    error_summary: str | None = None
    pending_replacement_section_ids: tuple[str, ...] = ()
    preserved_ready_siblings: bool = False


@dataclass(frozen=True)
class BoundaryWorkItemJob:
    session: Any
    work_item_id: str
    worker_id: str
    source: TeachingPlanSource | SourceIdentity
    previous_section: SharedSection
    next_section: SharedSection
    writer_requests: Mapping[str, SectionWriterRequest]
    semantic_validator: BoundarySemanticValidator | None = None
    repair_engine: BoundaryRepairEngine | None = None
    status: str = "queued"
    lease_seconds: int = 300


def accepted_section_output_hash(section: SharedSection) -> str:
    """Hash the exact accepted section representation in UTF-8."""
    payload = json.dumps(
        section.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _identity(source: TeachingPlanSource | SourceIdentity) -> SourceIdentity:
    if isinstance(source, TeachingPlanSource):
        return verify_teaching_plan_source(source)
    if isinstance(source, SourceIdentity):
        return source
    raise BoundarySourceConflict("boundary source must be an approved TeachingPlanSource")


def _plan_pair(
    source: TeachingPlanSource | SourceIdentity,
    previous_section: SharedSection,
    next_section: SharedSection,
) -> tuple[TeachingPlanSection, TeachingPlanSection]:
    if not isinstance(source, TeachingPlanSource):
        raise BoundarySourceConflict(
            "adjacent Teaching Plan sections are required to verify a boundary"
        )
    by_id = {section.slot_id: section for section in source.plan.sections}
    previous_plan = by_id.get(previous_section.id)
    next_plan = by_id.get(next_section.id)
    if previous_plan is None or next_plan is None:
        raise BoundarySourceConflict("boundary sections are not in the approved Teaching Plan")
    positions = {section.slot_id: index for index, section in enumerate(source.plan.sections)}
    if positions[next_section.id] != positions[previous_section.id] + 1:
        raise BoundarySourceConflict("boundary sections are not adjacent in the approved plan")
    if previous_section.position != positions[previous_section.id]:
        raise BoundarySourceConflict("previous accepted section position is stale")
    if next_section.position != positions[next_section.id]:
        raise BoundarySourceConflict("next accepted section position is stale")
    return previous_plan, next_plan


def _composition_identity(previous: str, next_: str) -> str:
    return json.dumps(
        {"previous": previous, "next": next_},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _work_order(
    identity: SourceIdentity,
    previous_section: SharedSection,
    next_section: SharedSection,
    *,
    previous_composition_identity: str,
    next_composition_identity: str,
) -> BoundaryWorkOrder:
    return BoundaryWorkOrder(
        source_plan_id=identity.source_artifact_id,
        source_plan_revision=identity.source_revision,
        source_plan_hash=identity.source_hash,
        previous_section_id=previous_section.id,
        previous_section_output_hash=accepted_section_output_hash(previous_section),
        previous_composition_identity=previous_composition_identity,
        next_section_id=next_section.id,
        next_section_output_hash=accepted_section_output_hash(next_section),
        next_composition_identity=next_composition_identity,
    )


async def _verify_run_source(
    session: Any,
    *,
    run_id: str,
    owner_user_id: str,
    source: SourceIdentity,
    lock: bool = False,
) -> GenerationRunModel:
    statement = select(GenerationRunModel).where(GenerationRunModel.id == run_id)
    if lock:
        statement = statement.with_for_update()
    run = await session.scalar(statement)
    if run is None or run.owner_user_id != owner_user_id:
        raise BoundarySourceConflict("SharedDocument Run is unavailable to this owner")
    persisted = (
        run.source_artifact_type,
        run.source_artifact_id,
        run.source_revision,
        run.source_hash,
    )
    observed = (
        source.source_artifact_type,
        source.source_artifact_id,
        source.source_revision,
        source.source_hash,
    )
    if persisted != observed:
        raise BoundarySourceConflict("boundary source differs from the admitted SharedDocument Run")
    return run


def _writer_item_output(
    item: GenerationWorkItemModel,
    *,
    section_id: str,
    position: int,
) -> SharedSection:
    if item.status != "ready" or item.output_json is None:
        raise BoundarySourceConflict(f"active writer output for {section_id!r} is not ready")
    try:
        output = SectionWriteResult.model_validate(item.output_json)
        section = output.as_shared_section(section_id=section_id, position=position)
    except (TypeError, ValueError) as exc:
        raise BoundarySourceConflict(
            f"active writer output for {section_id!r} violates its closed contract"
        ) from exc
    if item.output_hash != content_hash(item.output_json):
        raise BoundarySourceConflict(f"active writer output hash for {section_id!r} is invalid")
    if accepted_section_output_hash(section) == "":  # pragma: no cover - defensive
        raise BoundarySourceConflict("accepted writer output hash is empty")
    return section


def _logical_item_key(
    item: GenerationWorkItemModel,
    by_id: Mapping[str, GenerationWorkItemModel],
) -> str:
    """Return the original stable key for a replacement-chain leaf."""
    current = item
    seen: set[str] = set()
    while current.replaces_work_item_id is not None:
        if current.id in seen:
            raise BoundarySourceConflict("writer replacement chain contains a cycle")
        seen.add(current.id)
        predecessor = by_id.get(current.replaces_work_item_id)
        if predecessor is None:
            raise BoundarySourceConflict("writer replacement chain has a missing predecessor")
        current = predecessor
    return current.item_key


async def _verify_active_writer_outputs(
    session: Any,
    *,
    run_id: str,
    previous_section: SharedSection,
    next_section: SharedSection,
    previous_composition_identity: str,
    next_composition_identity: str,
    lock: bool = False,
) -> tuple[GenerationWorkItemModel, GenerationWorkItemModel]:
    statement = select(GenerationWorkItemModel).where(
        GenerationWorkItemModel.run_id == run_id,
        GenerationWorkItemModel.stage == "section_writing",
    )
    if lock:
        statement = statement.with_for_update()
    items = list((await session.scalars(statement)).all())
    by_id = {item.id: item for item in items}
    leaves = {
        _logical_item_key(item, by_id): item
        for item in active_work_items(items)
        if _logical_item_key(item, by_id)
        in {f"write:{previous_section.id}", f"write:{next_section.id}"}
    }
    expected = (
        (previous_section, previous_composition_identity),
        (next_section, next_composition_identity),
    )
    result: list[GenerationWorkItemModel] = []
    for section, composition_identity in expected:
        item = leaves.get(f"write:{section.id}")
        if item is None:
            raise BoundarySourceConflict(f"active writer output for {section.id!r} is missing")
        if item.composition_identity != composition_identity:
            raise BoundarySourceConflict(
                f"active writer composition identity for {section.id!r} is stale"
            )
        position = section.position
        produced = _writer_item_output(item, section_id=section.id, position=position)
        if accepted_section_output_hash(produced) != accepted_section_output_hash(section):
            raise BoundarySourceConflict(
                f"accepted section {section.id!r} differs from active writer output"
            )
        result.append(item)
    return result[0], result[1]


def _item_request(run_id: str, work: BoundaryWorkOrder, *, max_attempts: int) -> WorkItemAdmission:
    return WorkItemAdmission(
        run_id=run_id,
        item_key=f"boundary:{work.previous_section_id}->{work.next_section_id}",
        stage=BOUNDARY_STAGE,
        input_hash=content_hash(work.model_dump(mode="json")),
        definition_hash=hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest(),
        composition_identity=_composition_identity(
            work.previous_composition_identity, work.next_composition_identity
        ),
        max_attempts=max_attempts,
    )


async def admit_boundary_work_item(
    session: Any,
    *,
    run_id: str,
    owner_user_id: str,
    source: TeachingPlanSource | SourceIdentity,
    previous_section: SharedSection,
    next_section: SharedSection,
    previous_composition_identity: str,
    next_composition_identity: str,
    max_attempts: int = 3,
) -> AdmissionResult:
    """Admit one boundary only after both current writer leaves are ready."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _plan_pair(source, previous_section, next_section)
    if not previous_composition_identity.strip() or not next_composition_identity.strip():
        raise BoundarySourceConflict("boundary composition identities must be non-empty")
    await _verify_run_source(
        session, run_id=run_id, owner_user_id=owner_user_id, source=identity, lock=True
    )
    await _verify_active_writer_outputs(
        session,
        run_id=run_id,
        previous_section=previous_section,
        next_section=next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
    )
    work = _work_order(
        identity,
        previous_section,
        next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
    )
    return await add_work_item(session, _item_request(run_id, work, max_attempts=max_attempts))


def _verified_repair_proof(
    predecessor: GenerationWorkItemModel,
    identity: SourceIdentity,
) -> tuple[BoundaryWorkOrder, BoundaryValidationResult]:
    """Validate a failed boundary's durable ``shared_lesson_boundary_repair_result``.

    Returns the original frozen work order and the validated repair result.
    Any identity, hash, shape or source mismatch raises ``BoundarySourceConflict``.
    """
    try:
        checkpoint = RuntimeCheckpoint.model_validate(predecessor.checkpoint_json)
    except (TypeError, ValueError) as exc:
        raise BoundarySourceConflict(
            "boundary repair proof violates the runtime checkpoint contract"
        ) from exc
    if content_hash(checkpoint.payload) != checkpoint.payload_hash:
        raise BoundarySourceConflict("boundary repair proof hash is invalid")
    payload = checkpoint.payload
    if (
        not isinstance(payload, Mapping)
        or payload.get("kind") != "shared_lesson_boundary_repair_result"
    ):
        raise BoundarySourceConflict("boundary predecessor checkpoint is not a repair proof")
    try:
        original_work = BoundaryWorkOrder.model_validate(payload["work"])
        repair_result = BoundaryValidationResult.model_validate(payload["result"])
    except (TypeError, ValueError) as exc:
        raise BoundarySourceConflict(
            "boundary repair proof has an invalid work or result shape"
        ) from exc
    if (
        checkpoint.compatibility.source_revision != identity.source_revision
        or checkpoint.compatibility.source_hash != identity.source_hash
        or checkpoint.compatibility.input_hash
        != content_hash(original_work.model_dump(mode="json"))
        or checkpoint.compatibility.definition_hash
        != hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest()
        or checkpoint.compatibility.composition_identity
        != _composition_identity(
            original_work.previous_composition_identity,
            original_work.next_composition_identity,
        )
        or predecessor.input_hash != checkpoint.compatibility.input_hash
        or predecessor.definition_hash != checkpoint.compatibility.definition_hash
        or predecessor.composition_identity != checkpoint.compatibility.composition_identity
    ):
        raise BoundarySourceConflict("boundary repair proof identity is stale")
    if (
        original_work.source_plan_id,
        original_work.source_plan_revision,
        original_work.source_plan_hash,
    ) != (identity.source_artifact_id, identity.source_revision, identity.source_hash):
        raise BoundarySourceConflict("boundary repair proof source differs from the approved plan")
    return original_work, repair_result


async def admit_boundary_replacement_work_item(
    session: Any,
    *,
    predecessor_work_item_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    previous_section: SharedSection,
    next_section: SharedSection,
    previous_composition_identity: str,
    next_composition_identity: str,
    max_attempts: int = 3,
) -> GenerationWorkItemModel:
    """Admit a fresh boundary successor after a targeted writer replacement.

    The failed boundary row is historical evidence only.  Its checkpoint must
    prove the original pair and repair result; the successor is bound to the
    current active writer leaves and therefore receives a new item identity.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _plan_pair(source, previous_section, next_section)
    if not previous_composition_identity.strip() or not next_composition_identity.strip():
        raise BoundarySourceConflict("boundary composition identities must be non-empty")
    predecessor = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.id == predecessor_work_item_id,
            GenerationWorkItemModel.stage == BOUNDARY_STAGE,
        )
    )
    if predecessor is None or predecessor.status != "failed_recoverable":
        raise BoundarySourceConflict("boundary predecessor is not a recoverable historical item")
    successor = await session.scalar(
        select(GenerationWorkItemModel.id).where(
            GenerationWorkItemModel.replaces_work_item_id == predecessor_work_item_id
        )
    )
    if successor is not None:
        raise BoundarySourceConflict("boundary predecessor already has a successor")
    if predecessor.checkpoint_json is None:
        raise BoundarySourceConflict("boundary predecessor has no durable repair proof")
    await _verify_run_source(
        session,
        run_id=predecessor.run_id,
        owner_user_id=owner_user_id,
        source=identity,
        lock=True,
    )
    original_work, repair_result = _verified_repair_proof(predecessor, identity)
    if not repair_result.passed or not repair_result.repair_attempted:
        raise BoundarySourceConflict(
            "boundary repair proof does not contain a passing targeted repair"
        )
    original_hashes = {
        original_work.previous_section_id: original_work.previous_section_output_hash,
        original_work.next_section_id: original_work.next_section_output_hash,
    }
    result_hashes = {
        repair_result.previous_section.id: accepted_section_output_hash(
            repair_result.previous_section
        ),
        repair_result.next_section.id: accepted_section_output_hash(repair_result.next_section),
    }
    if set(original_hashes) != {previous_section.id, next_section.id}:
        raise BoundarySourceConflict("boundary repair proof binds a different original pair")
    changed = {
        section_id
        for section_id, original_hash in original_hashes.items()
        if result_hashes.get(section_id) != original_hash
    }
    if len(changed) != 1:
        raise BoundarySourceConflict("boundary repair proof must identify one changed section")
    # ``_verify_active_writer_outputs`` already raises ``BoundarySourceConflict``
    # unless the current active writer leaf for each side hashes to exactly
    # ``previous_section``/``next_section`` -- those are therefore already the
    # verified current output and are hashed directly by their own (slot) id,
    # not by re-deriving a section from the returned WorkItem rows.
    await _verify_active_writer_outputs(
        session,
        run_id=predecessor.run_id,
        previous_section=previous_section,
        next_section=next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
        lock=True,
    )
    current_hashes = {
        previous_section.id: accepted_section_output_hash(previous_section),
        next_section.id: accepted_section_output_hash(next_section),
    }
    for section_id, original_hash in original_hashes.items():
        observed_hash = current_hashes.get(section_id)
        if observed_hash is None:
            raise BoundarySourceConflict("current active boundary pair is incomplete")
        expected_hash = result_hashes[section_id] if section_id in changed else original_hash
        if observed_hash != expected_hash:
            raise BoundarySourceConflict(
                f"current active writer output for {section_id!r} does not match the durable repair proof"
            )
    current_work = _work_order(
        identity,
        previous_section,
        next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
    )
    if current_work.model_dump(mode="json") == original_work.model_dump(mode="json"):
        raise BoundarySourceConflict(
            "boundary successor must bind the changed active writer output"
        )
    input_hash = content_hash(current_work.model_dump(mode="json"))
    replacement = WorkItemAdmission(
        run_id=predecessor.run_id,
        item_key=(f"boundary:{previous_section.id}->{next_section.id}:repair:{input_hash[:24]}"),
        stage=BOUNDARY_STAGE,
        input_hash=input_hash,
        definition_hash=hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest(),
        composition_identity=_composition_identity(
            previous_composition_identity, next_composition_identity
        ),
        max_attempts=max_attempts,
    )
    return await replace_work_item(
        session,
        WorkItemReplacement(
            predecessor_work_item_id=predecessor_work_item_id,
            owner_user_id=owner_user_id,
            source=identity,
            replacement=replacement,
        ),
    )


def boundary_advisory_input_hash(work: BoundaryWorkOrder) -> str:
    """Input identity of an advisory successor bound to its *original* work order.

    It must differ from the failed predecessor's ``input_hash`` (a replacement
    must bind a changed identity) while still binding exactly the original pair.
    """
    return content_hash(
        {"kind": "shared_lesson_boundary_advisory", "work": work.model_dump(mode="json")}
    )


def is_boundary_advisory_item(item: GenerationWorkItemModel) -> bool:
    return getattr(item, "replaces_work_item_id", None) is not None and (
        BOUNDARY_ADVISORY_MARKER in str(getattr(item, "item_key", ""))
    )


def unique_boundary_issues(*groups: Sequence[ContinuityIssue]) -> tuple[ContinuityIssue, ...]:
    seen: list[ContinuityIssue] = []
    for group in groups:
        for issue in group:
            if issue not in seen:
                seen.append(issue)
    return tuple(seen)


def _advisory_issues_from_result(result: BoundaryValidationResult) -> tuple[ContinuityIssue, ...]:
    return unique_boundary_issues(result.initial_issues, result.issues)


async def admit_boundary_advisory_successor(
    session: Any,
    *,
    predecessor_work_item_id: str,
    owner_user_id: str,
    source: TeachingPlanSource,
    previous_section: SharedSection,
    next_section: SharedSection,
    previous_composition_identity: str,
    next_composition_identity: str,
    max_attempts: int = 3,
) -> GenerationWorkItemModel:
    """Admit a deterministic advisory successor for an unrepairable boundary.

    The failed predecessor must durably prove a targeted-repair result for the
    ORIGINAL pair, and both current active writer outputs must still equal that
    original pair.  The successor is bound to the original work order and
    completes without any provider call, carrying the proven issues as
    teacher-visible advisories.  Any source/identity mismatch raises
    ``BoundarySourceConflict`` so the boundary stays blocked.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    identity = _identity(source)
    _plan_pair(source, previous_section, next_section)
    if not previous_composition_identity.strip() or not next_composition_identity.strip():
        raise BoundarySourceConflict("boundary composition identities must be non-empty")
    predecessor = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.id == predecessor_work_item_id,
            GenerationWorkItemModel.stage == BOUNDARY_STAGE,
        )
    )
    if predecessor is None or predecessor.status != "failed_recoverable":
        raise BoundarySourceConflict("boundary predecessor is not a recoverable historical item")
    successor = await session.scalar(
        select(GenerationWorkItemModel.id).where(
            GenerationWorkItemModel.replaces_work_item_id == predecessor_work_item_id
        )
    )
    if successor is not None:
        raise BoundarySourceConflict("boundary predecessor already has a successor")
    if predecessor.checkpoint_json is None:
        raise BoundarySourceConflict("boundary predecessor has no durable repair proof")
    await _verify_run_source(
        session,
        run_id=predecessor.run_id,
        owner_user_id=owner_user_id,
        source=identity,
        lock=True,
    )
    original_work, _proof = _verified_repair_proof(predecessor, identity)
    await _verify_active_writer_outputs(
        session,
        run_id=predecessor.run_id,
        previous_section=previous_section,
        next_section=next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
        lock=True,
    )
    current_work = _work_order(
        identity,
        previous_section,
        next_section,
        previous_composition_identity=previous_composition_identity,
        next_composition_identity=next_composition_identity,
    )
    if current_work.model_dump(mode="json") != original_work.model_dump(mode="json"):
        raise BoundarySourceConflict(
            "current active writer outputs differ from the original boundary pair"
        )
    input_hash = boundary_advisory_input_hash(original_work)
    replacement = WorkItemAdmission(
        run_id=predecessor.run_id,
        item_key=(
            f"boundary:{previous_section.id}->{next_section.id}"
            f"{BOUNDARY_ADVISORY_MARKER}{input_hash[:24]}"
        ),
        stage=BOUNDARY_STAGE,
        input_hash=input_hash,
        definition_hash=hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest(),
        composition_identity=_composition_identity(
            previous_composition_identity, next_composition_identity
        ),
        max_attempts=max_attempts,
    )
    return await replace_work_item(
        session,
        WorkItemReplacement(
            predecessor_work_item_id=predecessor_work_item_id,
            owner_user_id=owner_user_id,
            source=identity,
            replacement=replacement,
        ),
    )


def _checkpoint_compatibility(
    *, source: SourceIdentity, item: GenerationWorkItemModel
) -> RuntimeCheckpointCompatibility:
    return RuntimeCheckpointCompatibility(
        schema_version=1,
        source_revision=source.source_revision,
        source_hash=source.source_hash,
        input_hash=item.input_hash,
        definition_hash=item.definition_hash,
        composition_identity=item.composition_identity,
    )


def _checkpoint_payload(work: BoundaryWorkOrder) -> dict[str, Any]:
    return {"kind": "shared_lesson_boundary", "work": work.model_dump(mode="json")}


def _validate_checkpoint_payload(payload: Any, work: BoundaryWorkOrder) -> None:
    if not isinstance(payload, Mapping) or payload.get("kind") != "shared_lesson_boundary":
        raise BoundaryCheckpointError("boundary checkpoint has an unsupported shape")
    if payload.get("work") != work.model_dump(mode="json"):
        raise BoundaryCheckpointError("boundary checkpoint is stale or conflicting")


def _is_repair_result_payload(payload: Any) -> bool:
    return (
        isinstance(payload, Mapping) and payload.get("kind") == "shared_lesson_boundary_repair_result"
    )


def _repair_proof_from_checkpoint(
    payload: Any, work: BoundaryWorkOrder
) -> BoundaryValidationResult:
    """Read the repair-result proof a prior attempt of THIS exact work item left.

    The checkpoint hash and compatibility were already verified by
    ``load_compatible_checkpoint``; this only binds the payload to ``work``.
    """
    if not _is_repair_result_payload(payload):
        raise BoundaryCheckpointError("boundary checkpoint has an unsupported shape")
    if payload.get("work") != work.model_dump(mode="json"):
        raise BoundaryCheckpointError("boundary checkpoint is stale or conflicting")
    try:
        return BoundaryValidationResult.model_validate(payload["result"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BoundaryCheckpointError("boundary repair proof has an invalid result shape") from exc


def _validate_item_binding(item: GenerationWorkItemModel, work: BoundaryWorkOrder) -> None:
    expected_identity = _composition_identity(
        work.previous_composition_identity, work.next_composition_identity
    )
    if (
        item.stage != BOUNDARY_STAGE
        or item.input_hash != content_hash(work.model_dump(mode="json"))
        or item.composition_identity != expected_identity
    ):
        raise BoundaryCheckpointError("boundary work item identity is stale or conflicting")


def _failure_for_exception(exc: Exception) -> WorkItemFailure:
    if isinstance(exc, BoundaryValidationDeadlineExceeded):
        return WorkItemFailure(
            error_code="boundary_validation_timeout",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Boundary validation exceeded its aggregate deadline.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, (TimeoutError, ConnectionError)) or is_retryable_provider_error(exc):
        return WorkItemFailure(
            error_code="boundary_provider_transport",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="Boundary semantic provider transport failed.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, DBAPIError):
        # Raw database faults are transient infrastructure errors; retryable.
        return WorkItemFailure(
            error_code="database_transient",
            error_class=ErrorClass.PROVIDER_TRANSPORT,
            safe_summary="A transient database error interrupted boundary validation.",
            recovery_action=RecoveryAction.RETRY,
        )
    if isinstance(exc, (BoundaryCheckpointError, BoundarySourceConflict)):
        return WorkItemFailure(
            error_code="boundary_checkpoint_integrity",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Boundary checkpoint or source identity failed validation.",
            recovery_action=RecoveryAction.NONE,
        )
    if isinstance(exc, UnexpectedModelBehavior):
        # The boundary semantic reviewer and its one bounded targeted-repair
        # dispatch share the same zero-output-retry structured provider as the
        # section writer. Exhausting that retry budget on malformed or empty
        # output is a recoverable provider failure, not a programming error.
        return WorkItemFailure(
            error_code="boundary_invalid_output",
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary="Boundary semantic provider returned invalid output.",
            recovery_action=RecoveryAction.RETRY,
        )
    if is_provider_request_rejected(exc):
        return WorkItemFailure(
            error_code="boundary_provider_request_rejected",
            error_class=ErrorClass.UNSUPPORTED_CONTRACT,
            safe_summary="Boundary semantic provider rejected the request.",
            recovery_action=RecoveryAction.NONE,
        )
    return WorkItemFailure(
        error_code="boundary_runtime_error",
        error_class=ErrorClass.INTERNAL_PROGRAMMING,
        safe_summary="Boundary runtime failed unexpectedly.",
        recovery_action=RecoveryAction.NONE,
    )


async def _record_boundary_execution_failure(
    session: Any,
    *,
    work_item_id: str,
    worker_id: str,
    lease_token: int,
    error: Exception,
    now: Any = None,
) -> WorkItemFailure:
    """Persist a typed boundary failure and its safe exception-type diagnostic.

    Mirrors ``document.shared_lesson.runtime._record_execution_failure``: the
    diagnostic event carries only the exception's type name, never its message,
    prompts, or provider text.
    """
    failure = _failure_for_exception(error)
    failed_item = await fail_work_item(
        session,
        work_item_id=work_item_id,
        worker_id=worker_id,
        lease_token=lease_token,
        failure=failure,
        now=now,
    )
    await append_event(
        session,
        run_id=failed_item.run_id,
        work_item_id=failed_item.id,
        event_type="boundary_failure_diagnostic",
        error_code=failure.error_code,
        safe_payload={"original_exception_type": type(error).__name__},
    )
    return failure


async def execute_boundary_work_item(
    job: BoundaryWorkItemJob,
    *,
    now: Any = None,
) -> BoundaryRuntimeOutcome:
    """Claim, validate, checkpoint and fenced-commit one boundary."""
    identity = _identity(job.source)
    _plan_pair(job.source, job.previous_section, job.next_section)
    previous_item, next_item = await _verify_active_writer_outputs(
        job.session,
        run_id=(
            await job.session.scalar(
                select(GenerationWorkItemModel.run_id).where(
                    GenerationWorkItemModel.id == job.work_item_id
                )
            )
        ),
        previous_section=job.previous_section,
        next_section=job.next_section,
        previous_composition_identity=_composition_identity_from_request(
            job.writer_requests[job.previous_section.id]
        ),
        next_composition_identity=_composition_identity_from_request(
            job.writer_requests[job.next_section.id]
        ),
    )
    del previous_item, next_item
    work = _work_order(
        identity,
        job.previous_section,
        job.next_section,
        previous_composition_identity=_composition_identity_from_request(
            job.writer_requests[job.previous_section.id]
        ),
        next_composition_identity=_composition_identity_from_request(
            job.writer_requests[job.next_section.id]
        ),
    )
    item = await claim_work_item(
        job.session,
        work_item_id=job.work_item_id,
        worker_id=job.worker_id,
        source=identity,
        lease_seconds=job.lease_seconds,
        now=now,
    )
    claimed_lease_token = item.lease_token or 0
    # Keep a reserve inside the item lease for the final fenced recheck and
    # failure/completion persistence.  All semantic review and targeted
    # repair calls share this one aggregate deadline.
    loop = asyncio.get_running_loop()
    validation_deadline = loop.time() + (
        job.lease_seconds * BOUNDARY_VALIDATION_LEASE_FRACTION
    )
    compatibility = _checkpoint_compatibility(source=identity, item=item)
    # ``advisories`` is not ``None`` only for an advisory successor admitted by
    # ``admit_boundary_advisory_successor``; it completes with no provider call.
    advisories: tuple[ContinuityIssue, ...] | None = None
    # ``proof_result`` is set when a manual retry re-ran a leaf that already
    # durably proved a targeted repair (see below).
    proof_result: BoundaryValidationResult | None = None
    try:
        if is_boundary_advisory_item(item):
            advisories = await _advisory_issues_for_successor(
                job.session, item=item, identity=identity, work=work
            )
        else:
            _validate_item_binding(item, work)
            checkpoint = await load_compatible_checkpoint(
                job.session,
                work_item_id=item.id,
                worker_id=job.worker_id,
                lease_token=item.lease_token or 0,
                compatibility=compatibility,
                now=now,
            )
            if checkpoint is None:
                await persist_checkpoint(
                    job.session,
                    work_item_id=item.id,
                    worker_id=job.worker_id,
                    lease_token=item.lease_token or 0,
                    compatibility=compatibility,
                    payload=_checkpoint_payload(work),
                    now=now,
                )
            elif _is_repair_result_payload(checkpoint.payload):
                proof_result = _repair_proof_from_checkpoint(checkpoint.payload, work)
            else:
                _validate_checkpoint_payload(checkpoint.payload, work)
    except LeaseLostError:
        raise
    except Exception as exc:  # noqa: BLE001 - persist unknown checkpoint failures as typed failures.
        # A checkpoint read/write failure may leave the session's transaction
        # aborted (e.g. a SQL error) even while ``is_active`` is True, so
        # always roll back first. The claim above is not yet committed, so the
        # item is reclaimed under a fresh fence before the typed failure can
        # persist. ORM attributes were captured before this rollback expired
        # them (a lazy reload outside the greenlet raises MissingGreenlet).
        failure_lease_token = await rollback_for_failure_record(
            job.session,
            lease_token=claimed_lease_token,
            lease_committed=False,
            reclaim=lambda: claim_work_item(
                job.session,
                work_item_id=job.work_item_id,
                worker_id=job.worker_id,
                source=identity,
                lease_seconds=job.lease_seconds,
                now=now,
            ),
        )
        if failure_lease_token is None:
            raise
        failure = await _record_boundary_execution_failure(
            job.session,
            work_item_id=job.work_item_id,
            worker_id=job.worker_id,
            lease_token=failure_lease_token,
            error=exc,
            now=now,
        )
        return BoundaryRuntimeOutcome(
            work_item_id=job.work_item_id,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
            preserved_ready_siblings=True,
        )

    if proof_result is not None:
        # A manual Retry (``retry_work_items`` keeps the checkpoint) re-ran a
        # leaf that already holds a durable targeted-repair proof.  Re-running
        # validation would spend more provider calls and could never advance,
        # so re-fail with the same pending-replacement code (no provider
        # call).  REVIEW keeps the leaf failed_recoverable regardless of the
        # attempt budget, and the dispatcher then admits the writer
        # replacement (or the advisory fallback) exactly as for a first failure.
        original = {
            work.previous_section_id: work.previous_section_output_hash,
            work.next_section_id: work.next_section_output_hash,
        }
        proof_changed = tuple(
            section.id
            for section in (proof_result.previous_section, proof_result.next_section)
            if original.get(section.id) != accepted_section_output_hash(section)
        )
        failure = WorkItemFailure(
            error_code=BOUNDARY_PENDING_REPLACEMENT_CODE,
            error_class=ErrorClass.PROVIDER_OUTPUT,
            safe_summary=(
                "Boundary repair produced a changed section; admit a linked writer "
                "replacement before retrying."
            ),
            recovery_action=RecoveryAction.REVIEW,
        )
        await fail_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            failure=failure,
            now=now,
        )
        return BoundaryRuntimeOutcome(
            work_item_id=item.id,
            result=proof_result,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
            pending_replacement_section_ids=proof_changed,
            preserved_ready_siblings=True,
        )

    # Make the lease and compatible checkpoint visible before any external
    # semantic-review or repair provider work begins. The final writer recheck
    # and fenced completion below still decide whether the result can commit.
    await job.session.commit()

    if advisories is not None:
        result = BoundaryValidationResult(
            status="pass",
            previous_section=job.previous_section,
            next_section=job.next_section,
            semantic_calls=0,
        )
    else:
        try:
            previous_plan, next_plan = _plan_pair(job.source, job.previous_section, job.next_section)

            semantic_dispatch = job.semantic_validator or default_boundary_semantic_validator

            async def bounded_semantic_validator(request: Any) -> Any:
                return await _await_before_boundary_deadline(
                    semantic_dispatch(request), deadline=validation_deadline
                )

            bounded_repair_engine = _DeadlineBoundedBoundaryRepair(
                job.repair_engine or _WriterBoundaryRepairEngine(),
                deadline=validation_deadline,
            )
            result = await _run_boundary_validation_before_deadline(
                lambda: validate_and_repair_boundary(
                    previous_section=job.previous_section,
                    previous_plan=previous_plan,
                    next_section=job.next_section,
                    next_plan=next_plan,
                    semantic_validator=bounded_semantic_validator,
                    repair_engine=bounded_repair_engine,
                    writer_requests=job.writer_requests,
                ),
                deadline=validation_deadline,
            )
        except LeaseLostError:
            raise
        except Exception as exc:  # noqa: BLE001 - persist unknown validator failures as typed failures.
            # The claim and checkpoint above are already committed. A semantic
            # provider or repair-provider error (e.g. UnexpectedModelBehavior)
            # never touches the database, but clear any aborted transaction state
            # before the typed failure persists so the fenced write is never
            # attempted against a poisoned session.
            rollback = getattr(job.session, "rollback", None)
            failure_lease_token = claimed_lease_token
            if callable(rollback):
                await rollback()
            failure = await _record_boundary_execution_failure(
                job.session,
                work_item_id=job.work_item_id,
                worker_id=job.worker_id,
                lease_token=failure_lease_token,
                error=exc,
                now=now,
            )
            return BoundaryRuntimeOutcome(
                work_item_id=job.work_item_id,
                error_code=failure.error_code,
                error_summary=failure.safe_summary,
                preserved_ready_siblings=True,
            )

    original_hashes = {
        job.previous_section.id: accepted_section_output_hash(job.previous_section),
        job.next_section.id: accepted_section_output_hash(job.next_section),
    }
    repaired_hashes = {
        result.previous_section.id: accepted_section_output_hash(result.previous_section),
        result.next_section.id: accepted_section_output_hash(result.next_section),
    }
    changed_sections = tuple(
        section_id
        for section_id, original_hash in original_hashes.items()
        if repaired_hashes.get(section_id) != original_hash
    )
    try:
        # Provider work runs outside the database lock. Re-read and lock both
        # writer leaves immediately before the boundary can become READY so a
        # concurrent targeted writer replacement cannot make this result stale.
        await _verify_active_writer_outputs(
            job.session,
            run_id=item.run_id,
            previous_section=job.previous_section,
            next_section=job.next_section,
            previous_composition_identity=work.previous_composition_identity,
            next_composition_identity=work.next_composition_identity,
            lock=True,
        )
    except BoundarySourceConflict:
        failure = WorkItemFailure(
            error_code="boundary_source_changed_before_commit",
            error_class=ErrorClass.SOURCE_CONFLICT,
            safe_summary="Accepted writer output changed while boundary validation was running.",
            recovery_action=RecoveryAction.NONE,
        )
        await fail_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            failure=failure,
            now=now,
        )
        return BoundaryRuntimeOutcome(
            work_item_id=item.id,
            result=result,
            error_code=failure.error_code,
            error_summary=failure.safe_summary,
            preserved_ready_siblings=True,
        )
    if result.passed and not changed_sections:
        output = {
            "kind": "shared_lesson_boundary_result",
            "status": "pass",
            "work": work.model_dump(mode="json"),
            "previous_section": result.previous_section.model_dump(mode="json"),
            "next_section": result.next_section.model_dump(mode="json"),
            "semantic_calls": result.semantic_calls,
        }
        if advisories is not None:
            output["advisories"] = [issue.model_dump(mode="json") for issue in advisories]
        await complete_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            output_json=output,
            output_hash=content_hash(output),
            now=now,
        )
        if advisories is not None:
            await _append_advisory_event(job.session, item=item, work=work, issues=advisories)
        return BoundaryRuntimeOutcome(work_item_id=item.id, result=result)

    # A boundary work item whose own predecessor was already replaced once
    # (``item.replaces_work_item_id is not None``) can only reach this branch
    # through ``admit_boundary_replacement_work_item`` -- the one linked
    # successor this module ever admits after a targeted writer repair. If
    # *that* replacement boundary still needs another changed repair, the
    # single bounded writer-replacement budget is exhausted.  Never attempt a
    # second writer repair: complete this boundary in place on its CURRENT
    # (already once-repaired) sections and carry the remaining findings as
    # teacher-visible advisories.
    # The validator reports findings on BOTH sections as
    # ``boundary_repair_ambiguous`` and never attempts a repair, so no repair
    # proof exists for the advisory successor path.  When every finding is a
    # narrative continuity code, accept in place with the originals kept.
    ambiguous_narrative = (
        not result.passed
        and not changed_sections
        and result.failure_code == "boundary_repair_ambiguous"
        and bool(result.initial_issues)
        and all(
            issue.issue_code in NARRATIVE_CONTINUITY_ISSUE_CODES
            for issue in result.initial_issues
        )
    )
    if ambiguous_narrative or (bool(changed_sections) and item.replaces_work_item_id is not None):
        exhausted_advisories = (
            unique_boundary_issues(result.initial_issues)
            if ambiguous_narrative
            else _advisory_issues_from_result(result)
        )
        accepted_result = BoundaryValidationResult(
            status="pass",
            previous_section=job.previous_section,
            next_section=job.next_section,
            semantic_calls=result.semantic_calls,
        )
        output = {
            "kind": "shared_lesson_boundary_result",
            "status": "pass",
            "work": work.model_dump(mode="json"),
            "previous_section": job.previous_section.model_dump(mode="json"),
            "next_section": job.next_section.model_dump(mode="json"),
            "semantic_calls": result.semantic_calls,
            "advisories": [issue.model_dump(mode="json") for issue in exhausted_advisories],
        }
        await complete_work_item(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            output_json=output,
            output_hash=content_hash(output),
            now=now,
        )
        await _append_advisory_event(
            job.session, item=item, work=work, issues=exhausted_advisories
        )
        return BoundaryRuntimeOutcome(work_item_id=item.id, result=accepted_result)

    pending = changed_sections
    failure = WorkItemFailure(
        error_code=(
            BOUNDARY_PENDING_REPLACEMENT_CODE
            if changed_sections
            else (result.failure_code or "boundary_validation_failed")
        ),
        error_class=ErrorClass.PROVIDER_OUTPUT,
        safe_summary=(
            "Boundary repair produced a changed section; admit a linked writer replacement before retrying."
            if changed_sections
            else "Boundary validation failed; retry the affected boundary after correcting its writer output."
        ),
        recovery_action=RecoveryAction.RETRY,
    )
    if changed_sections:
        # A changed targeted repair remains a recoverable boundary failure, but
        # its exact validated result must survive the failure transition so the
        # linked writer successor can prove what was admitted.  Checkpoints are
        # retained by the generic failure state machine; output_json is cleared.
        await persist_checkpoint(
            job.session,
            work_item_id=item.id,
            worker_id=job.worker_id,
            lease_token=item.lease_token or 0,
            compatibility=compatibility,
            payload={
                "kind": "shared_lesson_boundary_repair_result",
                "work": work.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
            now=now,
        )
    await fail_work_item(
        job.session,
        work_item_id=item.id,
        worker_id=job.worker_id,
        lease_token=item.lease_token or 0,
        failure=failure,
        now=now,
    )
    return BoundaryRuntimeOutcome(
        work_item_id=item.id,
        result=result,
        error_code=failure.error_code,
        error_summary=failure.safe_summary,
        pending_replacement_section_ids=pending,
        preserved_ready_siblings=True,
    )


async def _advisory_issues_for_successor(
    session: Any,
    *,
    item: GenerationWorkItemModel,
    identity: SourceIdentity,
    work: BoundaryWorkOrder,
) -> tuple[ContinuityIssue, ...]:
    """Re-derive an advisory successor's issues from its predecessor's proof."""
    predecessor = await session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.id == item.replaces_work_item_id,
            GenerationWorkItemModel.stage == BOUNDARY_STAGE,
        )
    )
    if (
        predecessor is None
        or predecessor.status != "failed_recoverable"
        or predecessor.checkpoint_json is None
    ):
        raise BoundaryCheckpointError("boundary advisory predecessor proof is unavailable")
    original_work, proof = _verified_repair_proof(predecessor, identity)
    if original_work != work:
        raise BoundaryCheckpointError("boundary advisory is not bound to the original work order")
    if (
        item.input_hash != boundary_advisory_input_hash(work)
        or item.composition_identity
        != _composition_identity(
            work.previous_composition_identity, work.next_composition_identity
        )
        or item.definition_hash != hashlib.sha256(BOUNDARY_DEFINITION.encode("utf-8")).hexdigest()
    ):
        raise BoundaryCheckpointError("boundary advisory work item identity is stale")
    return _advisory_issues_from_result(proof)


async def _append_advisory_event(
    session: Any,
    *,
    item: GenerationWorkItemModel,
    work: BoundaryWorkOrder,
    issues: Sequence[ContinuityIssue],
) -> None:
    await append_event(
        session,
        run_id=item.run_id,
        work_item_id=item.id,
        event_type="boundary_advisory_accepted",
        safe_payload={
            "previous_section_id": work.previous_section_id,
            "next_section_id": work.next_section_id,
            "issue_codes": sorted({issue.issue_code for issue in issues}),
        },
    )


def _composition_identity_from_request(request: SectionWriterRequest) -> str:
    payload = request.composition_plan.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def execute_boundary_work_items(
    jobs: Sequence[BoundaryWorkItemJob],
    *,
    concurrency: int = MAX_CONCURRENT_BOUNDARIES,
) -> tuple[BoundaryRuntimeOutcome, ...]:
    """Execute independent boundary items under a bounded concurrency cap."""
    if not jobs:
        return ()
    if concurrency < 1 or concurrency > MAX_CONCURRENT_BOUNDARIES:
        raise ValueError(f"concurrency must be between 1 and {MAX_CONCURRENT_BOUNDARIES}")
    ids = [job.work_item_id for job in jobs]
    if len(ids) != len(set(ids)):
        raise BoundaryRuntimeError("boundary batch contains duplicate work item IDs")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(job: BoundaryWorkItemJob) -> BoundaryRuntimeOutcome:
        if job.status == "ready":
            return BoundaryRuntimeOutcome(
                work_item_id=job.work_item_id, preserved_ready_siblings=True
            )
        if job.status != "queued":
            return BoundaryRuntimeOutcome(
                work_item_id=job.work_item_id,
                error_code="boundary_item_not_queued",
                error_summary="Boundary batch accepts queued items only; retry failed items explicitly.",
                preserved_ready_siblings=True,
            )
        async with semaphore:
            try:
                outcome = await execute_boundary_work_item(job)
            except LeaseLostError:
                await _settle_boundary_job_session(job.session, commit=False)
                return BoundaryRuntimeOutcome(
                    work_item_id=job.work_item_id,
                    error_code="boundary_lease_lost",
                    error_summary="Boundary worker lease was lost before commit.",
                    preserved_ready_siblings=True,
                )
            except BoundaryRuntimeError as exc:
                await _settle_boundary_job_session(job.session, commit=False)
                return BoundaryRuntimeOutcome(
                    work_item_id=job.work_item_id,
                    error_code="boundary_contract_failure",
                    error_summary=str(exc),
                    preserved_ready_siblings=True,
                )
            except BaseException:
                await _settle_boundary_job_session(job.session, commit=False)
                raise
            try:
                # Each job owns this session. Persist its fenced READY/FAILED
                # transition now, rather than after gather waits for siblings.
                await _settle_boundary_job_session(job.session, commit=True)
            except BaseException:
                await _settle_boundary_job_session(job.session, commit=False)
                raise
            return outcome

    tasks = [asyncio.create_task(run_one(job)) for job in jobs]
    try:
        # A raw gather propagates the first unexpected exception immediately,
        # while sibling jobs may still be using their AsyncSessions. The
        # dispatcher's AsyncExitStack would then close those sessions under
        # their in-flight database operations and mask the original error.
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except asyncio.CancelledError:
        # Cancellation must settle every job before its owner closes the
        # sessions. Runtime provider calls are bounded by their configured
        # timeout, and DB work is awaited by each task before it can settle.
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise

    for result in results:
        if isinstance(result, BaseException):
            raise result
    return tuple(results)


async def _settle_boundary_job_session(session: Any, *, commit: bool) -> None:
    method = getattr(session, "commit" if commit else "rollback", None)
    if callable(method):
        await method()


__all__ = [
    "BOUNDARY_DEFINITION",
    "BOUNDARY_STAGE",
    "MAX_CONCURRENT_BOUNDARIES",
    "BoundaryCheckpointError",
    "BoundaryRuntimeError",
    "BoundaryRuntimeOutcome",
    "BoundarySourceConflict",
    "BoundaryWorkItemJob",
    "BoundaryWorkOrder",
    "accepted_section_output_hash",
    "BOUNDARY_ADVISORY_MARKER",
    "BOUNDARY_PENDING_REPLACEMENT_CODE",
    "admit_boundary_advisory_successor",
    "admit_boundary_replacement_work_item",
    "admit_boundary_work_item",
    "boundary_advisory_input_hash",
    "is_boundary_advisory_item",
    "unique_boundary_issues",
    "execute_boundary_work_item",
    "execute_boundary_work_items",
]
