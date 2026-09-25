from __future__ import annotations

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
from document.shared_lesson.boundary import BoundaryValidationResult
from document.shared_lesson.boundary_runtime import (
    BoundaryCheckpointError,
    BoundarySourceConflict,
    BoundaryWorkOrder,
    _checkpoint_payload,
    _composition_identity_from_request,
    _logical_item_key,
    _validate_checkpoint_payload,
    accepted_section_output_hash,
)
from document.shared_lesson.composer import (
    CompositionChoice,
    validate_and_build_composition,
)
from document.shared_lesson.models import ParagraphDisplay, ParagraphNode, SharedSection
from document.shared_lesson.runtime import TeachingPlanSource, make_section_writer_request


def _section(section_id: str, position: int, text: str) -> SharedSection:
    return SharedSection(
        id=section_id,
        title=f"Section {section_id}",
        position=position,
        nodes=(
            ParagraphNode(
                id=f"{section_id}-node",
                teaching_block_id=f"{section_id}-block",
                display=ParagraphDisplay(text=text),
            ),
        ),
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
        teaching_plan_id="boundary-plan",
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


def _request(source: TeachingPlanSource, slot: str):
    plan = next(section for section in source.plan.sections if section.slot_id == slot)
    composition = validate_and_build_composition(
        section=plan,
        choices=(
            CompositionChoice(
                kind="paragraph",
                teaching_block_id=f"{slot}-block",
                semantic_role="explanation",
            ),
        ),
        tasks=(),
    )
    return make_section_writer_request(section=plan, composition=composition, tasks=())


def test_boundary_work_order_freezes_both_section_hashes_and_compositions() -> None:
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 1, "The second idea.")
    work = BoundaryWorkOrder(
        source_plan_id="plan",
        source_plan_revision=3,
        source_plan_hash="a" * 64,
        previous_section_id=previous.id,
        previous_section_output_hash=accepted_section_output_hash(previous),
        previous_composition_identity="composition-s1",
        next_section_id=following.id,
        next_section_output_hash=accepted_section_output_hash(following),
        next_composition_identity="composition-s2",
    )
    assert work.previous_section_output_hash != work.next_section_output_hash
    assert work.previous_composition_identity == "composition-s1"


def test_checkpoint_rejects_changed_boundary_inputs() -> None:
    work = BoundaryWorkOrder(
        source_plan_id="plan",
        source_plan_revision=3,
        source_plan_hash="a" * 64,
        previous_section_id="s1",
        previous_section_output_hash="b" * 64,
        previous_composition_identity="composition-s1",
        next_section_id="s2",
        next_section_output_hash="c" * 64,
        next_composition_identity="composition-s2",
    )
    payload = _checkpoint_payload(work)
    _validate_checkpoint_payload(payload, work)
    with pytest.raises(BoundaryCheckpointError):
        _validate_checkpoint_payload(
            payload
            | {
                "work": work.model_copy(update={"next_section_output_hash": "d" * 64}).model_dump(
                    mode="json"
                )
            },
            work,
        )


def test_writer_composition_identity_matches_runtime_canonical_hash() -> None:
    source = _source()
    request = _request(source, "s1")
    first = _composition_identity_from_request(request)
    second = _composition_identity_from_request(request.model_copy(deep=True))
    assert first == second
    assert len(first) == 64


@pytest.mark.asyncio
async def test_boundary_source_conflict_does_not_get_reclassified_as_provider_failure() -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 2, "The second idea.")
    from document.shared_lesson.boundary_runtime import _plan_pair

    with pytest.raises(BoundarySourceConflict, match="position"):
        _plan_pair(source, previous, following)


def test_boundary_work_order_is_closed() -> None:
    with pytest.raises(ValueError):
        BoundaryWorkOrder(
            source_plan_id="plan",
            source_plan_revision=3,
            source_plan_hash="a" * 64,
            previous_section_id="s1",
            previous_section_output_hash="b" * 64,
            previous_composition_identity="composition-s1",
            next_section_id="s2",
            next_section_output_hash="c" * 64,
            next_composition_identity="composition-s2",
            unexpected="forbidden",
        )


def test_active_writer_replacement_keeps_the_original_logical_section_key() -> None:
    predecessor = SimpleNamespace(id="writer-old", item_key="write:s1", replaces_work_item_id=None)
    replacement = SimpleNamespace(
        id="writer-new", item_key="write:s1:repair-1", replaces_work_item_id="writer-old"
    )
    assert (
        _logical_item_key(replacement, {predecessor.id: predecessor, replacement.id: replacement})
        == "write:s1"
    )


@pytest.mark.asyncio
async def test_replacement_during_validation_cannot_make_boundary_ready(monkeypatch) -> None:
    source = _source()
    previous = _section("s1", 0, "The first idea.")
    following = _section("s2", 1, "Connect s1 to s2. The second idea.")
    previous_request = _request(source, "s1")
    next_request = _request(source, "s2")
    previous_identity = _composition_identity_from_request(previous_request)
    next_identity = _composition_identity_from_request(next_request)
    work = boundary_runtime._work_order(
        boundary_runtime._identity(source),
        previous,
        following,
        previous_composition_identity=previous_identity,
        next_composition_identity=next_identity,
    )
    admission = boundary_runtime._item_request("run-1", work, max_attempts=3)
    item = SimpleNamespace(
        id="boundary-item",
        run_id="run-1",
        stage=admission.stage,
        input_hash=admission.input_hash,
        definition_hash=admission.definition_hash,
        composition_identity=admission.composition_identity,
        lease_token=1,
    )

    calls = 0

    async def writer_check(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise BoundarySourceConflict("writer replacement won the fence")
        return SimpleNamespace(), SimpleNamespace()

    class Session:
        async def scalar(self, _statement):
            return "run-1"

    async def claim(*_args, **_kwargs):
        return item

    failed = []

    async def fail(*_args, **kwargs):
        failed.append(kwargs["failure"].error_code)

    async def checkpoint(*_args, **_kwargs):
        return None

    async def validate(*_args, **_kwargs):
        return BoundaryValidationResult(
            status="pass",
            previous_section=previous,
            next_section=following,
            semantic_calls=1,
        )

    monkeypatch.setattr(boundary_runtime, "_verify_active_writer_outputs", writer_check)
    monkeypatch.setattr(boundary_runtime, "claim_work_item", claim)
    monkeypatch.setattr(boundary_runtime, "load_compatible_checkpoint", checkpoint)
    monkeypatch.setattr(boundary_runtime, "persist_checkpoint", checkpoint)
    monkeypatch.setattr(boundary_runtime, "validate_and_repair_boundary", validate)
    monkeypatch.setattr(boundary_runtime, "fail_work_item", fail)

    result = await boundary_runtime.execute_boundary_work_item(
        boundary_runtime.BoundaryWorkItemJob(
            session=Session(),
            work_item_id=item.id,
            worker_id="boundary-worker",
            source=source,
            previous_section=previous,
            next_section=following,
            writer_requests={"s1": previous_request, "s2": next_request},
        )
    )

    assert result.error_code == "boundary_source_changed_before_commit"
    assert failed == ["boundary_source_changed_before_commit"]
    assert calls == 2
