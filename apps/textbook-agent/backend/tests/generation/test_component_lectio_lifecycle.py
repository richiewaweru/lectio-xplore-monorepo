"""Truthful Component Lectio lifecycle and append-only recovery regressions."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType

import pytest

from core.database.models import GenerationModel
from core.database.session import async_session_factory
from generation.component_lectio.service import (
    FAILED_STEP,
    READY_STEP,
    load_ready_block_ids,
    reconstruct_checkpoint_store,
    run_component_lectio_execution,
)
from tests.generation.test_component_lectio_final_contract import (
    _exec_kwargs,
    _form,
    _seed_generation,
)
from tests.v3_blueprint.planning.test_intent_plan import (
    SUBJECT_FIXTURES,
    _intent_plan_for_subject,
)
from v3_blueprint.planning.models import intent_plan_to_structural_plan
from v3_blueprint.planning.persistence import insert_step, load_steps


async def _make_stale_generation(generation_id: str) -> None:
    await _seed_generation(generation_id)
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        model.status = "failed"
        model.document_json = {"stale": True}
        model.error = "stale error"
        model.error_type = "StaleError"
        model.error_code = "stale_error"
        model.quality_passed = False
        model.completed_at = model.created_at
        await session.commit()


@pytest.mark.asyncio
async def test_execution_start_clears_terminal_state_and_success_is_atomic() -> None:
    generation_id = f"lifecycle-ok-{uuid.uuid4().hex[:8]}"
    await _make_stale_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))
    observed_start: dict[str, object] = {}
    delegates = _exec_kwargs()
    base_executor = delegates["section_executor"]

    async def inspect_start(work_order, emit, **kwargs):
        if not observed_start:
            async with async_session_factory() as session:
                model = await session.get(GenerationModel, generation_id)
                assert model is not None
                observed_start.update(
                    status=model.status,
                    document=model.document_json,
                    error=model.error,
                    error_type=model.error_type,
                    error_code=model.error_code,
                    quality=model.quality_passed,
                    completed_at=model.completed_at,
                    stage=(model.chunked_state_json or {}).get("stage"),
                )
        return await base_executor(work_order, emit, **kwargs)

    delegates["section_executor"] = inspect_start
    document = await run_component_lectio_execution(
        generation_id=generation_id,
        plan=plan,
        form=_form(),
        **delegates,
    )

    assert observed_start == {
        "status": "running",
        "document": None,
        "error": None,
        "error_type": None,
        "error_code": None,
        "quality": None,
        "completed_at": None,
        "stage": "component_lectio_running",
    }
    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        state = model.chunked_state_json or {}
        assert model.status == "completed"
        assert model.document_json == document
        assert model.quality_passed is True
        assert model.error is None
        assert model.error_type is None
        assert model.error_code is None
        assert model.last_heartbeat is not None
        assert model.completed_at is not None
        assert state["stage"] == "complete"
        assert state["lesson_document"] == document
        assert state["selection_trace"]
        assert "selection_trace" not in document


@pytest.mark.asyncio
async def test_execution_failure_persists_matching_terminal_state_without_document() -> None:
    generation_id = f"lifecycle-fail-{uuid.uuid4().hex[:8]}"
    await _make_stale_generation(generation_id)
    plan = intent_plan_to_structural_plan(_intent_plan_for_subject(**SUBJECT_FIXTURES[0]))

    async def fail_content(work_order, emit, **kwargs):
        raise RuntimeError("controlled lifecycle failure")

    with pytest.raises(RuntimeError, match="controlled lifecycle failure"):
        await run_component_lectio_execution(
            generation_id=generation_id,
            plan=plan,
            form=_form(),
            **_exec_kwargs(section_executor=fail_content),
        )

    async with async_session_factory() as session:
        model = await session.get(GenerationModel, generation_id)
        assert model is not None
        state = model.chunked_state_json or {}
        assert model.status == "failed"
        assert model.document_json is None
        assert model.quality_passed is False
        assert model.error
        assert model.error_type == state["error_type"]
        assert model.error_code == state["error_code"]
        assert model.last_heartbeat is not None
        assert model.completed_at is not None
        assert state["stage"] == "assembly_blocked"
        assert "lesson_document" not in state


@pytest.mark.asyncio
async def test_repeated_failures_then_ready_use_newest_append_only_event() -> None:
    generation_id = f"events-{uuid.uuid4().hex[:8]}"
    await _seed_generation(generation_id)
    block_id = "practice:quiz-check"
    for attempt in (1, 2):
        await insert_step(
            generation_id,
            part_id=block_id,
            step=FAILED_STEP,
            payload={"attempt": attempt, "error": {"message": f"failure {attempt}"}},
        )
    await insert_step(
        generation_id,
        part_id=block_id,
        step=READY_STEP,
        payload={
            "attempt": 3,
            "recovery": "resume_after_failure",
            "plan_revision": 1,
            "plan_hash": "hash",
            "payload": {"component_id": "quiz-check", "content": {"ok": True}},
        },
    )

    rows = [row for row in await load_steps(generation_id) if row.part_id == block_id]
    assert [row.step for row in rows] == [FAILED_STEP, FAILED_STEP, READY_STEP]
    assert await load_ready_block_ids(generation_id) == {block_id}
    store = await reconstruct_checkpoint_store(
        generation_id,
        plan_revision=1,
        plan_hash="hash",
        desired_work=[block_id],
    )
    assert store.blocks[block_id].state == "ready"
    assert store.blocks[block_id].payload["component_id"] == "quiz-check"


def test_generation_step_constraint_migration_is_reversible() -> None:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "src/core/database/migrations/versions"
        / "20260904_0033_remove_generation_step_uniqueness.py"
    )
    spec = importlib.util.spec_from_file_location("generation_step_0033", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert isinstance(migration, ModuleType)
    assert migration.down_revision == "20260806_0032"

    calls: list[tuple[str, tuple, dict]] = []

    class Recorder:
        def drop_constraint(self, *args, **kwargs):
            calls.append(("drop_constraint", args, kwargs))

        def execute(self, *args, **kwargs):
            calls.append(("execute", args, kwargs))

        def create_unique_constraint(self, *args, **kwargs):
            calls.append(("create_unique_constraint", args, kwargs))

    migration.op = Recorder()
    migration.upgrade()
    migration.downgrade()

    assert [call[0] for call in calls] == [
        "drop_constraint",
        "execute",
        "create_unique_constraint",
    ]
    assert calls[0][1] == (
        "uq_generation_steps_part_variant_step",
        "generation_steps",
    )
