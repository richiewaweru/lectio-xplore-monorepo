"""Phase 01: path terminology contracts + legality slot-intent policy projection."""

from __future__ import annotations

import pytest

from core.database.models import UnitScopeContractModel, UserModel
from planning.models import PathPlanDraft, PathScopeDraft
from planning.page_blocks import PageBlockPlanError, validate_intent_departure
from planning.service import canonical_plan_from_version, create_unit, persist_path_plan
from planning.validation import normalize_path_plan_draft
from planning.whole_lesson.legality import (
    LessonLegalitySnapshot,
    legality_hash,
    project_slot_intent_policy,
)
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from tests.planning.path_helpers import four_lesson_draft, sample_canonical_plan, unit_create_from_fixture


@pytest.fixture
async def owner(db_session):
    user = UserModel(id="phase01-owner", email="phase01-owner@example.invalid", name="Phase01 Owner")
    db_session.add(user)
    await db_session.flush()
    return user


def test_c01_path_scope_terminology_schema_accepts_and_preserves() -> None:
    draft = four_lesson_draft()
    plan = normalize_path_plan_draft(draft)
    assert plan.scope.terminology == [
        "heart",
        "artery",
        "vein",
        "capillary",
        "circulation",
    ]
    # Case-insensitive dedupe keeps first spelling.
    dup = four_lesson_draft()
    dup.scope.terminology = ["Heart", "heart", " ARTERY ", "artery"]
    normalized = normalize_path_plan_draft(dup)
    assert normalized.scope.terminology == ["Heart", "ARTERY"]
    # Empty terminology is legal.
    empty = PathPlanDraft(
        scope=PathScopeDraft(
            must_cover=["outcome"],
            do_not_cover=[],
            terminology=[],
        ),
        lessons=draft.lessons,
    )
    assert normalize_path_plan_draft(empty).scope.terminology == []


@pytest.mark.asyncio
async def test_c02_terminology_persistence(db_session, owner) -> None:
    plan = sample_canonical_plan()
    unit = await create_unit(
        db_session,
        owner_id=owner.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    # Override fixture-based unit with circulation plan that has terminology.
    await persist_path_plan(db_session, unit=unit, plan=plan)
    scope = await db_session.get(UnitScopeContractModel, unit.id)
    assert scope is not None
    assert scope.terminology == plan.scope.terminology
    assert scope.terminology != []


@pytest.mark.asyncio
async def test_c03_terminology_round_trip(db_session, owner) -> None:
    plan = sample_canonical_plan()
    unit = await create_unit(
        db_session,
        owner_id=owner.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    version = await persist_path_plan(db_session, unit=unit, plan=plan)
    rebuilt = await canonical_plan_from_version(db_session, version)
    assert rebuilt.scope.terminology == plan.scope.terminology


@pytest.mark.asyncio
async def test_c04_packet_consumes_persisted_terminology(db_session, owner) -> None:
    plan = sample_canonical_plan()
    unit = await create_unit(
        db_session,
        owner_id=owner.id,
        request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
    )
    await persist_path_plan(db_session, unit=unit, plan=plan)
    scope = await db_session.get(UnitScopeContractModel, unit.id)
    assert scope is not None
    packet = ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-1",
            subject="Science",
            grade_level="Grade 4",
            objective="describe circulation",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=list(scope.terminology or [])),
        anchor=AnchorRecord(id="a1", description="A diagram of blood flow."),
        slots=[SlotRecord(slot_id="orient", typical_intents=["orient"])],
        limits=LessonLimits(),
        resource_id="lesson",
    )
    assert packet.scope.terminology == plan.scope.terminology


def _snapshot(**overrides: object) -> LessonLegalitySnapshot:
    data: dict[str, object] = {
        "resource_id": "lesson",
        "catalogue_version": "test",
        "permitted_intents": ["orient", "explain-cause", "emphasise"],
        "excluded_intents": ["investigate"],
        "typical_by_slot": {
            "orient": ["orient"],
            "explain": ["explain-cause"],
        },
        "permitted_objects": ["prose"],
        "compatible_objects_by_intent": {
            "orient": ["prose"],
            "explain-cause": ["prose"],
            "emphasise": ["prose"],
        },
    }
    data.update(overrides)
    data["catalogue_hash"] = legality_hash(data)
    return LessonLegalitySnapshot.model_validate(data)


def test_c05_typical_intent_legal_without_departure() -> None:
    validate_intent_departure(
        intent="orient",
        typical_intents={"orient"},
        permitted_intents={"orient", "emphasise"},
        excluded_intents={"investigate"},
        departure_reason=None,
    )


def test_c06_non_typical_permitted_requires_departure() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="emphasise",
            typical_intents={"orient"},
            permitted_intents={"orient", "emphasise"},
            excluded_intents=set(),
            departure_reason=None,
        )
    validate_intent_departure(
        intent="emphasise",
        typical_intents={"orient"},
        permitted_intents={"orient", "emphasise"},
        excluded_intents=set(),
        departure_reason="Need a short reminder.",
    )


def test_c07_excluded_intent_always_blocked() -> None:
    with pytest.raises(PageBlockPlanError):
        validate_intent_departure(
            intent="investigate",
            typical_intents={"orient"},
            permitted_intents={"orient"},
            excluded_intents={"investigate"},
            departure_reason="even with a reason",
        )


def test_c08_legality_projection_identity() -> None:
    snapshot = _snapshot()
    policy = project_slot_intent_policy(snapshot)
    assert policy["catalogue_hash"] == snapshot.catalogue_hash
    orient = policy["slot_intent_policy"]["orient"]
    assert orient["typical_intents"] == ["orient"]
    assert "emphasise" in orient["permitted_departures"]
    assert "investigate" not in orient["permitted_departures"]
    assert "explain-cause" in orient["permitted_departures"]
    explain = policy["slot_intent_policy"]["explain"]
    assert explain["typical_intents"] == ["explain-cause"]
    assert "orient" in explain["permitted_departures"]
    # Projection is deterministic for the same snapshot.
    assert project_slot_intent_policy(snapshot) == policy
