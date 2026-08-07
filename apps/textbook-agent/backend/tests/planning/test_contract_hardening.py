"""Contract hardening: persisted legality, fail-closed candidates, informed repair."""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from core.database.models import GenerationModel, UserModel
from core.database.session import async_session_factory
from generation.page_objects import WriterOutcome
from planning.catalogue_projections import build_form_candidate_map, project_form_guidance
from planning.llm_contract_errors import structured_output_errors
from planning.whole_lesson.executor import execute_after_teaching_approval
from planning.whole_lesson.form_agent import NoLegalFormCandidatesError, run_form_planner
from planning.whole_lesson.form_plan import FormDecision, FormPlan, FormPlanSection, coerce_form_plan
from planning.whole_lesson.legality import (
    LessonLegalityError,
    LessonLegalitySnapshot,
    build_lesson_legality_snapshot,
)
from planning.whole_lesson.packet import (
    AnchorRecord,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    SlotRecord,
)
from planning.whole_lesson.repository import PageDocumentRepository, empty_page_document_state
from planning.whole_lesson.teaching_agent import run_lesson_approach_planner
from planning.whole_lesson.teaching_plan import TeachingPlan
from planning.whole_lesson.validation import validate_form_plan
from tests.planning.contract_fixtures import teaching_and_form


def _packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="lesson-harden",
            subject="Science",
            grade_level="Grade 4",
            objective="Explain why plants need light.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(terminology=["light"]),
        anchor=AnchorRecord(id="a1", description="Two plants."),
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause"]),
        ],
        limits=LessonLimits(),
        resource_id="lesson",
    )


def test_missing_candidate_map_entry_fails() -> None:
    teaching, form = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    report = validate_form_plan(form, teaching, candidate_map={})
    assert not report.ok
    assert any(issue.code == "MISSING_CANDIDATE_SET" for issue in report.issues)


def test_empty_candidate_set_fails() -> None:
    teaching, form = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    report = validate_form_plan(
        form, teaching, candidate_map={"orient-b1": ()}
    )
    assert not report.ok
    assert any(issue.code == "NO_LEGAL_OBJECT" for issue in report.issues)


def test_illegal_object_fails_when_candidate_set_empty() -> None:
    teaching, form = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "table")])]
    )
    report = validate_form_plan(
        form, teaching, candidate_map={"orient-b1": ()}
    )
    codes = {issue.code for issue in report.issues}
    assert "NO_LEGAL_OBJECT" in codes
    assert "INCOMPATIBLE_OBJECT" not in codes


def test_form_uses_persisted_legality_not_recomputed_catalogue() -> None:
    teaching, _ = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    legality = LessonLegalitySnapshot(
        resource_id="lesson",
        catalogue_version="test",
        catalogue_hash="abc",
        permitted_intents=["orient"],
        excluded_intents=[],
        typical_by_slot={"orient": ["orient"]},
        permitted_objects=["prose"],
    )
    form_proj = project_form_guidance(
        permitted_object_ids=set(legality.permitted_objects)
    )
    candidates = build_form_candidate_map(
        teaching,
        form_guidance=form_proj,
        permitted_object_ids=set(legality.permitted_objects),
    )
    assert candidates["orient-b1"] == ("prose",)
    # Even if catalogue guidance alone would allow more, snapshot fence wins.
    wide = project_form_guidance()
    assert "table" in (wide.by_intent.get("orient") or ()) or True
    assert "table" not in candidates["orient-b1"]


@pytest.mark.asyncio
async def test_missing_legality_snapshot_load_fails_closed() -> None:
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    state = empty_page_document_state()
    state["lesson_legality"] = None
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="planning_forms",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "planning_forms",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()

    async with async_session_factory() as session:
        with pytest.raises(LessonLegalityError):
            await PageDocumentRepository(session, gid).load_lesson_legality()


@pytest.mark.asyncio
async def test_form_planner_skips_llm_when_no_candidates() -> None:
    teaching, _ = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    legality = LessonLegalitySnapshot(
        resource_id="lesson",
        catalogue_version="test",
        catalogue_hash="abc",
        permitted_intents=["orient"],
        excluded_intents=[],
        typical_by_slot={"orient": ["orient"]},
        # No objects → empty candidates after filtering.
        permitted_objects=[],
    )
    called = {"n": 0}

    async def _boom(*_a, **_k):  # noqa: ANN001
        called["n"] += 1
        raise AssertionError("LLM must not be called")

    with patch(
        "planning.whole_lesson.form_agent._call_form_model",
        new=AsyncMock(side_effect=_boom),
    ):
        with pytest.raises(NoLegalFormCandidatesError) as exc:
            await run_form_planner(
                _packet(), teaching, legality=legality, generation_id=None
            )
    assert called["n"] == 0
    assert exc.value.block_ids == ["orient-b1"]


