from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import (
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
    TeachingRevisionRecord,
)
from document.shared_lesson import boundary_runtime
from document.shared_lesson import writer_repair_runtime as runtime
from document.shared_lesson.boundary import BoundaryValidationResult
from document.shared_lesson.composer import CompositionChoice, validate_and_build_composition
from document.shared_lesson.continuity import ContinuityIssue
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode, SharedSection
from document.shared_lesson.runtime import (
    TeachingPlanSource,
    _stable_hash,
    make_section_writer_request,
)
from document.shared_lesson.writer import SectionWriteResult
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import (
    LeaseLostError,
    RuntimeCheckpoint,
    RuntimeCheckpointCompatibility,
)


def _source() -> TeachingPlanSource:
    sections = tuple(
        TeachingPlanSection(
            slot_id=slot,
            display_title=f"Section {slot}",
            entry_state=[f"Learner enters {slot}"],
            must_establish=[f"Learner understands {slot}"],
            avoid_repeating=[],
            bridge_from_previous=(None if slot == "s1" else "Connect s1 to s2"),
            exit_state=[f"Learner exits {slot}"],
            blocks=[
                TeachingPlanBlock(
                    id=f"{slot}-block",
                    position=0,
                    intent=f"Teach {slot}",
                    brief=f"Explain {slot}",
                    evidence=f"Learner explains {slot}",
                )
            ],
        )
        for slot in ("s1", "s2")
    )
    plan = TeachingPlan(
        arc="Teach two connected ideas",
        contract_version=2,
        learner_title="Two ideas",
        starting_state=["Learner is ready"],
        target_state=["Learner can explain both ideas"],
        teaching_plan_id="repair-plan",
        revision=2,
        approval_status="approved",
        sections=list(sections),
    )
    digest = teaching_plan_content_hash(plan)
    record = TeachingRevisionRecord(
        teaching_plan_id=plan.teaching_plan_id,
        revision=plan.revision,
        status="approved",
        preparation_hash="prep-hash",
        content_hash=digest,
        plan=plan.model_dump(mode="json"),
        created_at="2026-09-24T00:00:00Z",
        approved_at="2026-09-24T00:00:00Z",
        reviewed_by="teacher",
        approval_hash_binding="submitted",
    )
    return TeachingPlanSource(
        plan=plan,
        revision_record=record,
        id=plan.teaching_plan_id,
        revision=plan.revision,
        content_hash=digest,
    )


def _section(section_id: str, position: int, text: str) -> SharedSection:
    node_id = (
        "shared-node-"
        + hashlib.sha256(
            f"{section_id}{chr(0)}{section_id}-block{chr(0)}0{chr(0)}paragraph{chr(0)}explanation".encode()
        ).hexdigest()[:20]
    )
    return SharedSection(
        id=section_id,
        title=f"Section {section_id}",
        position=position,
        nodes=(
            ParagraphNode(
                id=node_id,
                teaching_block_id=f"{section_id}-block",
                display=ParagraphDisplay(text=text),
            ),
        ),
    )


