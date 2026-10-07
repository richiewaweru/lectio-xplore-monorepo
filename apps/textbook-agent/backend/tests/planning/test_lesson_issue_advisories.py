"""Issues tab: document-QA / boundary advisories, teacher copy, and "Mark as fine"."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture

from app import app
from application.unit_lesson import request_outputs
from core.database.models import LessonIssueDismissalModel, PathLessonModel, UserModel
from core.entities.user import User
from curriculum import issue_service
from curriculum.lesson_review import collect_lesson_issues
from curriculum.lesson_review.issue_copy import FLAG_COPY, HIDDEN_SHAPE_CODES
from curriculum.service import approve_path, create_unit, persist_path_plan
from document.shared_lesson.quality_flags import QualityFlag
from infra.auth.middleware import get_current_user
from infra.dependencies import get_async_session

OWNER = User(
    id="issues-owner",
    email="issues-owner@example.invalid",
    name="Issues Owner",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)
OTHER = User(
    id="issues-other",
    email="issues-other@example.invalid",
    name="Issues Other",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)

SECTIONS = [
    {"id": "s-1", "title": "Warm up", "nodes": [{"id": "n-1"}]},
    {"id": "s-2", "title": "Worked example", "nodes": [{"id": "n-2"}, {"id": "fig-1"}]},
    {"id": "s-3", "title": "Practice", "nodes": [{"id": "n-3"}]},
]
BOUNDARY_FLAG = {
    "code": "boundary_transition_warning",
    "severity": "warning",
    "source": "boundary_check",
    "message": "The move from Warm up into Worked example may feel abrupt — the opening may repeat earlier wording.",
    "section_id": "s-2",
    "node_ids": [],
    "required_correction": "Read the opening of Worked example and smooth the transition if needed.",
    "previous_section_id": "s-1",
    "next_section_id": "s-2",
    "previous_section_title": "Warm up",
    "next_section_title": "Worked example",
    "internal_issue_codes": ["boundary_repetition"],
}
QA_FLAG = {
    "code": "answer_leakage",
    "severity": "warning",
    "source": "semantic_qa",
    "message": "Prose before task-3 states the answer 42.",
    "section_id": "s-3",
    "node_ids": ["n-3"],
    "required_correction": "Remove the stated answer.",
}


def _collect(flags, **kwargs):
    return collect_lesson_issues(
        path="learn", quality_flags=flags, shared_sections=SECTIONS, **kwargs
    )


def test_boundary_and_qa_advisories_appear_with_teacher_copy_and_titles() -> None:
    response = _collect([QA_FLAG, BOUNDARY_FLAG])

    assert [(i.code, i.group) for i in response.issues] == [
        ("answer_leakage", "needs_look"),
        ("boundary_transition_warning", "needs_look"),
    ]
    by_code = {issue.code: issue for issue in response.issues}
    leak = by_code["answer_leakage"]
    assert leak.section_id == "s-3"
    assert leak.section_title == "Practice"
    assert leak.message == "A task's answer may be given away in the text around it."
    assert leak.details == "Prose before task-3 states the answer 42."
    assert leak.dismissible and not leak.dismissed
    boundary = by_code["boundary_transition_warning"]
    assert boundary.section_title == "Worked example"
    assert boundary.previous_section_title == "Warm up"
    assert "abrupt" in boundary.message
    assert boundary.path == "learn"
    assert response.counts.needs_look == 2
    assert response.counts.attention == 2
    assert all(issue.id for issue in response.issues)


def test_internal_flag_codes_and_unknown_codes_are_excluded() -> None:
    internal = [
        {**QA_FLAG, "code": "boundary_checkpoint_integrity"},
        {**QA_FLAG, "code": "some_future_internal_code"},
        *({**QA_FLAG, "code": code} for code in sorted(HIDDEN_SHAPE_CODES)),
    ]
    response = _collect(internal)
    assert response.issues == []
    assert response.counts.attention == 0
    assert not HIDDEN_SHAPE_CODES & set(FLAG_COPY)
    assert "boundary_checkpoint_integrity" not in FLAG_COPY


def test_unknown_raw_coherence_codes_are_excluded() -> None:
    response = collect_lesson_issues(
        path="learn",
        states=[
            {
                "coherence_report": {
                    "issues": [
                        {"code": "TASK_PARITY_DRIFT", "message": "x", "severity": "warning"},
                        {"code": "BRAND_NEW_CODE", "message": "y", "severity": "blocking"},
                    ]
                }
            }
        ],
    )
    assert response.issues == []


def test_figure_fallback_flag_is_deduplicated_against_the_plan_figure_warning() -> None:
    from curriculum.teaching_plan.models import TeachingPlanBlock
    from document.shared_lesson.composer import figure_item_for_block

    block = {
        "id": "explain-b1",
        "position": 0,
        "intent": "explain",
        "brief": "Explain the cycle.",
        "evidence": "Source text",
        "visual": {"purpose": "See the cycle.", "must_show": ["evaporation"]},
    }
    node_id = figure_item_for_block("explain", TeachingPlanBlock.model_validate(block)).id
    plan_state = {"teaching_plan": {"sections": [{"slot_id": "explain", "blocks": [block]}]}}
    document = {
        "nodes": [
            {
                "kind": "figure",
                "id": node_id,
                "teaching_block_id": "explain-b1",
                "status": "unavailable",
                "unavailable_reason": "The figure service was unavailable for this figure.",
            }
        ]
    }
    flag = {
        **QA_FLAG,
        "code": "figure_media_unavailable",
        "section_id": "s-2",
        "node_ids": [node_id],
        "message": "Figure could not be produced.",
    }
    sections = [{"id": "s-2", "title": "Worked example", "nodes": [{"id": node_id}]}]

    response = collect_lesson_issues(
        path="learn",
        realization={"realization_id": "r-1", "status": "ready"},
        states=[plan_state],
        documents=[document],
        quality_flags=[flag],
        shared_sections=sections,
    )

    figure_items = [i for i in response.issues if i.category == "figure"]
    assert len(figure_items) == 1
    assert figure_items[0].code == "REQUIRED_FIGURE_MISSING"
    assert figure_items[0].group == "needs_look"
    assert figure_items[0].section_id == "s-2"
    assert figure_items[0].section_title == "Worked example"

    # With no plan warning for it, the flag itself is shown.
    alone = collect_lesson_issues(path="learn", quality_flags=[flag], shared_sections=sections)
    assert [i.code for i in alone.issues] == ["figure_media_unavailable"]


def test_groups_order_blocking_then_needs_look_and_dismissed_leave_the_count() -> None:
    response = collect_lesson_issues(
        path="learn",
        realization={"realization_id": "r-1", "status": "failed_recoverable", "error_summary": "boom"},
        quality_flags=[QA_FLAG, BOUNDARY_FLAG],
        shared_sections=SECTIONS,
    )
    assert [i.group for i in response.issues] == ["blocking", "needs_look", "needs_look"]
    assert response.counts.attention == 3

    leak_id = next(i.id for i in response.issues if i.code == "answer_leakage")
    after = collect_lesson_issues(
        path="learn",
        realization={"realization_id": "r-1", "status": "failed_recoverable", "error_summary": "boom"},
        quality_flags=[QA_FLAG, BOUNDARY_FLAG],
        shared_sections=SECTIONS,
        dismissed_issue_ids={leak_id, response.issues[0].id},
    )
    dismissed = [i for i in after.issues if i.dismissed]
    assert [i.code for i in dismissed] == ["answer_leakage"]  # blocking is never dismissable
    assert after.counts.dismissed == 1
    assert after.counts.attention == 2


def test_issue_ids_are_stable_and_path_specific() -> None:
    learn = _collect([QA_FLAG])
    again = _collect([QA_FLAG])
    printed = collect_lesson_issues(
        path="print", quality_flags=[QA_FLAG], shared_sections=SECTIONS
    )
    assert learn.issues[0].id == again.issues[0].id
    assert learn.issues[0].id != printed.issues[0].id
    assert printed.issues[0].path == "print"


def test_migration_0051_is_chained_after_0050() -> None:
    versions = Path(__file__).resolve().parents[2] / "src/infra/database/migrations/versions"
    migration = (versions / "20261007_0051_lesson_issue_dismissals.py").read_text()
    assert 'revision = "20261007_0051"' in migration
    assert 'down_revision = "20261006_0050"' in migration
    assert "lesson_issue_dismissals" in migration
    assert (versions / "20261006_0050_pack_item_backbone_ref.py").exists()


# --- Route-level: payload, Mark as fine, regeneration reset, ownership ---


@pytest.fixture(autouse=True)
def _clear_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


class _Ctx:
    def __init__(self) -> None:
        self.user = OWNER

    async def override_user(self) -> User:
        return self.user


@pytest.fixture
def ctx() -> _Ctx:
    return _Ctx()


@pytest.fixture
def fake_flags(monkeypatch):
    flags = [
        QualityFlag.model_validate(QA_FLAG),
        QualityFlag.model_validate(BOUNDARY_FLAG),
        QualityFlag.model_validate({**QA_FLAG, "code": "length_over_target", "message": "Advisory shape check"}),
        QualityFlag.model_validate({**QA_FLAG, "code": "boundary_checkpoint_integrity", "message": "internal"}),
    ]

    async def fake_load_flags(session, *, run_id, owner_user_id):
        return tuple(flags)

    async def fake_sections(session, *, run_id, owner_user_id):
        return SECTIONS

    monkeypatch.setattr(issue_service, "load_run_quality_flags", fake_load_flags)
    monkeypatch.setattr(issue_service, "load_run_sections", fake_sections)


async def _seed(db_session_factory):
    plan = load_canonical_plan("grade4-photosynthesis-path.json")
    async with db_session_factory() as session:
        for user in (OWNER, OTHER):
            session.add(UserModel(id=user.id, email=user.email, name=user.name))
        unit = await create_unit(
            session,
            owner_id=OWNER.id,
            request=unit_create_from_fixture("grade4-photosynthesis-path.json"),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        rows = await request_outputs(
            session,
            path_lesson_id=lesson.id,
            paths=["learn"],
            teaching_plan_id="plan-1",
            teaching_plan_revision=1,
            teaching_plan_hash="a" * 64,
        )
        realization = rows[0][0]
        realization.status = "ready"
        realization.output_id = "output-1"
        realization.shared_document_run_id = "run-1"
        ids = (unit.id, lesson.id, realization.id)
        await session.commit()
    return ids


async def _regenerate(db_session_factory, realization_id, *, output_id, run_id):
    from core.database.models import NativeRealizationModel

    async with db_session_factory() as session:
        row = await session.get(NativeRealizationModel, realization_id)
        row.output_id = output_id
        row.shared_document_run_id = run_id
        await session.commit()


async def _client(db_session_factory, ctx):
    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = ctx.override_user
    app.dependency_overrides[get_async_session] = override_session
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_issues_payload_mark_as_fine_restore_and_regeneration_reset(
    db_session_factory, ctx, fake_flags
) -> None:
    unit_id, lesson_id, realization_id = await _seed(db_session_factory)
    base = f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/issues"
    async with await _client(db_session_factory, ctx) as client:
        payload = (await client.get(f"{base}?path=learn")).json()
        codes = sorted(i["code"] for i in payload["issues"])
        # Shape and internal-integrity flags never reach the payload.
        assert codes == ["answer_leakage", "boundary_transition_warning"]
        assert payload["counts"]["attention"] == 2
        leak = next(i for i in payload["issues"] if i["code"] == "answer_leakage")
        assert leak["group"] == "needs_look"
        assert leak["section_id"] == "s-3" and leak["section_title"] == "Practice"
        assert leak["dismissed"] is False

        # Mark as fine: persisted per lesson, leaves the attention count.
        marked = await client.post(
            f"{base}/dismissals", json={"path": "learn", "issue_id": leak["id"]}
        )
        assert marked.status_code == 200
        body = marked.json()
        assert body["counts"]["attention"] == 1 and body["counts"]["dismissed"] == 1
        assert next(i for i in body["issues"] if i["id"] == leak["id"])["dismissed"] is True
        # Idempotent, and still one row.
        again = await client.post(
            f"{base}/dismissals", json={"path": "learn", "issue_id": leak["id"]}
        )
        assert again.status_code == 200
        reloaded = (await client.get(f"{base}?path=learn")).json()
        assert reloaded["counts"]["dismissed"] == 1

        # The same advisory on Print is a separate item.
        printed = (await client.get(f"{base}?path=print")).json()
        assert printed["issues"] == [] or all(not i["dismissed"] for i in printed["issues"])

        # Unknown ids and non-dismissable items are rejected.
        bad = await client.post(
            f"{base}/dismissals", json={"path": "learn", "issue_id": "nope"}
        )
        assert bad.status_code == 422

        # Regeneration (new output / new document run) starts undismissed.
        await _regenerate(db_session_factory, realization_id, output_id="output-2", run_id="run-2")
        fresh = (await client.get(f"{base}?path=learn")).json()
        assert fresh["counts"]["dismissed"] == 0 and fresh["counts"]["attention"] == 2
        await _regenerate(db_session_factory, realization_id, output_id="output-1", run_id="run-1")
        back = (await client.get(f"{base}?path=learn")).json()
        assert back["counts"]["dismissed"] == 1

        # Restore.
        restored = await client.delete(
            f"{base}/dismissals", params={"path": "learn", "issue_id": leak["id"]}
        )
        assert restored.status_code == 200
        assert restored.json()["counts"]["dismissed"] == 0
        assert restored.json()["counts"]["attention"] == 2

    async with db_session_factory() as session:
        rows = (await session.scalars(select(LessonIssueDismissalModel))).all()
        assert rows == []


@pytest.mark.asyncio
async def test_dismissal_scope_key_combines_output_and_run() -> None:
    assert issue_service.dismissal_scope_key("o1", "r1") == "o1|r1"
    assert issue_service.dismissal_scope_key("o2", "r1") != issue_service.dismissal_scope_key("o1", "r1")
    assert issue_service.dismissal_scope_key("o1", "r2") != issue_service.dismissal_scope_key("o1", "r1")
    assert issue_service.dismissal_scope_key(None, None) == "|"


@pytest.mark.asyncio
async def test_issue_dismissal_endpoints_are_owner_scoped(
    db_session_factory, ctx, fake_flags
) -> None:
    unit_id, lesson_id, _realization_id = await _seed(db_session_factory)
    base = f"/api/v1/units/{unit_id}/path/lessons/{lesson_id}/issues"
    async with await _client(db_session_factory, ctx) as client:
        leak = next(
            i for i in (await client.get(f"{base}?path=learn")).json()["issues"]
            if i["code"] == "answer_leakage"
        )
        ctx.user = OTHER
        assert (await client.get(f"{base}?path=learn")).status_code == 404
        assert (
            await client.post(f"{base}/dismissals", json={"path": "learn", "issue_id": leak["id"]})
        ).status_code == 404
        assert (
            await client.delete(f"{base}/dismissals", params={"path": "learn", "issue_id": leak["id"]})
        ).status_code == 404

    async with db_session_factory() as session:
        assert (await session.scalars(select(LessonIssueDismissalModel))).all() == []


@pytest.mark.asyncio
async def test_quality_notes_endpoint_adds_section_titles(db_session_factory, ctx, monkeypatch) -> None:
    from core.database.models import GenerationModel
    from document.shared_lesson import http as shared_http

    async def fake_load_flags(session, *, run_id, owner_user_id):
        return (QualityFlag.model_validate(QA_FLAG), QualityFlag.model_validate(BOUNDARY_FLAG))

    async def fake_sections(session, *, run_id, owner_user_id):
        return SECTIONS

    monkeypatch.setattr(shared_http, "load_run_quality_flags", fake_load_flags)
    monkeypatch.setattr(shared_http, "load_run_sections", fake_sections)
    async with db_session_factory() as session:
        session.add(UserModel(id=OWNER.id, email=OWNER.email, name=OWNER.name))
        session.add(
            GenerationModel(
                id="gen-1",
                user_id=OWNER.id,
                subject="s",
                requested_template_id="t",
                requested_preset_id="p",
                shared_document_run_id="run-1",
            )
        )
        await session.commit()

    from infra.database.session import get_async_session as shared_session_dep

    async def override_session():
        async with db_session_factory() as session:
            yield session

    client_cm = await _client(db_session_factory, ctx)
    app.dependency_overrides[shared_session_dep] = override_session
    async with client_cm as client:
        response = await client.get(
            "/api/v1/shared-documents/quality-flags", params={"generation_id": "gen-1"}
        )
    assert response.status_code == 200
    titles = {f["code"]: f.get("section_title") for f in response.json()["flags"]}
    assert titles == {"answer_leakage": "Practice", "boundary_transition_warning": "Worked example"}