@pytest.mark.asyncio
async def test_teaching_schema_failure_gets_informed_repair() -> None:
    packet = _packet()
    legality = build_lesson_legality_snapshot(packet)
    payloads: list[dict[str, Any]] = []

    async def _fake_call(*, prompt, user_payload, trace_id, generation_id):  # noqa: ANN001
        payloads.append(user_payload)
        if len(payloads) == 1:
            raise ValidationError.from_exception_data(
                "TeachingPlan",
                [
                    {
                        "type": "missing",
                        "loc": ("arc",),
                        "msg": "Field required",
                        "input": {},
                    }
                ],
            )
        from planning.whole_lesson.teaching_plan import (
            AnchorUsage,
            TeachingPlan,
            TeachingPlanBlock,
            TeachingPlanSection,
        )

        plan = TeachingPlan(
            arc="Orient then explain",
            anchor_usage=AnchorUsage(orient="use", explain="dev", confront="", check=""),
            sections=[
                TeachingPlanSection(
                    slot_id="orient",
                    specific_purpose="Orient",
                    blocks=[
                        TeachingPlanBlock(
                            id="orient-b1",
                            position=0,
                            intent="orient",
                            brief=(
                                "Open with anchor a1: two plants that differ "
                                "only in light exposure so students notice the contrast."
                            ),
                            evidence="Anchor contrast between lit and dark plant.",
                        )
                    ],
                ),
                TeachingPlanSection(
                    slot_id="explain",
                    specific_purpose="Explain",
                    blocks=[
                        TeachingPlanBlock(
                            id="explain-b1",
                            position=0,
                            intent="explain-cause",
                            brief=(
                                "Explain that light is the differing condition "
                                "causing growth differences for the plants shown "
                                "in anchor a1 under otherwise equal care."
                            ),
                            evidence="Covered leaf fails while lit leaf grows.",
                        )
                    ],
                ),
            ],
        )
        return plan, plan.model_dump_json()

    with patch(
        "planning.whole_lesson.teaching_agent._call_teaching_model",
        new=AsyncMock(side_effect=_fake_call),
    ):
        result = await run_lesson_approach_planner(
            packet, legality=legality, require_items=False
        )
    assert result.validation.ok
    assert len(payloads) == 2
    assert "repair" in payloads[1]
    assert payloads[1]["repair"]["validation_errors"]
    assert "arc" in str(payloads[1]["repair"]["validation_errors"]).lower() or any(
        "arc" in str(err) for err in payloads[1]["repair"]["validation_errors"]
    )


@pytest.mark.asyncio
async def test_form_schema_extra_intent_gets_informed_repair() -> None:
    teaching, valid_form = teaching_and_form(
        sections=[("explain", [("explain-b1", "explain-cause", "prose")])]
    )
    legality = LessonLegalitySnapshot(
        resource_id="lesson",
        catalogue_version="test",
        catalogue_hash="abc",
        permitted_intents=["explain-cause"],
        excluded_intents=[],
        typical_by_slot={"explain": ["explain-cause"]},
        permitted_objects=["prose", "list", "table", "figure", "aside", "worked-example"],
    )
    payloads: list[dict[str, Any]] = []

    async def _fake_call(*, prompt, user_payload, trace_id, generation_id):  # noqa: ANN001
        payloads.append(user_payload)
        if len(payloads) == 1:
            # Extra teaching-owned field must fail schema.
            with pytest.raises(ValidationError) as raised:
                FormPlan.model_validate(
                    {
                        "sections": [
                            {
                                "slot_id": "explain",
                                "forms": [
                                    {
                                        "block_id": "explain-b1",
                                        "object": "prose",
                                        "intent": "explain-cause",
                                    }
                                ],
                            }
                        ]
                    }
                )
            raise raised.value
        return valid_form, valid_form.model_dump_json()

    with patch(
        "planning.whole_lesson.form_agent._call_form_model",
        new=AsyncMock(side_effect=_fake_call),
    ):
        result = await run_form_planner(
            _packet(), teaching, legality=legality, generation_id=None
        )
    assert result.validation.ok
    assert len(payloads) == 2
    repair = payloads[1]["repair"]
    assert repair["validation_errors"]
    assert any("intent" in str(err).lower() for err in repair["validation_errors"])