def _request(source: TeachingPlanSource, section_id: str):
    section = next(section for section in source.plan.sections if section.slot_id == section_id)
    composition = validate_and_build_composition(
        section=section,
        choices=(
            CompositionChoice(
                kind="paragraph",
                teaching_block_id=f"{section_id}-block",
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    return make_section_writer_request(section=section, composition=composition, tasks=())


def _issue() -> ContinuityIssue:
    return ContinuityIssue(
        issue_code="boundary_bridge_missing",
        affected_section_id="s2",
        affected_node_ids=("s2-node",),
        explanation="The opening needs the approved bridge.",
        required_correction="Add the approved bridge to the opening.",
    )


def _result(section: SharedSection) -> SectionWriteResult:
    return SectionWriteResult(
        section_slot_id=section.id,
        title=section.title,
        nodes=section.nodes,
    )


def _boundary_result(previous: SharedSection, original: SharedSection, repaired: SharedSection):
    return BoundaryValidationResult(
        status="pass",
        previous_section=previous,
        next_section=repaired,
        initial_issues=(_issue(),),
        repair_attempted=True,
        semantic_calls=2,
    )


@pytest.mark.asyncio
async def test_admission_binds_exact_issue_plan_composition_and_prior_output(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    request = _request(source, "s2")
    prior_result = _result(original)
    predecessor = SimpleNamespace(
        id="writer-old",
        item_key="write:s2",
        replaces_work_item_id=None,
        run_id="run-1",
        stage="section_writing",
        status="ready",
        output_json=prior_result.model_dump(mode="json"),
        output_hash=content_hash(prior_result.model_dump(mode="json")),
        composition_identity=_stable_hash(request.composition_plan.model_dump(mode="json")),
    )

    class Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            return predecessor if self.calls == 1 else None

    captured = []

    async def fake_replace(_session, request):
        captured.append(request)
        return "replacement-row"

    monkeypatch.setattr(runtime, "replace_work_item", fake_replace)

    async def no_boundary_proof(*_args, **_kwargs):
        return None

    monkeypatch.setattr(runtime, "_verify_boundary_proof", no_boundary_proof)
    monkeypatch.setattr(runtime, "validate_section_boundary", lambda **_kwargs: ())
    monkeypatch.setattr(runtime, "validate_section_continuity", lambda **_kwargs: ())
    result = await runtime.admit_writer_repair_work_item(
        Session(),
        owner_user_id="owner",
        source=source,
        predecessor_work_item_id=predecessor.id,
        accepted_section=original,
        writer_request=request,
        boundary_result=_boundary_result(previous, original, repaired),
        boundary_work_item_id="boundary-1",
        issue=_issue(),
        previous_section=previous,
        next_section=original,
    )

    assert result == "replacement-row"
    admission = captured[0].replacement
    assert admission.item_key.startswith("write:s2:boundary-repair:")
    assert admission.composition_identity == _stable_hash(
        request.composition_plan.model_dump(mode="json")
    )
    assert admission.input_hash
    assert admission.definition_hash == _stable_hash(runtime.WRITER_REPAIR_DEFINITION)
    assert captured[0].predecessor_work_item_id == predecessor.id


@pytest.mark.asyncio
async def test_admission_rejects_unchanged_or_forged_issue(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    request = _request(source, "s2")
    predecessor = SimpleNamespace(
        id="writer-old",
        item_key="write:s2",
        replaces_work_item_id=None,
        run_id="run-1",
        stage="section_writing",
        status="ready",
        output_json=_result(original).model_dump(mode="json"),
        output_hash=content_hash(_result(original).model_dump(mode="json")),
        composition_identity=_stable_hash(request.composition_plan.model_dump(mode="json")),
    )

    class Session:
        async def scalar(self, _statement):
            return predecessor

    monkeypatch.setattr(runtime, "validate_section_boundary", lambda **_kwargs: ())
    monkeypatch.setattr(runtime, "validate_section_continuity", lambda **_kwargs: ())
    unchanged = _boundary_result(previous, original, original)
    with pytest.raises(runtime.WriterRepairRuntimeError, match="did not change"):
        await runtime.admit_writer_repair_work_item(
            Session(),
            owner_user_id="owner",
            source=source,
            predecessor_work_item_id=predecessor.id,
            accepted_section=original,
            writer_request=request,
            boundary_result=unchanged,
            boundary_work_item_id="boundary-1",
            issue=_issue(),
            previous_section=previous,
            next_section=original,
        )
    forged = _issue().model_copy(update={"required_correction": "forged"})
    with pytest.raises(runtime.WriterRepairRuntimeError, match="exact typed issue"):
        await runtime.admit_writer_repair_work_item(
            Session(),
            owner_user_id="owner",
            source=source,
            predecessor_work_item_id=predecessor.id,
            accepted_section=original,
            writer_request=request,
            boundary_result=_boundary_result(
                previous,
                original,
                _section("s2", 1, "Connect the first idea to the second idea."),
            ),
            boundary_work_item_id="boundary-1",
            issue=forged,
            previous_section=previous,
            next_section=original,
        )


@pytest.mark.asyncio
async def test_admission_requires_durable_boundary_repair_proof() -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    boundary_result = _boundary_result(previous, original, repaired)
    work = boundary_runtime._work_order(
        runtime._identity(source),
        previous,
        original,
        previous_composition_identity="composition-s1",
        next_composition_identity="composition-s2",
    )
    payload = {
        "kind": "shared_lesson_boundary_repair_result",
        "work": work.model_dump(mode="json"),
        "result": boundary_result.model_dump(mode="json"),
    }
    checkpoint = RuntimeCheckpoint(
        compatibility=RuntimeCheckpointCompatibility(
            schema_version=1,
            source_revision=source.revision,
            source_hash=source.content_hash,
            input_hash="input",
            definition_hash="definition",
            composition_identity="identity",
        ),
        payload=payload,
        payload_hash=content_hash(payload),
    )
    row = SimpleNamespace(
        status="failed_recoverable",
        input_hash="input",
        definition_hash="definition",
        composition_identity="identity",
        checkpoint_json=checkpoint.model_dump(mode="json"),
    )

    class Session:
        async def scalar(self, _statement):
            return row

    await runtime._verify_boundary_proof(
        Session(),
        boundary_work_item_id="boundary-1",
        run_id="run-1",
        source=runtime._identity(source),
        boundary_result=boundary_result,
    )
    with pytest.raises(runtime.WriterRepairSourceConflict, match="checkpoint hash"):
        tampered = checkpoint.model_copy(update={"payload_hash": "f" * 64})
        row.checkpoint_json = tampered.model_dump(mode="json")
        await runtime._verify_boundary_proof(
            Session(),
            boundary_work_item_id="boundary-1",
            run_id="run-1",
            source=runtime._identity(source),
            boundary_result=boundary_result,
        )


@pytest.mark.asyncio
async def test_boundary_replacement_uses_current_writer_leaf_and_fresh_identity(
    monkeypatch,
) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    old_work = boundary_runtime._work_order(
        runtime._identity(source),
        previous,
        original,
        previous_composition_identity="composition-s1",
        next_composition_identity="composition-s2",
    )
    result = _boundary_result(previous, original, repaired)
    payload = {
        "kind": "shared_lesson_boundary_repair_result",
        "work": old_work.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    }
    old_item = boundary_runtime._item_request("run-1", old_work, max_attempts=3)
    checkpoint = RuntimeCheckpoint(
        compatibility=RuntimeCheckpointCompatibility(
            schema_version=1,
            source_revision=source.revision,
            source_hash=source.content_hash,
            input_hash=old_item.input_hash,
            definition_hash=old_item.definition_hash,
            composition_identity=old_item.composition_identity,
        ),
        payload=payload,
        payload_hash=content_hash(payload),
    )
    predecessor = SimpleNamespace(
        id="boundary-old",
        run_id="run-1",
        stage="continuity_validation",
        status="failed_recoverable",
        input_hash=old_item.input_hash,
        definition_hash=old_item.definition_hash,
        composition_identity=old_item.composition_identity,
        checkpoint_json=checkpoint.model_dump(mode="json"),
    )

    class Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            return predecessor if self.calls == 1 else None

    async def no_run_check(*_args, **_kwargs):
        return None

    async def no_writer_check(*_args, **_kwargs):
        return None

    captured = []

    async def fake_replace(_session, request):
        captured.append(request)
        return "boundary-successor"

    monkeypatch.setattr(boundary_runtime, "_verify_run_source", no_run_check)
    monkeypatch.setattr(boundary_runtime, "_verify_active_writer_outputs", no_writer_check)
    monkeypatch.setattr(boundary_runtime, "replace_work_item", fake_replace)
    admitted = await boundary_runtime.admit_boundary_replacement_work_item(
        Session(),
        predecessor_work_item_id=predecessor.id,
        owner_user_id="owner",
        source=source,
        previous_section=previous,
        next_section=repaired,
        previous_composition_identity="composition-s1",
        next_composition_identity="composition-s2",
    )
    assert admitted == "boundary-successor"
    replacement = captured[0].replacement
    assert replacement.item_key.startswith("boundary:s1->s2:repair:")
    assert replacement.input_hash != predecessor.input_hash
    assert captured[0].predecessor_work_item_id == predecessor.id


@pytest.mark.asyncio
async def test_boundary_replacement_rejects_second_successor_and_old_checkpoint_kind(
    monkeypatch,
) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    old_work = boundary_runtime._work_order(
        runtime._identity(source),
        previous,
        original,
        previous_composition_identity="composition-s1",
        next_composition_identity="composition-s2",
    )
    result = _boundary_result(previous, original, repaired)
    payload = {
        "kind": "shared_lesson_boundary_repair_result",
        "work": old_work.model_dump(mode="json"),
        "result": result.model_dump(mode="json"),
    }
    old_item = boundary_runtime._item_request("run-1", old_work, max_attempts=3)
    checkpoint = RuntimeCheckpoint(
        compatibility=RuntimeCheckpointCompatibility(
            schema_version=1,
            source_revision=source.revision,
            source_hash=source.content_hash,
            input_hash=old_item.input_hash,
            definition_hash=old_item.definition_hash,
            composition_identity=old_item.composition_identity,
        ),
        payload=payload,
        payload_hash=content_hash(payload),
    )
    predecessor = SimpleNamespace(
        id="boundary-old",
        run_id="run-1",
        stage="continuity_validation",
        status="failed_recoverable",
        input_hash=old_item.input_hash,
        definition_hash=old_item.definition_hash,
        composition_identity=old_item.composition_identity,
        checkpoint_json=checkpoint.model_dump(mode="json"),
    )

    class Session:
        async def scalar(self, _statement):
            return predecessor

    monkeypatch.setattr(boundary_runtime, "_verify_run_source", lambda *_a, **_k: None)
    with pytest.raises(boundary_runtime.BoundarySourceConflict, match="successor"):
        await boundary_runtime.admit_boundary_replacement_work_item(
            Session(),
            predecessor_work_item_id=predecessor.id,
            owner_user_id="owner",
            source=source,
            previous_section=previous,
            next_section=repaired,
            previous_composition_identity="composition-s1",
            next_composition_identity="composition-s2",
        )


def test_repair_result_checkpoint_cannot_be_reused_as_initial_boundary_checkpoint() -> None:
    work = boundary_runtime.BoundaryWorkOrder(
        source_plan_id="plan",
        source_plan_revision=2,
        source_plan_hash="a" * 64,
        previous_section_id="s1",
        previous_section_output_hash="b" * 64,
        previous_composition_identity="c1",
        next_section_id="s2",
        next_section_output_hash="c" * 64,
        next_composition_identity="c2",
    )
    with pytest.raises(boundary_runtime.BoundaryCheckpointError, match="unsupported shape"):
        boundary_runtime._validate_checkpoint_payload(
            {"kind": "shared_lesson_boundary_repair_result", "work": work.model_dump(mode="json")},
            work,
        )


@pytest.mark.asyncio
async def test_writer_repair_rejects_historical_leaf_with_existing_successor() -> None:
    source = _source()
    accepted = _section("s2", 1, "The second idea.")
    request = _request(source, "s2")
    predecessor = SimpleNamespace(
        id="writer-old",
        item_key="write:s2",
        replaces_work_item_id=None,
        stage="section_writing",
        status="ready",
    )
    child = SimpleNamespace(id="writer-child")

    class Session:
        def __init__(self):
            self.calls = 0

        async def scalar(self, _statement):
            self.calls += 1
            return predecessor if self.calls == 1 else child

    with pytest.raises(runtime.WriterRepairSourceConflict, match="already has a successor"):
        await runtime._load_predecessor(
            Session(),
            predecessor_work_item_id=predecessor.id,
            accepted_section=accepted,
            request=request,
        )


@pytest.mark.asyncio
async def test_execution_persists_section_result_and_preserves_sibling(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    request = _request(source, "s2")
    work = runtime.WriterRepairWorkOrder(
        source=runtime._identity(source),
        section_id="s2",
        composition_identity=_stable_hash(request.composition_plan.model_dump(mode="json")),
        prior_writer_work_item_id="writer-old",
        prior_writer_output_hash="old-output-hash",
        boundary_work_item_id="boundary-1",
        accepted_section_output_hash=runtime.accepted_section_output_hash(original),
        issue=_issue(),
        previous_section=previous,
        next_section=original,
        replacement=_result(repaired),
    )
    item = SimpleNamespace(
        id="writer-repair",
        run_id="run-1",
        stage="section_writing",
        input_hash=work.identity_hash,
        definition_hash=_stable_hash(runtime.WRITER_REPAIR_DEFINITION),
        composition_identity=work.composition_identity,
        lease_token=4,
    )

    class Session:
        async def scalars(self, _statement):
            return SimpleNamespace(all=lambda: [item])

    async def fake_claim(*_args, **_kwargs):
        return item

    completed = []

    async def fake_complete(_session, **kwargs):
        completed.append(kwargs)
        return item

    async def fake_checkpoint(*_args, **_kwargs):
        return None

    monkeypatch.setattr(runtime, "claim_work_item", fake_claim)
    monkeypatch.setattr(runtime, "load_compatible_checkpoint", fake_checkpoint)
    monkeypatch.setattr(runtime, "persist_checkpoint", fake_checkpoint)
    monkeypatch.setattr(runtime, "complete_work_item", fake_complete)
    monkeypatch.setattr(
        runtime,
        "_active_boundary_sections",
        lambda *_args, **_kwargs: _active_sections(previous, repaired),
    )
    monkeypatch.setattr(runtime, "validate_section_boundary", lambda **_kwargs: ())
    monkeypatch.setattr(runtime, "validate_section_continuity", lambda **_kwargs: ())
    outcome = await runtime.execute_writer_repair_work_item(
        runtime.WriterRepairWorkItemJob(
            session=Session(),
            work_item_id=item.id,
            worker_id="worker",
            source=source,
            work=work,
            writer_request=request,
        )
    )
    assert outcome.result == work.replacement
    assert completed[0]["output_json"] == work.replacement.model_dump(mode="json")


async def _active_sections(previous: SharedSection, repaired: SharedSection):
    return previous, repaired


@pytest.mark.asyncio
async def test_execution_stale_fence_does_not_publish_repair(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    original = _section("s2", 1, "The second idea.")
    repaired = _section("s2", 1, "Connect the first idea to the second idea.")
    request = _request(source, "s2")
    work = runtime.WriterRepairWorkOrder(
        source=runtime._identity(source),
        section_id="s2",
        composition_identity=_stable_hash(request.composition_plan.model_dump(mode="json")),
        prior_writer_work_item_id="writer-old",
        prior_writer_output_hash="old-output-hash",
        boundary_work_item_id="boundary-1",
        accepted_section_output_hash=runtime.accepted_section_output_hash(original),
        issue=_issue(),
        previous_section=previous,
        next_section=original,
        replacement=_result(repaired),
    )
    item = SimpleNamespace(
        id="writer-repair",
        run_id="run-1",
        stage="section_writing",
        input_hash=work.identity_hash,
        definition_hash=_stable_hash(runtime.WRITER_REPAIR_DEFINITION),
        composition_identity=work.composition_identity,
        lease_token=4,
    )

    async def fake_claim(*_args, **_kwargs):
        return item

    async def fake_checkpoint(*_args, **_kwargs):
        return None

    async def stale_complete(*_args, **_kwargs):
        raise LeaseLostError("stale fence")

    monkeypatch.setattr(runtime, "claim_work_item", fake_claim)
    monkeypatch.setattr(runtime, "load_compatible_checkpoint", fake_checkpoint)
    monkeypatch.setattr(runtime, "persist_checkpoint", fake_checkpoint)
    monkeypatch.setattr(runtime, "complete_work_item", stale_complete)
    monkeypatch.setattr(
        runtime,
        "_active_boundary_sections",
        lambda *_args, **_kwargs: _active_sections(previous, repaired),
    )
    monkeypatch.setattr(runtime, "validate_section_boundary", lambda **_kwargs: ())
    monkeypatch.setattr(runtime, "validate_section_continuity", lambda **_kwargs: ())
    with pytest.raises(LeaseLostError, match="stale fence"):
        await runtime.execute_writer_repair_work_item(
            runtime.WriterRepairWorkItemJob(
                session=object(),
                work_item_id=item.id,
                worker_id="worker",
                source=source,
                work=work,
                writer_request=request,
            )
        )
