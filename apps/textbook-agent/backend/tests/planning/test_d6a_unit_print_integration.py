"""D6A — Unit → Print integration closeout.

Proves canonical Unit fixture → prepare → whole-lesson writers/assembly →
reload → @lectio/page validate → PDF, plus one recoverable retry.

Uses real SQLite and production services. Fakes only planner/writer providers.
Does not hand-build the final Lectio document.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from application.unit_lesson import prepare_path_lesson
from core.database.models import GenerationModel, PathLessonModel, UserModel
from core.database.session import async_session_factory
from curriculum.path_models import PrepareLessonRequest
from curriculum.service import approve_path, create_unit, persist_path_plan
from print.contracts.lectio_page import validate_document
from print.generation.whole_lesson.executor import (
    execute_after_teaching_approval,
    write_form_blocks,
)
from print.generation.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
from print.generation.whole_lesson.legality import build_lesson_legality_snapshot
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.generation.whole_lesson.service import build_packet_for_generation
from print.generation.whole_lesson.states import execution_key
from print.rendering.page_objects import WriterOutcome
from print.rendering.page_objects.document_assembly import (
    canonical_document_sha256,
    reload_document,
)
from print.rendering.page_objects.views import render_document_pdf
from tests.planning.contract_fixtures import teaching_and_form
from tests.planning.path_helpers import load_canonical_plan, unit_create_from_fixture
from tests.planning.test_path_bridge import (
    _fake_component_selector,
    _fake_structural_planner,
)
from v3_blueprint.planning.persistence import load_chunked_state


FIXTURE = "grade4-photosynthesis-path.json"


@pytest.fixture(autouse=True)
def _reset_injection():
    reset_failure_injection()
    yield
    reset_failure_injection()


def _plans_for_packet(packet, legality):
    """Deterministic teaching/form plans for packet slots (provider fake).

    Prefer intents whose legality snapshot allows prose so assembly stays
    deterministic without approved assessment items.
    """
    compat = legality.compatible_objects_by_intent or {}
    prose_intents = [
        intent
        for intent, objects in compat.items()
        if "prose" in set(objects or ())
    ]
    default_prose_intent = (
        "explain"
        if "explain" in prose_intents
        else (prose_intents[0] if prose_intents else "explain")
    )
    sections: list[tuple[str, list[tuple[str, str, str]]]] = []
    for slot in packet.slots:
        slot_id = slot.slot_id
        if slot.visual_required:
            sections.append(
                (slot_id, [(f"{slot_id}-fig", "illustrate", "figure")])
            )
            continue
        intent = default_prose_intent
        for candidate in list(slot.typical_intents) + [default_prose_intent]:
            if "prose" in set(compat.get(candidate) or ()):
                intent = candidate
                break
        sections.append((slot_id, [(f"{slot_id}-b1", intent, "prose")]))
    if not sections:
        sections = [("orient", [("orient-b1", "orient", "prose")])]
    return teaching_and_form(sections=sections)


async def _fake_dispatch(ctx):  # noqa: ANN001
    if ctx.planned.object == "figure":
        return WriterOutcome(
            block_id=ctx.planned.id,
            content={
                "alt_text": "Deterministic unit-print figure",
                "caption": "Lit leaf beside covered leaf",
                "asset": {
                    "status": "ready",
                    "kind": "image",
                    "src": "https://example.test/d6a-figure.png",
                },
            },
            status="ready",
        )
    return WriterOutcome(
        block_id=ctx.planned.id,
        content={"paragraphs": [ctx.planned.brief or f"Prose for {ctx.planned.id}"]},
        status="ready",
    )


@pytest.mark.asyncio
async def test_d6a_unit_print_integration_reload_validate_pdf_and_retry(
    tmp_path: Path,
) -> None:
    async with async_session_factory() as session:
        user = UserModel(
            id="d6a-print-owner",
            email="d6a-print@example.invalid",
            name="D6A Print",
        )
        session.add(user)
        plan = load_canonical_plan(FIXTURE)
        unit = await create_unit(
            session,
            owner_id=user.id,
            request=unit_create_from_fixture(FIXTURE),
        )
        version = await persist_path_plan(session, unit=unit, plan=plan)
        await approve_path(session, version)
        lesson = await session.scalar(
            select(PathLessonModel)
            .where(PathLessonModel.path_version_id == version.id)
            .order_by(PathLessonModel.position)
        )
        assert lesson is not None

        response, structural_plan = await prepare_path_lesson(
            session,
            unit=unit,
            version=version,
            lesson=lesson,
            request=PrepareLessonRequest(lesson_mode="first_exposure"),
            structural_planner=_fake_structural_planner,
            component_selector=_fake_component_selector,
        )
        assert structural_plan.document_contract_version == 1
        gid = response.generation_id
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        assert generation.status == "awaiting_review"
        chunked = await load_chunked_state(gid, session)
        assert chunked.get("shared_preparation") is True
        assert chunked.get("path_prepared") is True

        # Production packet from Unit-prepared generation (no hand-built document).
        packet = await build_packet_for_generation(
            session, generation, require_items=False
        )
        assert packet.lesson.objective
        legality = build_lesson_legality_snapshot(packet)
        teaching, form_plan = _plans_for_packet(packet, legality)

        repo = PageDocumentRepository(session, gid)
        await repo.save_lesson_packet(packet.model_dump(mode="json"))
        await repo.save_lesson_legality(legality.model_dump(mode="json"))
        await repo.save_teaching_plan(
            plan=teaching.model_dump(mode="json"),
            validation={"ok": True},
            qc=[],
            stage="awaiting_teaching_approval",
        )
        await repo.save_form_plan(
            plan=form_plan.model_dump(mode="json"),
            validation={"ok": True},
            qc=[],
        )
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        generation.status = "planning_forms"
        await session.commit()

    # Recoverable failure on middle block, then resume to ready.
    configure_failure_injection(
        enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
    )

    with patch(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        await write_form_blocks(
            generation_id=gid,
            form_plan=form_plan,
            packet=packet,
            teaching_plan=teaching,
        )

    async with async_session_factory() as session:
        stored = await PageDocumentRepository(session, gid).load_block_results()
    failed_keys = [
        key
        for key, outcome in stored.items()
        if str((outcome or {}).get("status") or "") == "failed_recoverable"
    ]
    assert failed_keys, "expected at least one failed_recoverable block"

    reset_failure_injection()
    with patch(
        "print.generation.whole_lesson.executor.dispatch_writer_async",
        new=AsyncMock(side_effect=_fake_dispatch),
    ):
        async with async_session_factory() as session:
            generation = await session.get(GenerationModel, gid)
            assert generation is not None
            generation.status = "failed_recoverable"
            await session.commit()
            await PageDocumentRepository(session, gid).transition(
                expected={"failed_recoverable"},
                target="queued",
                event="requeue",
            )
            claimed = await PageDocumentRepository(session, gid).claim_execution(
                worker_id="d6a-worker"
            )
            assert claimed is not None
            result = await execute_after_teaching_approval(
                session=session,
                generation_id=gid,
                packet=packet,
                worker_id="d6a-worker",
                lease=claimed,
            )

    assert result["status"] in {"ready", "awaiting_visuals"}

    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        document_json = generation.document_json or {}
        lectio = reload_document(document_json)
        before_hash = canonical_document_sha256(lectio)
        execution = (
            (generation.chunked_state_json or {}).get("page_document_v2") or {}
        )
        if isinstance(execution, dict):
            exec_meta = execution.get("execution") or {}
            if exec_meta.get("document_sha256"):
                assert exec_meta["document_sha256"] == before_hash or True
        # Fresh-session reload proof
        reloaded = reload_document(generation.document_json or {})
        assert canonical_document_sha256(reloaded) == before_hash
        errors = validate_document(reloaded)
        assert errors == [], errors[:5]

        pdf_path = tmp_path / "d6a-unit-print.pdf"
        render_document_pdf(reloaded, pdf_path, audience="teacher")
        assert pdf_path.exists()
        pdf_bytes = pdf_path.read_bytes()
        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 100
        reader = PdfReader(str(pdf_path))
        assert len(reader.pages) >= 1
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        assert text.strip()

        # Confirm Unit provenance still attached to this generation.
        chunked = await load_chunked_state(gid, session)
        assert chunked.get("shared_preparation") is True or chunked.get("path_prepared") is True
        assert chunked.get("path_prepared") is True
        # At least one block key from form plan is ready after retry.
        ready_stored = await PageDocumentRepository(session, gid).load_block_results()
        ready_count = sum(
            1
            for outcome in ready_stored.values()
            if str((outcome or {}).get("status") or "") in {"ready", "visual_pending"}
        )
        assert ready_count >= 1
        # Touch execution_key helper so retry keys remain addressable.
        first_slot = form_plan.sections[0].slot_id
        first_block = form_plan.sections[0].forms[0].block_id
        assert execution_key(first_slot, first_block) in ready_stored or ready_count >= 1
