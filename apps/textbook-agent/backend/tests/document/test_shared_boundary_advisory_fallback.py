"""Multi-issue boundary repair, deterministic advisory fallback and safe retry."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update
from test_shared_boundary_dispatcher import (
    _bypass_deterministic_continuity_checks,
    _ChangingRepair,
    _patch_approved_source,
    _pass,
    _ready_writers,
    _set_preparation_generation,
)
from test_shared_composer_admission import _verifier  # noqa: F401
from test_shared_writer_admission import _seed_ready_composer_run

from document.shared_lesson import boundary_dispatcher
from document.shared_lesson import boundary_runtime
from document.shared_lesson.boundary import BoundaryValidationResult
from document.shared_lesson.boundary_recovery import (
    looks_like_recoverable_boundary_leaf,
    recover_boundary_repair_leaves,
)
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.finalizer import SharedLessonFinalizationError  # noqa: F401
from document.shared_lesson.post_section_pipeline import _boundary_quality_flags
from document.shared_lesson.quality_flags import QualityFlag, boundary_transition_flag
from document.shared_lesson.run_failure import summarize_failed_leaves
from document.shared_lesson.writer_repair_runtime import (
    WriterRepairRuntimeError,
    WriterRepairWorkOrder,
)
from infra.database.models import (
    GenerationEventModel,
    GenerationRunModel,
    GenerationWorkItemModel,
)
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import retry_work_item


def _issue(section_id: str, code: str = "boundary_bridge_missing") -> ContinuityIssue:
    return ContinuityIssue(
        issue_code=code,
        affected_section_id=section_id,
        affected_node_ids=("n1",),
        explanation=f"{code} in {section_id}",
        required_correction=f"fix {code}",
    )


def _install_fake_validation(monkeypatch, *, issues, change):
    """First boundary validation returns a crafted repaired result; later ones are real."""
    real = boundary_runtime.validate_and_repair_boundary
    state = {"calls": 0}

    async def fake(**kwargs):
        state["calls"] += 1
        if state["calls"] > 1:
            return await real(**kwargs)
        previous, next_ = kwargs["previous_section"], kwargs["next_section"]
        requests = kwargs["writer_requests"]
        repair = _ChangingRepair()
        repaired = {}
        for section in (previous, next_):
            if section.id in change:
                result = await repair.repair_section(
                    SimpleNamespace(writer_request=requests[section.id])
                )
                repaired[section.id] = result.as_shared_section(
                    section_id=section.id, position=section.position
                )
        return BoundaryValidationResult(
            status="pass",
            previous_section=repaired.get(previous.id, previous),
            next_section=repaired.get(next_.id, next_),
            initial_issues=tuple(issues),
            repair_attempted=True,
            semantic_calls=1,
        )

    monkeypatch.setattr(boundary_runtime, "validate_and_repair_boundary", fake)
    return state


async def _setup(db_session, monkeypatch):
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    await _set_preparation_generation(db_session)
    admissions = await _ready_writers(db_session, owner, run_id, source)
    _patch_approved_source(monkeypatch, source)
    _bypass_deterministic_continuity_checks(monkeypatch)
    return owner, run_id, source, admissions


async def _rows(db_session, run_id, stage):
    return list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel)
                .where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == stage,
                )
                .execution_options(populate_existing=True)
            )
        ).all()
    )


async def _events(db_session, run_id, event_type):
    return list(
        (
            await db_session.scalars(
                select(GenerationEventModel)
                .where(
                    GenerationEventModel.run_id == run_id,
                    GenerationEventModel.event_type == event_type,
                )
                .execution_options(populate_existing=True)
            )
        ).all()
    )


async def _dispatch(factory, owner, run_id, **kwargs):
    return await boundary_dispatcher.dispatch_shared_document_boundaries(
        factory, run_id=run_id, owner_user_id=owner, semantic_validator=_pass, **kwargs
    )


# ---------------------------------------------------------------------------
# identity stability
# ---------------------------------------------------------------------------


def test_legacy_single_issue_work_order_dump_and_hash_are_unchanged() -> None:
    fields = WriterRepairWorkOrder.model_fields
    assert "additional_issues" in fields
    # Build a minimal order through model_construct-free validation of a dump.
    from test_shared_writer_repair_runtime import (  # noqa: PLC0415
        _request,
        _section,
        _source,
    )

    source = _source()
    request = _request(source, "s2")
    section = _section("s2", 1, "Replacement text for the second idea.")
    from document.shared_lesson.runtime import _stable_hash  # noqa: PLC0415
    from document.shared_lesson.writer import validate_and_build_section  # noqa: PLC0415
    from document.shared_lesson.writer import ordinary_nodes_as_draft  # noqa: PLC0415

    replacement = validate_and_build_section(
        request=request, draft=ordinary_nodes_as_draft(section.nodes)
    )
    from infra.generation_runtime import SourceIdentity  # noqa: PLC0415

    base = dict(
        source=SourceIdentity(
            source_artifact_type="teaching_plan",
            source_artifact_id="p",
            source_revision=1,
            source_hash="h",
        ),
        section_id="s2",
        composition_identity=_stable_hash(request.composition_plan.model_dump(mode="json")),
        prior_writer_work_item_id="w",
        prior_writer_output_hash="o",
        boundary_work_item_id="b",
        accepted_section_output_hash="a" * 64,
        issue=_issue("s2"),
        previous_section=_section("s1", 0, "First."),
        next_section=section,
        replacement=replacement,
    )
    legacy = WriterRepairWorkOrder(**base)
    dump = legacy.model_dump(mode="json")
    assert "additional_issues" not in dump
    assert legacy.identity_hash == WriterRepairWorkOrder._hash_payload(dump)
    # A persisted legacy payload loads and re-dumps identically.
    assert WriterRepairWorkOrder.model_validate(dump).model_dump(mode="json") == dump
    assert legacy.issues == (legacy.issue,)
    multi = WriterRepairWorkOrder(**base, additional_issues=(_issue("s2", "boundary_repetition"),))
    assert "additional_issues" in multi.model_dump(mode="json")
    assert multi.identity_hash != legacy.identity_hash
    assert len(multi.issues) == 2


def test_legacy_quality_flag_dict_still_loads_and_dumps_unchanged() -> None:
    legacy = {
        "code": "x",
        "severity": "warning",
        "source": "semantic_qa",
        "message": "m",
        "section_id": "s",
        "node_ids": [],
        "required_correction": "c",
    }
    flag = QualityFlag.model_validate(legacy)
    assert flag.model_dump(mode="json") == legacy
    assert content_hash(flag.model_dump(mode="json")) == content_hash(legacy)


def test_boundary_flag_is_plain_language_one_per_boundary() -> None:
    flag = boundary_transition_flag(
        previous_section_id="a",
        next_section_id="b",
        previous_title="Two Raw Materials",
        next_title="Pairing Each Material",
        issues=(_issue("b", "boundary_bridge_missing"), _issue("b", "boundary_repetition")),
    )
    assert flag.source == "boundary_check" and flag.code == "boundary_transition_warning"
    assert "Two Raw Materials" in flag.message and "Pairing Each Material" in flag.message
    assert "repeat earlier wording" in flag.message and "skip the planned bridge" in flag.message
    assert "boundary_" not in flag.message and "boundary_" not in flag.required_correction
    assert flag.section_id == "b"
    assert flag.internal_issue_codes == ("boundary_bridge_missing", "boundary_repetition")
    assert QualityFlag.model_validate(flag.model_dump(mode="json")) == flag


# ---------------------------------------------------------------------------
# multi-issue same-section repair
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_issues_same_section_admit_writer_replacement_then_pass(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, _source, admissions = await _setup(db_session, monkeypatch)
    _install_fake_validation(
        monkeypatch,
        issues=(_issue("explain"), _issue("explain", "boundary_repetition")),
        change={"explain"},
    )
    first = await _dispatch(db_session_factory, owner, run_id)
    assert first.state == "pending_repair", first
    original = next(a.work_item_id for a in admissions if a.section.slot_id == "explain")
    replacement = await db_session.scalar(
        select(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.replaces_work_item_id == original)
        .execution_options(populate_existing=True)
    )
    assert replacement is not None and replacement.status == "ready"
    checkpoint = replacement.checkpoint_json["payload"]["work"]
    assert len(checkpoint["additional_issues"]) == 1
    second = await _dispatch(db_session_factory, owner, run_id)
    assert second.state == "passed", second
    assert not await _events(db_session, run_id, "boundary_repair_skipped")


# ---------------------------------------------------------------------------
# advisory fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issues_in_both_sections_fall_back_to_advisory(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, _source, admissions = await _setup(db_session, monkeypatch)
    _install_fake_validation(
        monkeypatch, issues=(_issue("orient"), _issue("explain")), change={"explain"}
    )
    first = await _dispatch(db_session_factory, owner, run_id)
    assert first.state in {"pending", "pending_repair"}, first
    # No writer replacement: both originals are kept.
    writers = await _rows(db_session, run_id, "section_writing")
    assert len(writers) == len(admissions)
    assert all(row.status == "ready" and row.replaces_work_item_id is None for row in writers)

    second = await _dispatch(db_session_factory, owner, run_id)
    assert second.state == "passed", second
    boundaries = await _rows(db_session, run_id, "continuity_validation")
    ready = [b for b in boundaries if b.status == "ready"]
    assert len(ready) == 1 and ":advisory:" in ready[0].item_key
    output = ready[0].output_json
    assert output["semantic_calls"] == 0 and output["status"] == "pass"
    assert {issue["affected_section_id"] for issue in output["advisories"]} == {
        "orient",
        "explain",
    }
    events = await _events(db_session, run_id, "boundary_advisory_accepted")
    assert len(events) == 1
    assert events[0].safe_payload_json["previous_section_id"] == "orient"

    sections = {
        "orient": SimpleNamespace(id="orient", title="Orient Title", position=0),
        "explain": SimpleNamespace(id="explain", title="Explain Title", position=1),
    }
    flags = _boundary_quality_flags(ready, sections)
    assert len(flags) == 1
    assert flags[0].source == "boundary_check"
    assert "Orient Title" in flags[0].message and "Explain Title" in flags[0].message


@pytest.mark.asyncio
async def test_admission_conflict_falls_back_with_skip_event(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, _source, _admissions = await _setup(db_session, monkeypatch)
    _install_fake_validation(monkeypatch, issues=(_issue("explain"),), change={"explain"})

    async def reject(*_a, **_k):
        raise WriterRepairRuntimeError("conflict")

    monkeypatch.setattr(boundary_dispatcher, "admit_writer_repair_work_item", reject)
    assert (await _dispatch(db_session_factory, owner, run_id)).state in {"pending", "pending_repair"}
    skipped = await _events(db_session, run_id, "boundary_repair_skipped")
    assert [e.safe_payload_json["reason"] for e in skipped] == ["writer_repair_admission_rejected"]
    assert (await _dispatch(db_session_factory, owner, run_id)).state == "passed"
    assert await _events(db_session, run_id, "boundary_advisory_accepted")


@pytest.mark.asyncio
async def test_repair_changing_both_sections_falls_back_to_advisory(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, _source, _admissions = await _setup(db_session, monkeypatch)
    _install_fake_validation(
        monkeypatch, issues=(_issue("explain"),), change={"orient", "explain"}
    )
    # The checkpointed repair changed both sections: no single writer repair applies.
    assert (await _dispatch(db_session_factory, owner, run_id)).state in {"pending", "pending_repair"}
    assert (await _dispatch(db_session_factory, owner, run_id)).state == "passed"
    assert await _events(db_session, run_id, "boundary_advisory_accepted")


# ---------------------------------------------------------------------------
# safe manual retry and recovery
# ---------------------------------------------------------------------------


async def _stall(db_session, db_session_factory, monkeypatch):
    owner, run_id, source, admissions = await _setup(db_session, monkeypatch)
    state = _install_fake_validation(monkeypatch, issues=(_issue("explain"),), change={"explain"})

    async def reject(*_a, **_k):
        raise WriterRepairRuntimeError("conflict")

    async def reject_advisory(*_a, **_k):
        raise boundary_runtime.BoundarySourceConflict("blocked")

    patches = (
        pytest.MonkeyPatch(),
        pytest.MonkeyPatch(),
    )
    patches[0].setattr(boundary_dispatcher, "admit_writer_repair_work_item", reject)
    patches[1].setattr(boundary_dispatcher, "admit_boundary_advisory_successor", reject_advisory)
    first = await _dispatch(db_session_factory, owner, run_id)
    assert first.state == "pending_repair", first
    leaf = (await _rows(db_session, run_id, "continuity_validation"))[0]
    assert leaf.status == "failed_recoverable"
    assert leaf.error_code == "boundary_repair_pending_writer_replacement"
    return owner, run_id, leaf, state, patches


@pytest.mark.asyncio
async def test_manual_retry_of_pending_leaf_refails_without_integrity_or_provider_call(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, leaf, state, patches = await _stall(db_session, db_session_factory, monkeypatch)
    try:
        await retry_work_item(db_session, work_item_id=leaf.id, owner_user_id=owner)
        await db_session.commit()
        calls_before = state["calls"]
        result = await _dispatch(db_session_factory, owner, run_id)
        assert result.state == "pending_repair"
        assert state["calls"] == calls_before  # no provider/validation re-run
        refreshed = (await _rows(db_session, run_id, "continuity_validation"))[0]
        assert refreshed.status == "failed_recoverable"
        assert refreshed.error_code == "boundary_repair_pending_writer_replacement"
        assert refreshed.recovery_action == "review"
        assert refreshed.attempt == 2
    finally:
        for patch in patches:
            patch.undo()
    # With the fallback available again the stalled run now resolves.
    assert (await _dispatch(db_session_factory, owner, run_id)).state in {"pending", "pending_repair"}
    assert (await _dispatch(db_session_factory, owner, run_id)).state == "passed"


@pytest.mark.asyncio
async def test_terminal_integrity_leaf_with_valid_proof_is_recovered_by_retry(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, leaf, _state, patches = await _stall(db_session, db_session_factory, monkeypatch)
    for patch in patches:
        patch.undo()
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == leaf.id)
        .values(
            status="failed_terminal",
            error_code="boundary_checkpoint_integrity",
            error_class="unsupported_contract",
            recovery_action="none",
        )
    )
    await db_session.execute(
        update(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .values(status="failed_terminal")
    )
    await db_session.commit()
    row = (await _rows(db_session, run_id, "continuity_validation"))[0]
    assert looks_like_recoverable_boundary_leaf(row)
    summary = summarize_failed_leaves([row])
    assert summary is not None and summary.recovery_action == "retry"
    assert summary.boundary_recoverable and summary.retryable

    assert await recover_boundary_repair_leaves(db_session, run_id=run_id, owner_user_id=owner)
    await db_session.commit()
    row = (await _rows(db_session, run_id, "continuity_validation"))[0]
    assert row.status == "queued" and row.error_code is None
    run = await db_session.scalar(
        select(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .execution_options(populate_existing=True)
    )
    assert run.status == "queued"
    assert await _events(db_session, run_id, "work_item_resolution_queued")

    # Normal dispatch resolves it (re-fail with proof, then advisory fallback).
    result = await _dispatch(db_session_factory, owner, run_id)
    assert result.state in {"pending", "pending_repair"}
    assert (await _dispatch(db_session_factory, owner, run_id)).state == "passed"


@pytest.mark.asyncio
async def test_genuine_corruption_is_not_recovered(db_session, db_session_factory, monkeypatch):
    owner, run_id, leaf, _state, patches = await _stall(db_session, db_session_factory, monkeypatch)
    for patch in patches:
        patch.undo()
    tampered = copy.deepcopy(leaf.checkpoint_json)
    tampered["payload_hash"] = "0" * 64
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == leaf.id)
        .values(
            status="failed_terminal",
            error_code="boundary_checkpoint_integrity",
            error_class="unsupported_contract",
            recovery_action="none",
            checkpoint_json=tampered,
        )
    )
    await db_session.execute(
        update(GenerationRunModel)
        .where(GenerationRunModel.id == run_id)
        .values(status="failed_terminal")
    )
    await db_session.commit()
    assert not await recover_boundary_repair_leaves(
        db_session, run_id=run_id, owner_user_id=owner
    )
    row = (await _rows(db_session, run_id, "continuity_validation"))[0]
    assert row.status == "failed_terminal"
    # A boundary that never reached repair (no checkpoint) is not recoverable either.
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == leaf.id)
        .values(checkpoint_json=None)
    )
    await db_session.commit()
    assert not await recover_boundary_repair_leaves(
        db_session, run_id=run_id, owner_user_id=owner
    )


@pytest.mark.asyncio
async def test_advisory_admission_blocks_when_writer_output_changed(
    db_session, db_session_factory, monkeypatch
):
    """Source/identity mismatch keeps the boundary blocked (skip event, no successor)."""
    owner, run_id, _source, _admissions = await _setup(db_session, monkeypatch)
    _install_fake_validation(
        monkeypatch, issues=(_issue("orient"), _issue("explain")), change={"explain"}
    )
    real_admit = boundary_runtime.admit_boundary_advisory_successor

    async def mismatched(session, **kwargs):
        # Present a different pair than the proof's original one.
        kwargs["next_section"] = kwargs["next_section"].model_copy(update={"title": "Changed"})
        return await real_admit(session, **kwargs)

    monkeypatch.setattr(boundary_dispatcher, "admit_boundary_advisory_successor", mismatched)
    result = await _dispatch(db_session_factory, owner, run_id)
    assert result.state == "pending_repair", result
    skipped = await _events(db_session, run_id, "boundary_repair_skipped")
    assert skipped and skipped[0].safe_payload_json["reason"].startswith(
        "advisory_admission_rejected:BoundarySourceConflict"
    )
    boundaries = await _rows(db_session, run_id, "continuity_validation")
    assert len(boundaries) == 1 and boundaries[0].status == "failed_recoverable"


# ---------------------------------------------------------------------------
# Real validator: findings on both sections complete in place with advisories.
# ---------------------------------------------------------------------------


def _both_sides_deterministic(monkeypatch):
    """Deterministic narrative issues on BOTH sections (real validate_and_repair_boundary)."""
    from document.shared_lesson import boundary as boundary_module

    monkeypatch.setattr(
        boundary_module,
        "validate_section_boundary",
        lambda **_kwargs: (
            _issue("explain", "boundary_repetition"),
            _issue("orient", "boundary_repetition"),
        ),
    )


@pytest.mark.asyncio
async def test_real_validator_issues_on_both_sections_complete_with_advisories(
    db_session, db_session_factory, monkeypatch
):
    owner, run_id, _source, admissions = await _setup(db_session, monkeypatch)
    _both_sides_deterministic(monkeypatch)
    repair = _ChangingRepair()
    result = await _dispatch(db_session_factory, owner, run_id, repair_engine=repair)
    assert result.state == "passed", result
    assert repair.calls == 0  # no repair, no further provider calls
    boundaries = await _rows(db_session, run_id, "continuity_validation")
    assert len(boundaries) == 1 and boundaries[0].status == "ready"
    output = boundaries[0].output_json
    assert output["status"] == "pass" and output["semantic_calls"] == 0
    assert {i["affected_section_id"] for i in output["advisories"]} == {"orient", "explain"}
    assert await _events(db_session, run_id, "boundary_advisory_accepted")
    writers = await _rows(db_session, run_id, "section_writing")
    assert len(writers) == len(admissions)
    sections = {
        "orient": SimpleNamespace(id="orient", title="Orient Title", position=0),
        "explain": SimpleNamespace(id="explain", title="Explain Title", position=1),
    }
    flags = _boundary_quality_flags(boundaries, sections)
    assert len(flags) == 1 and flags[0].source == "boundary_check"
    assert "repeat earlier wording" in flags[0].message


@pytest.mark.asyncio
async def test_non_narrative_ambiguous_failure_keeps_blocking(
    db_session, db_session_factory, monkeypatch
):
    from document.shared_lesson import boundary as boundary_module

    owner, run_id, _source, _admissions = await _setup(db_session, monkeypatch)
    monkeypatch.setattr(
        boundary_module,
        "validate_section_boundary",
        lambda **_kwargs: (
            _issue("explain", "section_structure_broken"),
            _issue("orient", "boundary_repetition"),
        ),
    )
    result = await _dispatch(db_session_factory, owner, run_id)
    assert result.state == "pending_repair", result
    boundaries = await _rows(db_session, run_id, "continuity_validation")
    assert boundaries[0].status == "failed_recoverable"
    assert boundaries[0].error_code == "boundary_repair_ambiguous"


# ---------------------------------------------------------------------------
# End to end through the real post-section pipeline entry point.
# ---------------------------------------------------------------------------


def _patch_pipeline_source(monkeypatch, source):
    from document.shared_lesson import post_section_pipeline as pipeline

    async def load(**_kwargs):
        return source

    monkeypatch.setattr(pipeline, "load_current_approved_teaching_plan_source", load)


async def _run_pipeline(factory, owner, run_id):
    from document.shared_lesson.post_section_pipeline import run_post_section_pipeline

    return await run_post_section_pipeline(
        factory,
        run_id=run_id,
        owner_user_id=owner,
        path_lesson_id="composer-admission-lesson",
        preparation_generation_id="boundary-test-preparation",
        boundary_semantic_validator=_pass,
        boundary_repair_engine=_ChangingRepair(),
        media_executor=SimpleNamespace(),
        qa_semantic_validator=_pass,
        worker_id="e2e-post-section",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["same_section_two_issues", "both_sections"])
async def test_pipeline_gets_past_boundaries_from_multi_issue_state(
    db_session, db_session_factory, monkeypatch, scenario
):
    owner, run_id, source, _admissions = await _setup(db_session, monkeypatch)
    _patch_pipeline_source(monkeypatch, source)
    if scenario == "same_section_two_issues":
        _install_fake_validation(
            monkeypatch,
            issues=(_issue("explain"), _issue("explain", "boundary_repetition")),
            change={"explain"},
        )
    else:
        _both_sides_deterministic(monkeypatch)

    outcomes = [await _run_pipeline(db_session_factory, owner, run_id) for _ in range(3)]
    # The seeded harness has no preparation generation, so the media stage is as far
    # as it can go; reaching it proves the boundary stage no longer stalls the run.
    assert outcomes[-1].stage == "media", outcomes
    boundaries = await _rows(db_session, run_id, "continuity_validation")
    assert any(row.status == "ready" for row in boundaries)
    assert not [row for row in boundaries if row.status == "failed_terminal"]