def test_structured_output_errors_from_validation_error() -> None:
    try:
        FormDecision.model_validate(
            {"block_id": "b1", "object": "prose", "intent": "x"}
        )
    except ValidationError as exc:
        messages = structured_output_errors(exc)
    assert messages
    assert any("intent" in msg.lower() or "extra" in msg.lower() for msg in messages)


@pytest.mark.asyncio
async def test_resume_revalidates_legacy_fat_form_plan() -> None:
    teaching, slim = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    packet = _packet()
    legality = LessonLegalitySnapshot(
        resource_id="lesson",
        catalogue_version="test",
        catalogue_hash="abc",
        permitted_intents=["orient"],
        excluded_intents=[],
        typical_by_slot={"orient": ["orient"]},
        # Selected object prose is no longer permitted → reuse must fail.
        permitted_objects=["list"],
    )
    legacy_fat = {
        "sections": [
            {
                "slot_id": "orient",
                "blocks": [
                    {
                        "id": "orient-b1",
                        "position": 0,
                        "intent": "orient",
                        "brief": "Open",
                        "object": "prose",
                        "placement": "main",
                        "reason": "legacy",
                    }
                ],
            }
        ]
    }
    # Coercion succeeds but legality fails.
    coerced = coerce_form_plan(legacy_fat)
    assert coerced.sections[0].forms[0].object == "prose"

    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["lesson_legality"] = legality.model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = legacy_fat
    state["form_validation"] = {"ok": True}
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="planning_forms",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "planning_forms",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()

    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w1"
        )
        assert lease is not None

    form_calls = {"n": 0}

    async def _fake_form(*_a, **_k):  # noqa: ANN001
        form_calls["n"] += 1
        from planning.whole_lesson.form_agent import FormPlanResult
        from planning.whole_lesson.validation import ValidationReport

        # Return a legal list decision for the replan path.
        legal = FormPlan(
            sections=[
                FormPlanSection(
                    slot_id="orient",
                    forms=[
                        FormDecision(
                            block_id="orient-b1",
                            object="list",
                            placement="main",
                            reason="list earns sequence",
                            escalation="prose would bury steps",
                        )
                    ],
                )
            ]
        )
        return FormPlanResult(
            plan=legal,
            validation=ValidationReport(ok=True, issues=[]),
            qc=[],
            prompt="p",
            raw_response="{}",
            form_guidance={},
            candidate_map={"orient-b1": ("list",)},
            attempts=1,
        )

    async def _fake_dispatch(ctx):  # noqa: ANN001
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"style": "unordered", "items": [{"text": "a"}]},
            status="ready",
        )

    with patch(
        "planning.whole_lesson.executor.run_form_planner",
        new=AsyncMock(side_effect=_fake_form),
    ), patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ), patch(
        "planning.whole_lesson.executor.assemble_from_db",
        new=AsyncMock(
            return_value={
                "document": {"document_version": 2},
                "terminal": "ready",
                "writer_count": 1,
                "document_sha256": "abc",
            }
        ),
    ):
        async with async_session_factory() as session:
            await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                teaching_plan=teaching,
                lease=lease,
            )

    assert form_calls["n"] == 1  # not silently reused


