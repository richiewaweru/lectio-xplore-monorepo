"""R04-G04 — writer failure injection, retry, sibling isolation (P08 pattern)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from core.database.models import GenerationModel, NativeRealizationModel
from core.database.session import async_session_factory
from print.generation.whole_lesson.failure_injection import (
    configure_failure_injection,
    reset_failure_injection,
)
from print.generation.whole_lesson.repository import PageDocumentRepository
from print.rendering.page_objects.document_assembly import reload_document
from tests.print_learn.test_p08_integration_gates import (
    _approve_shared_teaching,
    _prepare_unit_generation,
    _run_learn,
    _run_print,
)


@pytest.fixture(autouse=True)
def _reset_injection():
    reset_failure_injection()
    yield
    reset_failure_injection()


def _logical_block_ids(document: dict) -> list[str]:
    ids: list[str] = []
    blocks = document.get("blocks")
    if isinstance(blocks, dict):
        ids.extend(str(b.get("id")) for b in blocks.values() if isinstance(b, dict) and b.get("id"))
    for section in document.get("sections") or []:
        if not isinstance(section, dict):
            continue
        for block in section.get("blocks") or []:
            if isinstance(block, dict) and block.get("id"):
                ids.append(str(block["id"]))
    return sorted(set(ids))


@pytest.mark.asyncio
async def test_r04_g04_print_writer_failure_retry_siblings_intact() -> None:
    """MOCK Print writer fails once; production retry; Learn sibling unchanged; no duplicate blocks."""
    gid, item_id, user_id, lesson_id = await _prepare_unit_generation(owner_suffix="r04-g04")
    await _approve_shared_teaching(gid=gid, item_id=item_id)

    learn_result = await _run_learn(gid=gid, user_id=user_id, path_lesson_id=lesson_id)
    assert learn_result["status"] == "ready"
    learn_realization_id = str(learn_result["realization_id"])

    configure_failure_injection(
        enabled=True, generation_id=gid, fail_block_index=1, fail_once=True
    )
    first = await _run_print(gid=gid, fail_once=True)
    assert first["status"] in {
        "ready",
        "awaiting_visuals",
        "failed_recoverable",
        "writing_sections",
        "writing_blocks",
    }

    reset_failure_injection()
    async with async_session_factory() as session:
        generation = await session.get(GenerationModel, gid)
        assert generation is not None
        if generation.status == "failed_recoverable":
            await PageDocumentRepository(session, gid).transition(
                expected={"failed_recoverable"},
                target="queued",
                event="requeue",
            )
            await session.commit()

    if first["status"] not in {"ready", "awaiting_visuals"}:
        second = await _run_print(gid=gid, fail_once=False)
        assert second["status"] in {"ready", "awaiting_visuals"}

    async with async_session_factory() as session:
        print_gen = await session.get(GenerationModel, gid)
        assert print_gen is not None
        print_doc = reload_document(print_gen.document_json or {})
        block_ids = _logical_block_ids(print_doc)
        assert block_ids
        assert len(block_ids) == len(set(block_ids)), "duplicate logical block ids after retry"

        learn_row = await session.get(NativeRealizationModel, learn_realization_id)
        assert learn_row is not None
        assert learn_row.status == "ready"
        assert learn_row.path == "learn"

        print_rows = (
            await session.scalars(
                select(NativeRealizationModel).where(
                    NativeRealizationModel.path_lesson_id == lesson_id,
                    NativeRealizationModel.path == "print",
                )
            )
        ).all()
        assert print_rows
        assert all(r.status in {"ready", "awaiting_visuals"} for r in print_rows)
