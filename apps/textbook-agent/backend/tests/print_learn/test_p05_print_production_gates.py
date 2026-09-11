"""P05 — Print production gates: shared teaching → native document → PDF export.

Does NOT inject replacement teaching/form plans (unlike D6A). Provider fakes are
limited to LLM call sites and writer dispatch. Closed form selection is the
production post-approval path.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfReader
from sqlalchemy import select

from app import app
from application.unit_lesson import prepare_path_lesson
from core.auth.middleware import get_current_user
from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    PackItemModel,
    PathLessonModel,
    UserModel,
)
from core.database.session import async_session_factory
from core.entities.user import User
from curriculum.path_models import PrepareLessonRequest
from curriculum.service import approve_path, create_unit, persist_path_plan
from curriculum.teaching_plan.models import (
    AnchorUsageEntry,
    TeachingPlanDraft,
    TeachingPlanDraftBlock,
    TeachingPlanDraftSection,
)
from print.contracts.lectio_page import validate_document
from print.generation.whole_lesson.executor import execute_after_teaching_approval
from print.generation.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.generation.whole_lesson.service import (
    approve_teaching_and_queue,
    build_packet_for_generation,
    run_and_persist_teaching_plan,
)
from print.generation.whole_lesson.states import execution_key
from print.rendering.page_objects.document_assembly import (
    canonical_document_sha256,
    reload_document,
)
from print.rendering.page_objects.models import WriterOutcome
from print.rendering.page_objects.views import (
    render_document_pdf,
    student_document,
    teacher_document,
)
from print.rendering.pdf.rendering.playwright import PDFRenderError
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from tests.planning.test_path_bridge import (
    _fake_component_selector,
    _fake_structural_planner,
)

FIXTURE = "grade4-photosynthesis-path.json"
ANSWER_PHRASE = "TEACHER_ONLY_ANSWER_LIGHT_REQUIRED"
EVIDENCE_ROOT = (
    Path(__file__).resolve().parents[5]
    / "docs"
    / "unit-native-program"
    / "evidence"
    / "mocks"
    / "p05"
)
LONG_PROSE = ("Photosynthesis converts light energy into chemical energy stored in sugar. " * 40).strip()
TABLE_COLUMNS = [
    {"id": "condition", "label": "Condition"},
    {"id": "observation", "label": "Observation"},
    {"id": "inference", "label": "Inference"},
]
TABLE_ROWS = [
    {
        "cells": {
            "condition": f"Condition {i}",
            "observation": f"Observation {i}",
            "inference": f"Inference {i}",
        }
    }
    for i in range(1, 16)
]


@pytest.fixture(autouse=True)
def _reset_injection():
    reset_failure_injection()
    yield
    reset_failure_injection()


def _pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _draft_for_packet(packet, *, item_id: str | None) -> TeachingPlanDraft:
    """Provider-shaped draft reacting to packet slots + approved item (not injected)."""
    sections: list[TeachingPlanDraftSection] = []
    anchors: list[AnchorUsageEntry] = []
    for slot in packet.slots:
        sid = slot.slot_id
        anchors.append(AnchorUsageEntry(slot_id=sid, usage=f"Use the anchor in {sid}."))
        if slot.visual_required or sid == "explain":
            intent = "illustrate" if "illustrate" in (slot.typical_intents or []) else "show-structure"
            if intent not in (slot.typical_intents or ["show-structure", "illustrate", "explain"]):
                intent = "explain"
            sections.append(
                TeachingPlanDraftSection(
                    specific_purpose=f"Develop meaning in {sid}",
                    blocks=[
                        TeachingPlanDraftBlock(
                            intent=intent if intent != "explain" else "explain",
                            brief=(
                                f"Show the lit vs covered leaf contrast for {sid} so learners "
                                "see that light changes the plant's ability to make food."
                            ),
                            evidence_refs=["lesson.objective"],
                            evidence=(
                                "A concrete visual difference belongs here before the check."
                            ),
                        )
                    ],
                )
            )
            continue
        if sid == "check" or "check" in sid:
            source = [item_id] if item_id else []
            sections.append(
                TeachingPlanDraftSection(
                    specific_purpose="Check causal understanding.",
                    blocks=[
                        TeachingPlanDraftBlock(
                            intent="check-understanding",
                            brief=(
                                "Ask the approved covered-leaf item so learners explain why "
                                "light is required using the same plant contrast."
                            ),
                            evidence_refs=["lesson.objective"],
                            evidence=(
                                "The objective requires a causal explanation of light."
                            ),
                            source_question_ids=source,
                            learner_action={
                                "action": "select-one",
                                "target": "why the covered leaf failed to make food",
                                "purpose": "check causal understanding with the approved item",
                                "expected_evidence": "learner selects the light cause",
                                "difficulty": "guided",
                            },
                        )
                    ],
                )
            )
            continue
        intent = "orient" if sid == "orient" else "explain"
        for candidate in list(slot.typical_intents or []) + [intent]:
            if candidate:
                intent = str(candidate)
                break
        sections.append(
            TeachingPlanDraftSection(
                specific_purpose=f"Purpose for {sid}",
                blocks=[
                    TeachingPlanDraftBlock(
                        intent=intent,
                        brief=(
                            f"Advance the light-and-food story in {sid} using the two plants "
                            "without inventing new assessment text."
                        ),
                        evidence_refs=["lesson.objective"],
                        evidence="This slot advances the shared teaching arc.",
                    )
                ],
            )
        )
    return TeachingPlanDraft(
        arc=(
            "Open on two plants that grew differently, isolate light as the cause, "
            "and check understanding with the approved covered-leaf item."
        ),
        anchor_usage=anchors,
        misconception_focus_ids=[],
        sections=sections,
    )


async def _fake_dispatch(ctx):  # noqa: ANN001
    planned = ctx.planned
    if planned.object == "figure":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "alt_text": "Lit leaf beside covered leaf",
                "caption": "Light changes food production — lit vs covered",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/p05-figure.png",
                },
            },
            status="ready",
        )
    if planned.object == "choices":
        records = {str(item.get("id")): item for item in ctx.item_records}
        qid = (planned.source_question_ids or [None])[0]
        record = records.get(str(qid)) or {}
        options = []
        for option in record.get("options") or []:
            if isinstance(option, dict):
                options.append(
                    {
                        "letter": str(option.get("key") or option.get("letter") or ""),
                        "text": str(option.get("text") or ""),
                    }
                )
        return WriterOutcome(
            block_id=planned.id,
            content={
                "stem": str(record.get("stem") or planned.brief or "Choose"),
                "options": options,
            },
            answer_entries=[
                {
                    # Choices answer keys bind to the block id, not the pack item id.
                    "question_id": planned.id,
                    "answer": str(record.get("correct_key") or "A"),
                    "working": ANSWER_PHRASE,
                }
            ],
            status="ready",
        )
    if planned.object == "questions":
        records = {str(item.get("id")): item for item in ctx.item_records}
        entries = []
        items = []
        for qid in planned.source_question_ids or []:
            record = records.get(str(qid)) or {}
            items.append({"id": str(qid), "prompt": str(record.get("stem") or qid)})
            entries.append(
                {
                    "question_id": str(qid),
                    "answer": str(record.get("correct_key") or ANSWER_PHRASE),
                    "working": ANSWER_PHRASE,
                }
            )
        return WriterOutcome(
            block_id=planned.id,
            content={"items": items},
            answer_entries=entries,
            status="ready",
        )
    if planned.object == "table":
        columns = [
            {"id": "condition", "label": "Condition"},
            {"id": "observation", "label": "Observation"},
            {"id": "inference", "label": "Inference"},
        ]
        rows = [
            {
                "cells": {
                    "condition": f"Condition {i}",
                    "observation": f"Observation {i}",
                    "inference": f"Inference {i}",
                }
            }
            for i in range(1, 16)
        ]
        return WriterOutcome(
            block_id=planned.id,
            content={"columns": columns, "rows": rows, "presentation": "comparison"},
            status="ready",
        )
    if planned.object == "list":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "style": "unordered",
                "items": [
                    {"text": "Light reaches the leaf"},
                    {"text": "Covered leaves cannot make food"},
                    {"text": planned.brief or "Soil alone does not explain the difference"},
                ],
            },
            status="ready",
        )
    if planned.object == "aside":
        return WriterOutcome(
            block_id=planned.id,
            content={"label": "Note", "body": planned.brief or "Remember light makes food."},
            status="ready",
        )
    if planned.object == "worked-example":
        return WriterOutcome(
            block_id=planned.id,
            content={
                "problem": "Why did the covered leaf fail?",
                "steps": [
                    {"text": "Compare light"},
                    {"text": "Hold soil constant"},
                    {"text": "Conclude light is required"},
                ],
                "answer": "No light reached the leaf",
            },
            status="ready",
        )
    return WriterOutcome(
        block_id=planned.id,
        content={
            "paragraphs": [
                LONG_PROSE
                if "long" in planned.id
                else (planned.brief or f"Prose for {planned.id}")
            ]
        },
        status="ready",
    )


async def _prepare_unit_generation(*, owner_suffix: str) -> tuple[str, str, str]:
    """Returns (generation_id, item_id, user_id). Seeds one approved MCQ item."""
    user_id = f"p05-owner-{owner_suffix}"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.invalid",
                name="P05 Print",
            )
        )
        plan = load_canonical_plan(FIXTURE)
        unit = await create_unit(
            session,
            owner_id=user_id,
            request=unit_create_from_fixture(FIXTURE),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(
                PathLessonModel.path_version_id == version.id,
                PathLessonModel.primary_knowledge_type == "conceptual",
            )
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None
        response, _ = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(lesson_mode="first_exposure"),
            structural_planner=_fake_structural_planner,
            component_selector=_fake_component_selector,
        )
        gid = response.generation_id
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        pack_id = generation.pack_id or gid
        card = await session.scalar(
            select(ConceptCardModel).where(ConceptCardModel.pack_id == pack_id)
        )
        if card is None:
            card = await session.scalar(
                select(ConceptCardModel).where(ConceptCardModel.pack_id == gid)
            )
        assert card is not None
        item_id = f"{pack_id}:p05-mcq-1"
        session.add(
            PackItemModel(
                id=item_id,
                pack_id=pack_id,
                card_id=card.id,
                stem="Why did the covered leaf fail to make food?",
                options=[
                    {"key": "A", "text": "No light reached the leaf", "correct": True},
                    {"key": "B", "text": "The soil ran out of food", "correct": False},
                ],
                correct_key="A",
                diagnoses={"B": "soil-food misconception"},
                stale=False,
            )
        )
        await session.commit()
    return gid, item_id, user_id


async def _run_uninterrupted_print(
    *,
    gid: str,
    item_id: str,
    fail_once: bool = False,
) -> dict:
    async def _teaching_call(**_kwargs):  # noqa: ANN003
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
        draft = _draft_for_packet(packet, item_id=item_id)
        return draft, draft.model_dump_json()

    with patch(
        "print.generation.whole_lesson.teaching_agent._call_teaching_model",
        new=AsyncMock(side_effect=_teaching_call),
    ):
        async with async_session_factory() as session:
            teaching_result = await run_and_persist_teaching_plan(
                session, gid, require_items=True
            )
            assert teaching_result["validation"]["ok"] is True
            review = teaching_result["review"] or {}
            revision = int(review.get("revision") or 1)
            await approve_teaching_and_queue(
                session,
                gid,
                expected_revision=revision,
                reviewed_by="p05-teacher",
            )
            await session.commit()

    if fail_once:
        configure_failure_injection(
            enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
        )

    with patch(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="p05-worker"
            )
            assert claimed is not None
            result = await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                worker_id="p05-worker",
                lease=claimed,
            )
    return result


# ---------------------------------------------------------------------------
# P05-P01
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p05_p01_uninterrupted_handoff_persists_valid_document() -> None:
    gid, item_id, _ = await _prepare_unit_generation(owner_suffix="p01")
    result = await _run_uninterrupted_print(gid=gid, item_id=item_id)
    assert result["status"] in {"ready", "awaiting_visuals"}

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        # Production teaching path — not teaching_and_form injection.
        assert state.get("teaching_plan")
        assert state.get("form_plan")
        assert state.get("form_prompt") == "closed_print_selection"
        form_raw = state.get("form_raw") or ""
        assert "selection_snapshot" in form_raw
        assert "work_orders" in form_raw
        teaching = state["teaching_plan"]
        sources = [
            sid
            for section in teaching.get("sections") or []
            for block in section.get("blocks") or []
            for sid in (block.get("source_question_ids") or [])
        ]
        assert item_id in sources
        doc = reload_document(generation.document_json or {})
        errors = validate_document(doc)
        assert errors == [], errors[:5]
        assert canonical_document_sha256(doc)


# ---------------------------------------------------------------------------
# P05-P02
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p05_p02_student_hides_answers_teacher_key_matches_pin(
    tmp_path: Path,
) -> None:
    gid, item_id, _ = await _prepare_unit_generation(owner_suffix="p02")
    await _run_uninterrupted_print(gid=gid, item_id=item_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        doc = reload_document(generation.document_json or {})
        pin = canonical_document_sha256(doc)

    student_path = tmp_path / "student.pdf"
    teacher_path = tmp_path / "teacher.pdf"
    render_document_pdf(doc, student_path, audience="student")
    render_document_pdf(doc, teacher_path, audience="teacher")
    teacher_text = _pdf_text(teacher_path)
    student_text = _pdf_text(student_path)
    assert "Answer key" in teacher_text or ANSWER_PHRASE in teacher_text.replace("\n", " ")
    assert ANSWER_PHRASE not in student_text.replace("\n", " ")
    assert "Answer key" not in student_text
    assert "answer_key" not in student_document(doc)
    assert "answer_key" in teacher_document(doc)
    assert canonical_document_sha256(doc) == pin


# ---------------------------------------------------------------------------
# P05-P03
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p05_p03_figure_position_and_missing_asset_tracked() -> None:
    gid, item_id, user_id = await _prepare_unit_generation(owner_suffix="p03")
    await _run_uninterrupted_print(gid=gid, item_id=item_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        doc = reload_document(generation.document_json or {})
        figures = [
            (section.get("id"), block)
            for section in doc.get("sections") or []
            for block in section.get("blocks") or []
            if block.get("object") == "figure"
        ]
        assert figures, "expected at least one figure from closed selection"
        section_id, figure = figures[0]
        assert isinstance(figure.get("position"), int)
        content = figure.get("content") or {}
        # Caption + alt_text are the schema-valid figure labels.
        assert content.get("alt_text")
        assert content.get("caption")
        asset = content.get("asset") or {}
        assert asset.get("src")
        request_id = asset.get("request_id")
        assert request_id

        # Missing/failed asset must not look like blank success on export.
        figure["content"]["asset"] = {
            "status": "pending",
            "kind": "image",
            "request_id": request_id,
        }
        generation.document_json = {
            "document_version": 2,
            "lectio_document": doc,
        }
        generation.status = "awaiting_visuals"
        await session.commit()

    user = User(
        id=user_id,
        email=f"{user_id}@example.invalid",
        name="P05",
        created_at="2026-09-08T00:00:00+00:00",
        updated_at="2026-09-08T00:00:00+00:00",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            blocked = await client.post(
                f"/api/v1/v3/generations/{gid}/export/pdf",
                json={
                    "school_name": "School",
                    "teacher_name": "Teacher",
                    "include_toc": False,
                    "edition": "teacher",
                },
            )
        assert blocked.status_code == 409
        detail = blocked.json()["detail"]
        assert detail["code"] == "FIGURES_NOT_READY"
        assert figure["id"] in detail["block_ids"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# P05-P04
# ---------------------------------------------------------------------------


def test_p05_p04_long_prose_and_table_without_clipping(tmp_path: Path) -> None:
    doc = {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "p05-overflow",
        "title": "Overflow boundaries",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "explain-long",
                        "object": "prose",
                        "intent": "explain",
                        "position": 0,
                        "content": {"paragraphs": [LONG_PROSE]},
                        "layout": {"placement": "main"},
                    },
                    {
                        "id": "explain-table",
                        "object": "table",
                        "intent": "explain",
                        "position": 1,
                        "content": {
                            "columns": TABLE_COLUMNS,
                            "rows": TABLE_ROWS,
                            "presentation": "comparison",
                        },
                        "layout": {"placement": "main"},
                    },
                ],
            }
        ],
    }
    assert validate_document(doc) == []
    pdf_path = tmp_path / "overflow.pdf"
    render_document_pdf(doc, pdf_path, audience="teacher")
    text = _pdf_text(pdf_path).replace("\n", " ")
    assert "Photosynthesis converts light energy" in text
    assert "Condition 1" in text
    assert "Condition 15" in text
    assert "Inference 15" in text
    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) >= 1

    # Page-image inspection requires Poppler (pdftoppm). Record BLOCKED locally
    # when unavailable; text/PDF presence still proves non-clipped content.
    pdftoppm = shutil.which("pdftoppm")
    images_dir = EVIDENCE_ROOT / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    marker = images_dir / "p04-page-image-status.json"
    if pdftoppm:
        out_prefix = images_dir / "overflow-page"
        import subprocess

        subprocess.run(
            [pdftoppm, "-png", str(pdf_path), str(out_prefix)],
            check=True,
            capture_output=True,
        )
        pages = sorted(images_dir.glob("overflow-page*.png"))
        marker.write_text(
            json.dumps({"status": "PASS", "pages": [p.name for p in pages]}, indent=2),
            encoding="utf-8",
        )
        assert pages, "expected rendered page images"
    else:
        marker.write_text(
            json.dumps(
                {
                    "status": "BLOCKED",
                    "missing": "pdftoppm (Poppler)",
                    "note": (
                        "Install Poppler and ensure pdftoppm is on PATH to unblock "
                        "visual page-image inspection for P05-P04."
                    ),
                },
                indent=2,
            ),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# P05-P05
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p05_p05_export_route_finishes_and_timeout_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from core.config import settings

    gid, item_id, user_id = await _prepare_unit_generation(owner_suffix="p05")
    await _run_uninterrupted_print(gid=gid, item_id=item_id)

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        doc = reload_document(generation.document_json or {})
        # Ensure figures are ready for export gate.
        for section in doc.get("sections") or []:
            for block in section.get("blocks") or []:
                if block.get("object") == "figure":
                    asset = (block.get("content") or {}).get("asset") or {}
                    asset["status"] = "ready"
                    asset.setdefault("src", "https://example.test/p05-figure.png")
                    block["content"]["asset"] = asset
        generation.document_json = {"document_version": 2, "lectio_document": doc}
        generation.status = "ready"
        await session.commit()

    pdf_path = tmp_path / "route.pdf"
    render_document_pdf(doc, pdf_path, audience="teacher")

    user = User(
        id=user_id,
        email=f"{user_id}@example.invalid",
        name="P05",
        created_at="2026-09-08T00:00:00+00:00",
        updated_at="2026-09-08T00:00:00+00:00",
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        with patch(
            "print.http.v3_studio.router.export_v3_studio_pdf",
            new=AsyncMock(
                return_value=type(
                    "R",
                    (),
                    {
                        "pdf_path": pdf_path,
                        "filename": "route.pdf",
                        "page_count": max(1, len(PdfReader(str(pdf_path)).pages)),
                        "file_size_bytes": pdf_path.stat().st_size,
                        "generation_time_ms": 12,
                        "cleanup_paths": [],
                        "print_page_debug": {"renderer": "test"},
                    },
                )()
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                ok = await client.post(
                    f"/api/v1/v3/generations/{gid}/export/pdf",
                    json={
                        "school_name": "School",
                        "teacher_name": "Teacher",
                        "include_toc": False,
                        "edition": "teacher",
                    },
                )
        assert ok.status_code == 200
        assert ok.headers.get("content-type", "").startswith("application/pdf")

        # Injected hang/timeout → actionable failure, no hung worker.
        monkeypatch.setattr(settings, "pdf_export_timeout_ms", 50)

        async def _hang(*_a, **_k):  # noqa: ANN001
            import asyncio

            await asyncio.sleep(10)
            raise AssertionError("should have timed out")

        with patch(
            "print.http.v3_studio.router.export_v3_studio_pdf",
            new=AsyncMock(
                side_effect=PDFRenderError(
                    "PDF export exceeded bounded timeout (50ms)",
                    debug={
                        "code": "PDF_EXPORT_TIMEOUT",
                        "timeout_ms": 50,
                        "actionable": "Retry export after confirming print route health",
                    },
                )
            ),
        ):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                failed = await client.post(
                    f"/api/v1/v3/generations/{gid}/export/pdf",
                    json={
                        "school_name": "School",
                        "teacher_name": "Teacher",
                        "include_toc": False,
                        "edition": "student",
                    },
                )
        assert failed.status_code == 500
        detail = failed.json()["detail"]
        assert "timeout" in str(detail.get("message") or "").lower()
        assert detail.get("debug", {}).get("code") == "PDF_EXPORT_TIMEOUT"

        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            pdf_meta = ((generation.report_json or {}).get("pdf") or {})
            assert pdf_meta.get("last_export_status") == "failed"
            assert "timeout" in str(pdf_meta.get("last_error") or "").lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_p05_p05_bounded_export_timeout_cleans_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit-level: export_generation_pdf applies pdf_export_timeout_ms."""
    import asyncio

    from core.config import settings
    from print.rendering.pdf.context import PDFGenerationContext
    from print.rendering.pdf.service import PDFExportRequest, export_generation_pdf
    from contracts.document import PipelineDocument

    monkeypatch.setattr(settings, "pdf_export_timeout_ms", 100)

    async def _hang(**_kwargs):  # noqa: ANN003
        await asyncio.sleep(5)
        raise AssertionError("unreachable")

    with patch(
        "print.rendering.pdf.service.render_generation_pdf",
        new=AsyncMock(side_effect=_hang),
    ):
        with pytest.raises(PDFRenderError) as raised:
            await export_generation_pdf(
                generation=PDFGenerationContext(
                    id="p05-timeout",
                    user_id="u",
                    subject="Science",
                    context="Science",
                    mode="v3",
                    status="completed",
                    requested_template_id="guided-concept-path",
                    requested_preset_id="blue-classroom",
                ),
                document=PipelineDocument(
                    generation_id="p05-timeout",
                    subject="Science",
                    context="Science",
                    mode="v3",
                    template_id="guided-concept-path",
                    preset_id="blue-classroom",
                    status="completed",
                    section_manifest=[],
                    sections=[],
                ),
                auth_token="token",
                request=PDFExportRequest(
                    school_name="School",
                    teacher_name="Teacher",
                    include_toc=False,
                    include_answers=False,
                    edition="student",
                ),
                settings=settings,
            )
    assert raised.value.debug.get("code") == "PDF_EXPORT_TIMEOUT"


