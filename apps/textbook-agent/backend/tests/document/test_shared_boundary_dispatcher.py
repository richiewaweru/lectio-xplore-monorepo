from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from test_shared_composer_admission import _verifier
from test_shared_writer_admission import _seed_ready_composer_run

from document.shared_lesson import boundary as boundary_module
from document.shared_lesson import boundary_dispatcher, writer_repair_runtime
from document.shared_lesson.boundary import BoundarySemanticVerdict, ContinuityIssue
from document.shared_lesson.writer import validate_and_build_section
from document.shared_lesson.writer_admission import admit_writer_work_items
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash


async def _ready_writers(db_session, owner, run_id, source):
    admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    for admission in admissions:
        section = admission.section
        unique_opening = (
            "A compass uses magnetic forces to point north across a landscape. Travelers can navigate safely."
            if section.slot_id == "orient"
            else "A microscope magnifies tiny structures inside a sample. Scientists compare each observation carefully."
        )
        text = (
            f"{unique_opening} "
            + ". ".join(
                [
                    *section.entry_state,
                    *section.must_establish,
                    *([section.bridge_from_previous] if section.bridge_from_previous else []),
                    *section.exit_state,
                ]
            )
            + "."
        )
        draft = {
            "nodes": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "teaching_block_id": item.teaching_block_id,
                    "accessibility": {"description": "A clear explanation."},
                    "display": {"text": text},
                }
                for item in admission.request.composition_plan.items
                if item.kind == "paragraph"
            ]
        }
        output = validate_and_build_section(request=admission.request, draft=draft)
        item = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert item is not None
        payload = output.model_dump(mode="json")
        item.status = "ready"
        item.output_json = payload
        item.output_hash = content_hash(payload)
    await db_session.commit()
    return admissions


def _patch_approved_source(monkeypatch, source):
    async def load(**_kwargs):
        return source

    monkeypatch.setattr(boundary_dispatcher, "load_current_approved_teaching_plan_source", load)
    monkeypatch.setattr(
        boundary_dispatcher, "make_approved_source_verifier", lambda **_kw: _verifier
    )


async def _set_preparation_generation(db_session):
    from infra.database.models import PathLessonModel

    lesson = await db_session.get(PathLessonModel, "composer-admission-lesson")
    assert lesson is not None
    lesson.pack_id = "boundary-test-preparation"
    await db_session.commit()


async def _pass(_request):
    return BoundarySemanticVerdict(status="pass")


async def _issue(request):
    return BoundarySemanticVerdict(
        status="issue",
        issue=ContinuityIssue(
            issue_code="boundary_test_issue",
            affected_section_id=request.next_plan.slot_id,
            explanation="The example needs a clearer connection.",
            required_correction="Clarify the connection in the next section.",
        ),
    )


@pytest.mark.asyncio
async def test_dispatch_admits_and_passes_adjacent_boundaries_on_same_run(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_pass,
    )
    assert result.state == "passed", result
    assert len(result.admitted_work_item_ids) == 1
    row = await db_session.get(GenerationWorkItemModel, result.admitted_work_item_ids[0])
    assert row is not None and row.run_id == run_id and row.status == "ready"


@pytest.mark.asyncio
async def test_boundary_aggregate_deadline_fails_recoverably_before_lease_expiry(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)
    provider_cancelled = asyncio.Event()
    release_provider = asyncio.Event()
    provider_finished = asyncio.Event()

    async def slow_semantic_review(_request):
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            provider_cancelled.set()
            await release_provider.wait()
        provider_finished.set()
        return BoundarySemanticVerdict(
            status="issue",
            issue=ContinuityIssue(
                issue_code="late_boundary_issue",
                affected_section_id=_request.next_plan.slot_id,
                explanation="The late review found a boundary issue.",
                required_correction="Clarify the boundary in the affected section.",
            ),
        )

    class LateRepair:
        calls = 0

        async def repair_section(self, _request):
            self.calls += 1
            raise AssertionError("deadline must prevent a late repair call")

    repair = LateRepair()

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=slow_semantic_review,
        repair_engine=repair,
        lease_seconds=1,
    )

    assert result.state == "pending_repair"
    assert len(result.pending_repair_work_item_ids) == 1
    assert result.outcomes[0].error_code == "boundary_validation_timeout"
    await asyncio.wait_for(provider_cancelled.wait(), timeout=0.1)
    assert provider_finished.is_set() is False
    boundary = await db_session.get(
        GenerationWorkItemModel, result.pending_repair_work_item_ids[0]
    )
    assert boundary is not None and boundary.status == "failed_recoverable"
    for admission in admissions:
        writer = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert writer is not None and writer.status == "ready"
    release_provider.set()
    await asyncio.wait_for(provider_finished.wait(), timeout=0.2)
    assert repair.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("writer_state", ["missing", "queued", "stale"])
