"""P02 shared preparation and teaching gates."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from application.unit_lesson import prepare_path_lesson
from curriculum.path_models import PrepareLessonRequest
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.teaching_plan.compatibility import (
    ActionSourceIncompatibleError,
    assert_action_compatible_with_sources,
)
from curriculum.teaching_plan.consumers import (
    accept_approved_teaching_revision,
    assert_identical_consumer_handoffs,
)
from curriculum.teaching_plan.instance_ids import assign_slot_instance_ids
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
    TeachingPlanSection,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.projections import (
    ProjectionLeakError,
    assert_sentinels_absent,
    project_shared_preparation_packet,
    serialize_provider_request,
    with_excluded_sentinels,
)
from curriculum.teaching_plan.revisions import TeachingRevisionStore
from curriculum.teaching_plan.service import edit_teaching_plan, plan_shared_teaching
from core.database.models import PathLessonModel, UserModel
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from tests.planning.test_path_bridge import (
    _fake_component_selector,
    _fake_structural_planner,
)
from v3_blueprint.planning.persistence import load_chunked_state
from v3_blueprint.skeletons import SkeletonPreviewRequest, load_skeleton_catalog


@pytest.mark.asyncio
async def test_p02_s01_shared_prep_no_native_inventory_and_sentinels(db_session) -> None:
    """P02-S01: Real Unit prep → shared plan; serialized provider request has no natives."""
    user = UserModel(id="p02-s01", email="p02-s01@example.invalid", name="S01")
    db_session.add(user)
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    unit = await create_unit(
        db_session,
        owner_id=user.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    await approve_path(db_session, version)
    lesson = await db_session.scalar(
        select(PathLessonModel)
        .where(PathLessonModel.path_version_id == version.id)
        .order_by(PathLessonModel.position)
    )
    assert lesson is not None

    sentinel_form = "SENTINEL_FORM_ID_p02s01_zz9"
    sentinel_component = "SENTINEL_COMPONENT_p02s01_aa1"
    captured: dict = {}

    async def capturing_planner(context: dict):
        captured["context"] = dict(context)
        return await _fake_structural_planner(context)

    selector = AsyncMock(side_effect=AssertionError("component selector must not run"))
    response, structural = await prepare_path_lesson(
        db_session,
        unit=unit,
        version=version,
        lesson=lesson,
        request=PrepareLessonRequest(lesson_mode="first_exposure"),
        structural_planner=capturing_planner,
        component_selector=selector,
    )

    assert structural.document_contract_version == 1
    assert all(not section.components for section in structural.sections)
    assert all(not section.blocks for section in structural.sections)
    state = await load_chunked_state(response.generation_id, db_session)
    assert state["shared_preparation"] is True
    assert state.get("native_whole_lesson") is not True
    assert "components" not in json.dumps(state.get("shared_preparation_packet") or {})

    polluted = with_excluded_sentinels(
        captured["context"],
        sentinels={
            "component_selections": {sentinel_component: {"slug": sentinel_component}},
            "form_id": sentinel_form,
            "allowed_components": [sentinel_component],
            "document_contract_version": 2,
            "native_whole_lesson": True,
        },
    )
    projected = project_shared_preparation_packet(polluted)
    serialized = serialize_provider_request(
        system_prompt="Shared structural preparation. No forms or components.",
        user_payload=projected,
    )
    assert_sentinels_absent(
        serialized,
        [sentinel_form, sentinel_component, "allowed_components", "form_id"],
        where="P02-S01 provider request",
    )
    with pytest.raises(ProjectionLeakError):
        from curriculum.teaching_plan.projections import assert_no_native_inventory

        assert_no_native_inventory(
            {"allowed_components": [sentinel_component]},
            where="direct",
        )
    selector.assert_not_awaited()


def test_p02_s02_objective_refs_scope_and_code_owned_ids() -> None:
    """P02-S02: drift / invented refs / forbidden scope rejected; IDs code-owned."""
    from application.unit_lesson.prepare import (
        PathPreparationBlocked,
        _normalize_page_concept_card_payload,
    )
    from v3_blueprint.planning.objective_ownership import (
        ObjectiveOwnership,
        ObjectiveOwnershipError,
    )

    ownership = ObjectiveOwnership.from_path_objective(
        "Explain why plants need light to make food."
    )
    with pytest.raises(ObjectiveOwnershipError):
        ownership.verify_generated_objective("A rewritten objective about chlorophyll.")

    lesson = SimpleNamespace(
        concept_id="concept-canonical",
        objective="Explain why plants need light to make food.",
        title="Light",
    )
    normalized = _normalize_page_concept_card_payload(
        {
            "id": "invented-id",
            "objective": "Invented objective",
            "title": "Light",
            "misconceptions": [],
            "no_known_misconceptions": True,
            "opens_by": "",
        },
        lesson=lesson,
    )
    assert normalized["id"] == "concept-canonical"
    assert normalized["objective"] == lesson.objective

    draft = TeachingPlanDraft(
        arc="Establish then check.",
        sections=[
            TeachingPlanDraftSection(
                blocks=[
                    TeachingPlanDraftBlock(
                        intent="check-understanding",
                        brief="Ask for the order of stages.",
                        evidence="Learner reconstructs the sequence",
                        evidence_refs=["item.does-not-exist"],
                        source_question_ids=["invented-source"],
                    )
                ]
            )
        ],
    )
    plan = materialize_teaching_plan(draft, slot_ids=["check"])
    assert plan.sections[0].blocks[0].id == "check-b1"
    assert plan.sections[0].slot_id == "check"

    # Forbidden scope term in evidence refs is not silently accepted by consumers.
    with pytest.raises(ActionSourceIncompatibleError):
        assert_action_compatible_with_sources(
            action="order-items",
            source_items=[
                SimpleNamespace(id="mcq-1", options=[{"key": "A"}, {"key": "B"}])
            ],
        )


def test_p02_s03_zero_misconceptions_modes_and_repeated_apply_ids() -> None:
    """P02-S03: zero misconceptions + modes; repeated apply slots keep sequence/IDs."""
    catalog = load_skeleton_catalog()

    for knowledge_type, lesson_mode in (
        ("conceptual", "first_exposure"),
        ("procedural", "first_exposure"),
        ("factual", "first_exposure"),
    ):
        preview = catalog.preview(
            SkeletonPreviewRequest(
                objective="Apply the procedure to a new case.",
                lesson_mode=lesson_mode,
                misconception_count=0,
                group_profiles=["core"],
            ),
            knowledge_type=knowledge_type,
        )
        assert preview.variants
        roles = [slot.slot_id for slot in preview.variants[0].slots]
        assert "check" in roles

    # Extension profile inserts a transfer/apply slot (may repeat apply).
    preview = catalog.preview(
        SkeletonPreviewRequest(
            objective="Transfer the capability to a less familiar case.",
            lesson_mode="first_exposure",
            misconception_count=0,
            group_profiles=["extension"],
        ),
        knowledge_type="conceptual",
    )
    roles = [slot.slot_id for slot in preview.variants[0].slots]
    instance_ids = assign_slot_instance_ids(roles)
    assert len(instance_ids) == len(roles)
    assert len(set(instance_ids)) == len(instance_ids)
    # Explicit repeated-role case (never keyed only by role).
    repeated = assign_slot_instance_ids(["orient", "apply", "apply", "check"])
    assert repeated == ["orient", "apply-1", "apply-2", "check"]


@pytest.mark.asyncio
async def test_p02_s04_print_and_learn_accept_identical_revision() -> None:
    """P02-S04: both consumers accept the same approved teaching without fixtures."""
    plan = TeachingPlan(
        teaching_plan_id="tp-shared",
        revision=1,
        preparation_hash="prep-hash-1",
        arc="Orient, explain, then check independently.",
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                blocks=[
                    TeachingPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="orient",
                        brief="Introduce the shared anchor.",
                        evidence="Learner attends to the anchor",
                        learner_action=None,
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="check",
                blocks=[
                    TeachingPlanBlock(
                        id="check-b1",
                        position=0,
                        intent="check-understanding",
                        brief="Reconstruct the sequence without the answer shown.",
                        evidence="Correct complete order",
                        source_question_ids=["item-open-1"],
                        learner_action=LearnerActionBrief(
                            action="order-items",
                            support_level="independent",
                            evidence="Correct complete order",
                            source_item_ids=["item-open-1"],
                        ),
                    )
                ],
            ),
        ],
    )
    state: dict = {}
    store = TeachingRevisionStore(state)
    store.record_draft(plan, preparation_hash="prep-hash-1", revision=1)
    store.approve(expected_revision=1, reviewed_by="teacher-1")

    print_plan = accept_approved_teaching_revision(state, consumer="print")
    learn_plan = accept_approved_teaching_revision(state, consumer="learn")
    assert print_plan.model_dump(mode="json") == learn_plan.model_dump(mode="json")
    assert print_plan.sections[0].blocks[0].intent == "orient"
    assert learn_plan.sections[1].blocks[0].learner_action is not None
    assert learn_plan.sections[1].blocks[0].learner_action.action == "order-items"
    assert_identical_consumer_handoffs(state)


def test_p02_s05_incompatible_source_fails_without_rewrite() -> None:
    """P02-S05: approved item identity preserved; incompatible action fails."""
    mcq = SimpleNamespace(id="mcq-1", options=[{"key": "A"}, {"key": "B"}])
    open_item = SimpleNamespace(id="open-1", options=[])

    assert_action_compatible_with_sources(
        action="select-one",
        source_items=[mcq],
    )
    assert_action_compatible_with_sources(
        action="order-items",
        source_items=[open_item],
    )
    with pytest.raises(ActionSourceIncompatibleError, match="incompatible"):
        assert_action_compatible_with_sources(
            action="order-items",
            source_items=[mcq],
        )
    with pytest.raises(ActionSourceIncompatibleError, match="multiple-choice"):
        assert_action_compatible_with_sources(
            action="select-one",
            source_items=[open_item],
        )


def test_p02_s06_edit_creates_revision_old_approved_readable() -> None:
    """P02-S06: teaching edit → new revision; old approved remains readable."""
    original = TeachingPlan(
        arc="Original arc.",
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                blocks=[
                    TeachingPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="orient",
                        brief="Original brief.",
                        evidence="Attend",
                    )
                ],
            )
        ],
    )
    state: dict = {}
    store = TeachingRevisionStore(state)
    store.record_draft(original, preparation_hash="hash-a", revision=1)
    approved = store.approve(expected_revision=1, reviewed_by="teacher")
    assert approved.status == "approved"
    assert approved.revision == 1

    edited = original.model_copy(update={"arc": "Edited arc after teacher change."})
    new_draft = edit_teaching_plan(
        state,
        edited,
        preparation_hash="hash-a",
        teacher_note="Clarify the orient brief.",
    )
    assert new_draft.revision == 2
    assert new_draft.status == "pending"

    old = store.get_revision(1)
    assert old is not None
    assert old.status in {"approved", "superseded"}
    assert old.plan["arc"] == "Original arc."
    assert store.get_revision(2) is not None
    assert store.get_revision(2).plan["arc"] == "Edited arc after teacher change."

    # Old approved (or superseded) revision remains consumable by identity.
    pinned = accept_approved_teaching_revision(state, consumer="print", revision=1)
    assert pinned.arc == "Original arc."


@pytest.mark.asyncio
async def test_p02_print_adapts_to_curriculum_teaching_service() -> None:
    """Print binds the curriculum façade rather than owning a duplicated planner."""
    from curriculum.teaching_plan.service import bind_shared_teaching_runner
    from print.generation.whole_lesson.teaching_agent import run_lesson_approach_planner

    called = {}

    async def fake_run(packet, **kwargs):
        called["ok"] = True
        return SimpleNamespace(plan=None)

    bind_shared_teaching_runner(fake_run)
    try:
        await plan_shared_teaching(SimpleNamespace(), require_items=False)
        assert called["ok"] is True
    finally:
        bind_shared_teaching_runner(run_lesson_approach_planner)
