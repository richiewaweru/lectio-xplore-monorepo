from __future__ import annotations

import pytest
from sqlalchemy import func, select, update
from test_shared_composer_admission import _seed_run, _verifier

from curriculum.teaching_plan.models import TeachingPlanSection
from document.shared_lesson.composer import CompositionChoice, validate_and_build_composition
from document.shared_lesson.composer_admission import admit_composer_work_items
from document.shared_lesson.writer_admission import (
    WriterAdmissionError,
    admit_writer_work_items,
)
from infra.database.models import GenerationRunModel, GenerationWorkItemModel
from infra.execution.checkpoints import content_hash
from infra.generation_runtime import WorkItemConflict


async def _seed_ready_composer_run(db_session):
    owner, run_id, source, _sourcebook = await _seed_run(db_session)
    composer_items = await admit_composer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    for admission in composer_items:
        section: TeachingPlanSection = admission.section
        block = section.blocks[0]
        composition = validate_and_build_composition(
            section=section,
            choices=(
                CompositionChoice(
                    teaching_block_id=block.id,
                    kind="paragraph",
                    semantic_role="explanation",
                ),
            ),
            tasks=(),
        )
        item = await db_session.get(GenerationWorkItemModel, admission.work_item_id)
        assert item is not None
        payload = composition.model_dump(mode="json")
        item.status = "ready"
        item.output_json = payload
        item.output_hash = content_hash(payload)
    await db_session.commit()
    return owner, run_id, source


@pytest.mark.asyncio
async def test_admission_derives_requests_on_same_run_and_does_not_create_run(db_session) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    before_runs = await db_session.scalar(
        select(func.count()).select_from(GenerationRunModel).where(GenerationRunModel.id == run_id)
    )

    admitted = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )

    assert tuple(item.section.slot_id for item in admitted) == ("orient", "explain")
    assert all(item.request.sources for item in admitted)
    assert all(
        item.request.composition_plan.section_slot_id == item.section.slot_id for item in admitted
    )
    after_runs = await db_session.scalar(
        select(func.count()).select_from(GenerationRunModel).where(GenerationRunModel.id == run_id)
    )
    assert after_runs == before_runs == 1
    rows = list(
        (
            await db_session.scalars(
                select(GenerationWorkItemModel).where(
                    GenerationWorkItemModel.run_id == run_id,
                    GenerationWorkItemModel.stage == "section_writing",
                )
            )
        ).all()
    )
    assert {row.id for row in rows} == {item.work_item_id for item in admitted}
    assert all(row.status == "queued" for row in rows)


@pytest.mark.asyncio
async def test_admission_is_idempotent_and_changed_writer_identity_conflicts(db_session) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    first = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    second = await admit_writer_work_items(
        db_session,
        run_id=run_id,
        owner_user_id=owner,
        source=source,
        source_verifier=_verifier,
    )
    assert tuple(item.work_item_id for item in second) == tuple(item.work_item_id for item in first)

    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == first[0].work_item_id)
        .values(input_hash="0" * 64)
    )
    await db_session.commit()
    with pytest.raises(WorkItemConflict):
        await admit_writer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=_verifier,
        )


@pytest.mark.asyncio
async def test_admission_rejects_wrong_owner_and_source_verifier(db_session) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)

    with pytest.raises(WriterAdmissionError, match="durable"):
        await admit_writer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id="another-owner",
            source=source,
            source_verifier=_verifier,
        )

    async def wrong_source_verifier(_session, requested):
        return requested.model_copy(update={"source_hash": "f" * 64})

    with pytest.raises(WriterAdmissionError, match="exact admitted identity"):
        await admit_writer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=wrong_source_verifier,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("status", "queued", "not ready"),
        ("input_hash", "0" * 64, "stale input"),
        ("composition_identity", "f" * 64, "invalid composition identity"),
        ("replaces_work_item_id", "missing-predecessor", "durable"),
    ],
)
async def test_admission_rejects_missing_or_stale_composer_state(
    db_session,
    field,
    value,
    message,
) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    composer = await db_session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.item_key == "compose:orient",
        )
    )
    assert composer is not None
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == composer.id)
        .values(**{field: value})
    )
    await db_session.commit()

    with pytest.raises(WriterAdmissionError, match=message):
        await admit_writer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=_verifier,
        )


@pytest.mark.asyncio
async def test_admission_rejects_tampered_composer_output(db_session) -> None:
    owner, run_id, source = await _seed_ready_composer_run(db_session)
    composer = await db_session.scalar(
        select(GenerationWorkItemModel).where(
            GenerationWorkItemModel.run_id == run_id,
            GenerationWorkItemModel.item_key == "compose:orient",
        )
    )
    assert composer is not None
    await db_session.execute(
        update(GenerationWorkItemModel)
        .where(GenerationWorkItemModel.id == composer.id)
        .values(output_json={"forged": True})
    )
    await db_session.commit()

    with pytest.raises(WriterAdmissionError, match="output hash"):
        await admit_writer_work_items(
            db_session,
            run_id=run_id,
            owner_user_id=owner,
            source=source,
            source_verifier=_verifier,
        )