async def test_missing_or_nonready_writer_blocks_boundary_admission(
    db_session, db_session_factory, monkeypatch, writer_state
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    first_writer = await db_session.get(GenerationWorkItemModel, admissions[0].work_item_id)
    assert first_writer is not None
    if writer_state == "missing":
        await db_session.delete(first_writer)
    elif writer_state == "stale":
        first_writer.status = "ready"
        first_writer.output_json = {"invalid": "stale writer output"}
        first_writer.output_hash = content_hash(first_writer.output_json)
    await db_session.commit()
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )

    assert result.state == "blocked"
    boundary_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "continuity_validation",
                )
            )
        ).all()
    )
    assert boundary_rows == []
    for admission in admissions[1:]:
        row = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert row is not None and row.status == "queued"


@pytest.mark.asyncio
async def test_duplicate_dispatch_reuses_ready_boundary_identity(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    first = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )
    second = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )

    assert first.state == second.state == "passed", (first, second)
    assert first.admitted_work_item_ids == second.admitted_work_item_ids


@pytest.mark.asyncio
async def test_one_section_plan_returns_without_admitting_a_boundary(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    first_plan_section = source.plan.sections[0]
    one_section_source = source.model_copy(
        update={"plan": source.plan.model_copy(update={"sections": (first_plan_section,)})}
    )
    run = await db_session.get(GenerationRunModel, run_id)
    assert run is not None

    async def verified(_session, **_kwargs):
        from document.shared_lesson.models import SharedSection

        return (
            one_section_source,
            SimpleNamespace(id=run.id),
            (
                SharedSection(
                    id=first_plan_section.slot_id,
                    title=first_plan_section.display_title,
                    position=0,
                    nodes=(),
                ),
            ),
            {},
            {},
        )

    monkeypatch.setattr(boundary_dispatcher, "_verified_run_inputs", verified)
    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner
    )
    assert result.state == "no_boundaries"
    assert result.admitted_work_item_ids == ()


@pytest.mark.asyncio
async def test_boundary_failure_is_pending_repair_and_preserves_ready_writers(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)

    result = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_issue,
    )

    assert result.state == "pending_repair"
    assert len(result.pending_repair_work_item_ids) == 1
    for admission in admissions:
        writer = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert writer is not None and writer.status == "ready"


# ---------------------------------------------------------------------------
# Boundary-triggered targeted writer repair: admit the linked writer
# replacement, then the linked boundary replacement, bounded to one repair.
# ---------------------------------------------------------------------------


class _ChangingRepair:
    """A targeted repair engine that always returns a changed section."""

    def __init__(self):
        self.calls = 0

    _ATTEMPT_WORDS = ("first", "second", "third", "fourth")

    async def repair_section(self, request):
        self.calls += 1
        attempt_word = self._ATTEMPT_WORDS[self.calls - 1]
        items = [
            item
            for item in request.writer_request.composition_plan.items
            if item.kind == "paragraph"
        ]
        draft = {
            "nodes": [
                {
                    "id": item.id,
                    "kind": item.kind,
                    "teaching_block_id": item.teaching_block_id,
                    "accessibility": {"description": "A clearer explanation."},
                    "display": {
                        "text": (
                            f"This is the {attempt_word} repaired connection. A magnifier "
                            "bridges the compass discussion to microscopic detail."
                        )
                    },
                }
                for item in items
            ]
        }
        return validate_and_build_section(request=request.writer_request, draft=draft)


def _once_issue_then_pass():
    state = {"calls": 0}

    async def validator(request):
        state["calls"] += 1
        if state["calls"] == 1:
            return BoundarySemanticVerdict(
                status="issue",
                issue=ContinuityIssue(
                    issue_code="boundary_test_issue",
                    affected_section_id=request.next_plan.slot_id,
                    explanation="The example needs a clearer connection.",
                    required_correction="Clarify the connection in the next section.",
                ),
            )
        return BoundarySemanticVerdict(status="pass")

    return validator


