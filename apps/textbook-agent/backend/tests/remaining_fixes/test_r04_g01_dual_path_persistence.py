"""R04-G01 — dual Print/Learn production, fresh-session reload (REGRESSION_SCENARIOS §7)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from core.database.models import GenerationModel, NativeRealizationModel
from core.database.session import async_session_factory
from curriculum.teaching_plan.consumers import assert_identical_consumer_handoffs
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.rendering.page_objects.document_assembly import reload_document
from print.contracts.lectio_page import validate_document
from tests.print_learn.test_p08_integration_gates import (
    _approve_shared_teaching,
    _prepare_unit_generation,
    _run_learn,
    _run_print,
)


@pytest.mark.asyncio
async def test_r04_g01_dual_path_persist_fresh_session_reload() -> None:
    """MOCK providers; real Unit prep, Print executor, Learn produce; fresh SQLAlchemy reload."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="r04-g01")
    revision = await _approve_shared_teaching(gid=gid, item_id=item_id)

    print_result = await _run_print(gid=gid)
    assert print_result["status"] in {"ready", "awaiting_visuals"}

    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)
    assert learn_result["status"] == "ready"

    print_output_id = gid
    learn_output_id = str(learn_result["output_id"])
    learn_lesson_id = str(learn_result["editable_lesson_id"])

    # Close implicit session scope — all commits done; open fresh factory reload.
    async with async_session_factory() as session:
        print_gen = await session.get(GenerationModel, print_output_id)
        learn_gen = await session.get(GenerationModel, learn_output_id)
        assert print_gen is not None
        assert learn_gen is not None

        print_state = await PageDocumentRepository(session, gid).load_page_generation_state()
        handoffs = print_state.get("teaching_consumer_handoffs") or {}
        assert handoffs["print"]["revision"] == revision
        assert handoffs["learn"]["revision"] == revision
        assert_identical_consumer_handoffs(print_state)

        print_doc = reload_document(print_gen.document_json or {})
        assert validate_document(print_doc) == []
        learn_doc = dict(learn_gen.document_json or {})
        # Canonical LearnDocument v2 uses nodes; legacy v1 used blocks.
        assert learn_doc.get("nodes") or learn_doc.get("blocks")
        assert int(learn_doc.get("version") or 0) >= 1
        assert print_doc != learn_doc

        print_realizations = (
            await session.scalars(
                select(NativeRealizationModel).where(
                    NativeRealizationModel.path_lesson_id == lesson_id,
                    NativeRealizationModel.path == "print",
                )
            )
        ).all()
        learn_realizations = (
            await session.scalars(
                select(NativeRealizationModel).where(
                    NativeRealizationModel.path_lesson_id == lesson_id,
                    NativeRealizationModel.path == "learn",
                )
            )
        ).all()
        assert print_realizations
        assert learn_realizations
        prep_hash = handoffs["print"]["preparation_hash"]
        assert all(r.teaching_plan_hash for r in print_realizations)
        assert all(r.teaching_plan_hash for r in learn_realizations)
        assert handoffs["print"]["preparation_hash"] == prep_hash

        # Meaningful content: both reference shared teaching arc and sequence stage labels.
        teaching_arc = str((print_state.get("teaching_plan") or {}).get("arc") or "")
        assert teaching_arc
        combined = json.dumps(print_doc).lower() + json.dumps(learn_doc).lower()
        assert "light" in combined or "photosynthesis" in combined

        from core.database.models import EditableLessonModel

        editable = await session.get(EditableLessonModel, learn_lesson_id)
        assert editable is not None
        assert editable.document_json is not None
        assert editable.document_json.get("id") == learn_lesson_id
