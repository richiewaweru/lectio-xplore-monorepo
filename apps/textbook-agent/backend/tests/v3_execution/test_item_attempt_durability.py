"""Durable item-attempt journal survives stage failure and success paths."""

from __future__ import annotations

import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from core.database.models import ConceptCardModel, UserModel
from core.database.session import async_session_factory
from generation.v3_studio.dtos import V3InputForm
from generation.v3_studio.router import (
    _ensure_chunked_generation_row,
    _generate_shared_pack_items,
)
from v3_blueprint.planning.models import (
    AnchorSpec,
    ConceptCard,
    ItemOption,
    LessonIntent,
    QuestionBrief,
    StructuralPlan,
)
from v3_blueprint.planning.persistence import load_chunked_state, persist_chunked_state
from v3_execution.executors.item_diagnostics import attempt_record
from v3_execution.executors.item_executor import (
    ITEM_MAX_ATTEMPTS,
    ItemGenerationResult,
    ItemGenerationRun,
)


def _form() -> V3InputForm:
    return V3InputForm(
        grade_level="Grade 4",
        subject="Science",
        duration_minutes=45,
        resource_type="lesson",
        topic="plants and light",
        outcome="Explain why plants need light.",
    )


def _plan() -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="Explain why plants need light.",
            structure_rationale="Concrete-first.",
        ),
        anchor=AnchorSpec(
            example="two plants on a windowsill",
            reuse_scope="throughout",
        ),
        prior_knowledge=[],
        sections=[],
        question_plan=[],
        answer_key_style="brief_explanations",
    )


def _valid_result(card_id: str) -> ItemGenerationResult:
    return ItemGenerationResult(
        card_id=card_id,
        items=[
            QuestionBrief(
                question_id=f"q{i}",
                prompt_text=f"Stem {i}",
                options=[
                    ItemOption(key="A", text="correct", correct=True, diagnoses=None),
                    ItemOption(key="B", text="wrong", correct=False, diagnoses="m1"),
                    ItemOption(key="C", text="other", correct=False, diagnoses=None),
                    ItemOption(key="D", text="other2", correct=False, diagnoses=None),
                ],
                expected_answer="correct",
            )
            for i in range(1, 6)
        ],
    )


async def _seed(generation_id: str, card_id: str) -> None:
    user_id = f"item-dur-{generation_id[:8]}"
    async with async_session_factory() as session:
        if await session.get(UserModel, user_id) is None:
            session.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.com",
                    name="Item Durability",
                )
            )
            await session.commit()
    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=user_id,
        subject="Science",
        context="Plants",
        pack_id=generation_id,
    )
    await persist_chunked_state(generation_id, {"stage": "item_generation"})
    async with async_session_factory() as session:
        session.add(
            ConceptCardModel(
                id=card_id,
                pack_id=generation_id,
                slug="science.plants.light",
                title="Light",
                objective="Explain why plants need light",
                prereqs=[],
                misconceptions=[
                    {"id": "m1", "description": "Plants eat soil", "source": "drafted"},
                    {
                        "id": "m2",
                        "description": "Plants only need water",
                        "source": "drafted",
                    },
                ],
            )
        )
        await session.commit()


@pytest.mark.asyncio
async def test_semantic_fail_then_success_persists_both_attempts() -> None:
    gid = f"item-dur-{uuid.uuid4()}"
    card_id = f"card-{uuid.uuid4().hex[:8]}"
    await _seed(gid, card_id)

    async def _flaky(card: ConceptCard, **_k):
        cid = f"item:{gid}:{card.id}"
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=1,
                    started_at=time.monotonic(),
                    outcome_class="SEMANTIC",
                    error="unknown misconception",
                    retryable=True,
                ),
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=2,
                    started_at=time.monotonic(),
                    outcome_class="OK",
                    retryable=False,
                ),
            ],
            correlation_id=cid,
        )

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_flaky,
        ),
        patch(
            "generation.v3_studio.router._persist_item_results",
            new=AsyncMock(),
        ),
    ):
        summary = await _generate_shared_pack_items(
            generation_id=gid,
            form=_form(),
            plan=_plan(),
        )

    assert summary["generated_card_count"] == 1
    assert len(summary["attempts"]) == 2
    state = await load_chunked_state(gid)
    persisted = (state.get("item_generation") or {}).get("attempts") or []
    assert len(persisted) == 2
    assert persisted[0]["class"] == "SEMANTIC"
    assert persisted[0]["retryable"] is True
    assert persisted[1]["class"] == "OK"
    assert ITEM_MAX_ATTEMPTS == 3