def _bypass_deterministic_continuity_checks(monkeypatch):
    """The deterministic continuity/boundary checks are exercised in
    ``test_shared_boundary_runtime.py`` and ``continuity.py``'s own tests.
    Bypassing them here (as the writer-repair unit tests already do) keeps
    this dispatcher-level test focused on the admission/execution/replacement
    plumbing rather than on crafting text that satisfies every deterministic
    continuity heuristic."""
    for module in (boundary_module, writer_repair_runtime):
        monkeypatch.setattr(module, "validate_section_boundary", lambda **_kwargs: ())
        monkeypatch.setattr(module, "validate_section_continuity", lambda **_kwargs: ())


@pytest.mark.asyncio
async def test_dispatch_admits_writer_repair_and_replacement_boundary_then_passes(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)
    _bypass_deterministic_continuity_checks(monkeypatch)

    explain_admission = next(a for a in admissions if a.section.slot_id == "explain")
    original_writer_id = explain_admission.work_item_id

    repair = _ChangingRepair()
    semantic = _once_issue_then_pass()

    first = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=semantic,
        repair_engine=repair,
    )
    assert first.state == "pending_repair", first
    assert repair.calls == 1

    # The dispatcher committed through its own session_factory sessions; this
    # test's own session must reload rather than trust its identity-map cache.
    original_writer = await db_session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == original_writer_id)
        .execution_options(populate_existing=True)
    )
    assert original_writer is not None and original_writer.status == "ready"
    replacement_writer = await db_session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.replaces_work_item_id == original_writer_id)
        .execution_options(populate_existing=True)
    )
    assert replacement_writer is not None and replacement_writer.status == "ready"
    assert replacement_writer.output_json != original_writer.output_json

    boundary_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "continuity_validation",
                )
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    original_boundary = next(row for row in boundary_rows if row.replaces_work_item_id is None)
    assert original_boundary.status == "failed_recoverable"
    assert original_boundary.error_code == "boundary_repair_pending_writer_replacement"
    replacement_boundary = next(
        row for row in boundary_rows if row.replaces_work_item_id == original_boundary.id
    )
    assert replacement_boundary.status == "queued"

    second = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_pass,
    )
    assert second.state == "passed", second
    # The one bounded provider repair call is never repeated.
    assert repair.calls == 1

    refreshed_replacement_boundary = await db_session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == replacement_boundary.id)
        .execution_options(populate_existing=True)
    )
    assert refreshed_replacement_boundary is not None
    assert refreshed_replacement_boundary.status == "ready"


@pytest.mark.asyncio
async def test_dispatch_completes_boundary_with_advisories_when_replacement_needs_second_repair(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)
    _bypass_deterministic_continuity_checks(monkeypatch)

    # The same repair engine instance is reused across both dispatch calls so
    # its second repair produces text that actually differs from the first
    # repair's already-accepted output (otherwise the second attempt would be
    # a no-op change and never exercise the exhaustion path at all).
    repair = _ChangingRepair()
    first = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_once_issue_then_pass(),
        repair_engine=repair,
    )
    assert first.state == "pending_repair", first
    assert repair.calls == 1

    # The replacement boundary now needs a second changed repair; the bounded
    # writer-repair budget is exhausted, so it completes in place on its
    # current sections with advisories rather than admit a second writer
    # replacement or fail the run.
    second = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory,
        run_id=run_id,
        owner_user_id=owner,
        semantic_validator=_once_issue_then_pass(),
        repair_engine=repair,
    )
    assert second.state == "passed", second
    assert repair.calls == 2

    boundary_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "continuity_validation",
                )
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    assert not [row for row in boundary_rows if row.status == "failed_terminal"]
    completed = [
        row for row in boundary_rows if row.status == "ready" and row.replaces_work_item_id
    ]
    assert len(completed) == 1
    assert completed[0].output_json["status"] == "pass"
    assert completed[0].output_json["advisories"], completed[0].output_json
    assert completed[0].output_json["advisories"][0]["issue_code"] == "boundary_test_issue"

    writer_rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "section_writing",
                )
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    explain_chain = [row for row in writer_rows if row.item_key.startswith("write:explain")]
    # Exactly one writer repair -- never a second -- was admitted.
    assert len(explain_chain) == 2

    run = await db_session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .execution_options(populate_existing=True)
    )
    assert run is not None and run.status != "failed_terminal"

    third = await boundary_dispatcher.dispatch_shared_document_boundaries(
        db_session_factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass
    )
    assert third.state == "passed", third