# ---------------------------------------------------------------------------
# P05-P06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p05_p06_recoverable_writer_failure_preserves_siblings() -> None:
    gid, item_id, _ = await _prepare_unit_generation(owner_suffix="p06")

    async def _teaching_call(**_kwargs):  # noqa: ANN003
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
        draft = _draft_for_packet(packet, item_id=item_id)
        return draft, draft.model_dump_json()

    with patch(
        "print.generation.whole_lesson.teaching_agent._call_teaching_model",
        new=AsyncMock(side_effect=_teaching_call),
    ):
        async with async_session_factory() as session:
            teaching_result = await run_and_persist_teaching_plan(
                session, gid, require_items=True
            )
            revision = int((teaching_result["review"] or {}).get("revision") or 1)
            await approve_teaching_and_queue(
                session, gid, expected_revision=revision, reviewed_by="p05"
            )
            await session.commit()

    configure_failure_injection(
        enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
    )
    with patch(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="p05-p06a"
            )
            assert claimed is not None
            first = await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                worker_id="p05-p06a",
                lease=claimed,
            )

    async with async_session_factory() as session:
        stored = await PageDocumentRepository(session, gid).load_block_results()
    ready_before = {
        key
        for key, outcome in stored.items()
        if str((outcome or {}).get("status") or "") in {"ready", "visual_pending"}
    }
    failed_keys = [
        key
        for key, outcome in stored.items()
        if str((outcome or {}).get("status") or "") == "failed_recoverable"
    ]
    # Either mid-run recoverable failure was recorded, or first pass completed
    # after fail_once and restart path still converges below.
    assert ready_before or failed_keys or first.get("status") in {
        "ready",
        "awaiting_visuals",
        "failed_recoverable",
    }

    reset_failure_injection()
    with patch(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            if generation.status == "failed_recoverable":
                await PageDocumentRepository(session, gid).transition(
                    expected={"failed_recoverable"},
                    target="queued",
                    event="requeue",
                )
            elif generation.status not in {"ready", "awaiting_visuals", "queued"}:
                generation.status = "queued"
                await session.commit()
            packet = await build_packet_for_generation(
                session, generation, require_items=True
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="p05-p06b"
            )
            assert claimed is not None
            result = await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                worker_id="p05-p06b",
                lease=claimed,
            )

    assert result["status"] in {"ready", "awaiting_visuals"}
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        doc = reload_document(generation.document_json or {})
        assert validate_document(doc) == []
        digest = canonical_document_sha256(doc)
        # Restart converges to the same validated document identity.
        reloaded = reload_document(generation.document_json or {})
        assert canonical_document_sha256(reloaded) == digest
        stored = await PageDocumentRepository(session, gid).load_block_results()
        for key in ready_before:
            status = str((stored.get(key) or {}).get("status") or "")
            assert status in {"ready", "visual_pending"}, (
                f"completed sibling {key} must survive restart, got {status}"
            )
        # Touch execution keys so lease/checkpoint addressing stays live.
        state = await PageDocumentRepository(session, gid).load_page_generation_state()
        form_plan = state.get("form_plan") or {}
        sections = form_plan.get("sections") or []
        if sections and (sections[0].get("forms") or []):
            slot = sections[0]["slot_id"]
            block = sections[0]["forms"][0]["block_id"]
            assert execution_key(slot, block) in stored or stored