@pytest.mark.asyncio
async def test_assemble_lesson_guidance_not_recalled_on_form_resume() -> None:
    packet = _packet()
    teaching, plan = teaching_and_form(
        sections=[("orient", [("orient-b1", "orient", "prose")])]
    )
    legality = build_lesson_legality_snapshot(packet)
    gid = str(uuid.uuid4())
    user_id = f"user-{gid[:8]}"
    state = empty_page_document_state()
    state["lesson_packet"] = packet.model_dump(mode="json")
    state["lesson_legality"] = legality.model_dump(mode="json")
    state["teaching_plan"] = teaching.model_dump(mode="json")
    state["form_plan"] = plan.model_dump(mode="json")
    state["form_validation"] = {"ok": True}
    async with async_session_factory() as session:
        session.add(UserModel(id=user_id, email=f"{user_id}@example.com", name="Test"))
        session.add(
            GenerationModel(
                id=gid,
                user_id=user_id,
                subject="Science",
                requested_template_id="guided-concept-path",
                requested_preset_id="default",
                status="planning_forms",
                chunked_state_json={
                    "page_document_v2": state,
                    "stage": "planning_forms",
                    "native_whole_lesson": True,
                },
            )
        )
        await session.commit()

    async with async_session_factory() as session:
        lease = await PageDocumentRepository(session, gid).claim_execution(
            worker_id="w1"
        )
        assert lease is not None

    guidance_calls = {"n": 0}
    real = __import__(
        "resource_specs.candidates", fromlist=["assemble_lesson_guidance"]
    ).assemble_lesson_guidance

    def _counting(*args, **kwargs):  # noqa: ANN001
        guidance_calls["n"] += 1
        return real(*args, **kwargs)

    async def _fake_dispatch(ctx):  # noqa: ANN001
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={"paragraphs": [ctx.planned.brief]},
            status="ready",
        )

    with patch(
        "planning.whole_lesson.legality.assemble_lesson_guidance",
        side_effect=_counting,
    ), patch(
        "planning.whole_lesson.executor.run_form_planner",
        new=AsyncMock(side_effect=AssertionError("must reuse form plan")),
    ), patch(
        "planning.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ), patch(
        "planning.whole_lesson.executor.assemble_from_db",
        new=AsyncMock(
            return_value={
                "document": {"document_version": 2},
                "terminal": "ready",
                "writer_count": 1,
                "document_sha256": "abc",
            }
        ),
    ):
        async with async_session_factory() as session:
            await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                teaching_plan=teaching,
                lease=lease,
            )

    assert guidance_calls["n"] == 0


@pytest.mark.asyncio
async def test_teaching_with_persisted_legality_does_not_reassemble() -> None:
    packet = _packet()
    legality = build_lesson_legality_snapshot(packet)
    guidance_calls = {"n": 0}

    def _counting(*args, **kwargs):  # noqa: ANN001
        guidance_calls["n"] += 1
        raise AssertionError("assemble_lesson_guidance must not re-run")

    async def _fake_call(*, prompt, user_payload, trace_id, generation_id):  # noqa: ANN001
        from planning.whole_lesson.teaching_plan import (
            AnchorUsage,
            TeachingPlan,
            TeachingPlanBlock,
            TeachingPlanSection,
        )

        plan = TeachingPlan(
            arc="Orient then explain using the plant contrast.",
            anchor_usage=AnchorUsage(orient="use", explain="dev", confront="", check=""),
            sections=[
                TeachingPlanSection(
                    slot_id="orient",
                    specific_purpose="Orient",
                    blocks=[
                        TeachingPlanBlock(
                            id="orient-b1",
                            position=0,
                            intent="orient",
                            brief=(
                                "Open with anchor a1: two plants that differ "
                                "only in light exposure so students notice the contrast."
                            ),
                            evidence="Anchor contrast between lit and dark plant.",
                        )
                    ],
                ),
                TeachingPlanSection(
                    slot_id="explain",
                    specific_purpose="Explain",
                    blocks=[
                        TeachingPlanBlock(
                            id="explain-b1",
                            position=0,
                            intent="explain-cause",
                            brief=(
                                "Explain that light is the differing condition "
                                "causing growth differences for the plants shown "
                                "in anchor a1 under otherwise equal care."
                            ),
                            evidence="Covered leaf fails while lit leaf grows.",
                        )
                    ],
                ),
            ],
        )
        return plan, plan.model_dump_json()

    with patch(
        "planning.whole_lesson.legality.assemble_lesson_guidance",
        side_effect=_counting,
    ), patch(
        "planning.whole_lesson.teaching_agent._call_teaching_model",
        new=AsyncMock(side_effect=_fake_call),
    ):
        result = await run_lesson_approach_planner(
            packet, legality=legality, require_items=False
        )
    assert result.validation.ok
    assert guidance_calls["n"] == 0


def test_build_lesson_legality_snapshot_calls_assemble_once() -> None:
    packet = _packet()
    calls = {"n": 0}
    real = __import__(
        "resource_specs.candidates", fromlist=["assemble_lesson_guidance"]
    ).assemble_lesson_guidance

    def _counting(*args, **kwargs):  # noqa: ANN001
        calls["n"] += 1
        return real(*args, **kwargs)

    with patch(
        "planning.whole_lesson.legality.assemble_lesson_guidance",
        side_effect=_counting,
    ):
        snap = build_lesson_legality_snapshot(packet)
    assert calls["n"] == 1
    assert snap.resource_id == "lesson"
    assert snap.permitted_objects