@pytest.mark.asyncio
async def test_all_attempts_fail_persisted_after_stage_failure() -> None:
    gid = f"item-dur-{uuid.uuid4()}"
    card_id = f"card-{uuid.uuid4().hex[:8]}"
    await _seed(gid, card_id)

    async def _always_fail(card: ConceptCard, **_k):
        cid = f"item:{gid}:{card.id}"
        journal = [
            attempt_record(
                correlation_id=cid,
                card_id=card.id,
                attempt=i,
                started_at=time.monotonic(),
                outcome_class="SEMANTIC",
                error=f"fail-{i}",
                retryable=i < ITEM_MAX_ATTEMPTS,
            )
            for i in range(1, ITEM_MAX_ATTEMPTS + 1)
        ]
        exc = ValueError("item generation exhausted")
        setattr(exc, "item_attempts", journal)
        setattr(exc, "item_correlation_id", cid)
        raise exc

    with patch(
        "v3_execution.executors.item_executor.execute_items_with_diagnostics",
        new=_always_fail,
    ):
        with pytest.raises(ValueError, match="exhausted"):
            await _generate_shared_pack_items(
                generation_id=gid,
                form=_form(),
                plan=_plan(),
            )

    state = await load_chunked_state(gid)
    item_gen = state.get("item_generation") or {}
    persisted = item_gen.get("attempts") or []
    assert len(persisted) == ITEM_MAX_ATTEMPTS
    assert [row["attempt"] for row in persisted] == [1, 2, 3]
    assert item_gen.get("failed_cards")
    assert item_gen["failed_cards"][0]["card_id"] == card_id


@pytest.mark.asyncio
async def test_transport_class_survives_persistence() -> None:
    gid = f"item-dur-{uuid.uuid4()}"
    card_id = f"card-{uuid.uuid4().hex[:8]}"
    await _seed(gid, card_id)

    async def _transport_fail(card: ConceptCard, **_k):
        cid = f"item:{gid}:{card.id}"
        journal = [
            attempt_record(
                correlation_id=cid,
                card_id=card.id,
                attempt=1,
                started_at=time.monotonic(),
                outcome_class="TIMEOUT",
                error="provider timed out",
                retryable=True,
            )
        ]
        exc = TimeoutError("provider timed out")
        setattr(exc, "item_attempts", journal)
        setattr(exc, "item_correlation_id", cid)
        raise exc

    with patch(
        "v3_execution.executors.item_executor.execute_items_with_diagnostics",
        new=_transport_fail,
    ):
        with pytest.raises(TimeoutError):
            await _generate_shared_pack_items(
                generation_id=gid,
                form=_form(),
                plan=_plan(),
            )

    state = await load_chunked_state(gid)
    persisted = (state.get("item_generation") or {}).get("attempts") or []
    assert len(persisted) == 1
    assert persisted[0]["class"] == "TIMEOUT"
    assert persisted[0]["retryable"] is True


@pytest.mark.asyncio
async def test_first_attempt_success_one_record() -> None:
    gid = f"item-dur-{uuid.uuid4()}"
    card_id = f"card-{uuid.uuid4().hex[:8]}"
    await _seed(gid, card_id)

    async def _ok(card: ConceptCard, **_k):
        cid = f"item:{gid}:{card.id}"
        return ItemGenerationRun(
            result=_valid_result(card.id),
            attempts=[
                attempt_record(
                    correlation_id=cid,
                    card_id=card.id,
                    attempt=1,
                    started_at=time.monotonic(),
                    outcome_class="OK",
                    retryable=False,
                )
            ],
            correlation_id=cid,
        )

    with (
        patch(
            "v3_execution.executors.item_executor.execute_items_with_diagnostics",
            new=_ok,
        ),
        patch(
            "generation.v3_studio.router._persist_item_results",
            new=AsyncMock(),
        ),
    ):
        summary = await _generate_shared_pack_items(
            generation_id=gid,
            form=_form(),
            plan=_plan(),
        )

    assert len(summary["attempts"]) == 1
    state = await load_chunked_state(gid)
    persisted = (state.get("item_generation") or {}).get("attempts") or []
    assert len(persisted) == 1
    assert persisted[0]["class"] == "OK"
    assert persisted[0]["retryable"] is False
