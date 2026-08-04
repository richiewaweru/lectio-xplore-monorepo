from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.auth.middleware import get_current_user
from core.database.models import ConceptCardModel, PackItemModel, UserModel
from core.database.session import async_session_factory
from core.entities.user import User
from generation.v3_studio.router import _ensure_chunked_generation_row
from v3_blueprint.planning.persistence import persist_chunked_state
from v3_execution.executors.item_executor import ItemGenerationResult

TEST_USER = User(
    id="v3-item-review-user",
    email="v3-item-review@example.com",
    name="Item Review",
    picture_url=None,
    has_profile=True,
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)


async def _override_user() -> User:
    return TEST_USER


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_pack() -> tuple[str, str]:
    generation_id = f"item-review-{uuid.uuid4()}"
    card_id = f"biology.photosynthesis.{uuid.uuid4().hex[:8]}"
    async with async_session_factory() as session:
        existing = await session.get(UserModel, TEST_USER.id)
        if existing is None:
            session.add(
                UserModel(
                    id=TEST_USER.id,
                    email=TEST_USER.email,
                    name=TEST_USER.name,
                )
            )
            await session.commit()
    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=TEST_USER.id,
        subject="Biology",
        context="Photosynthesis",
    )
    await persist_chunked_state(
        generation_id,
        {
            "stage": "complete",
            "structural_plan": {
                "lesson_mode": "first_exposure",
                "lesson_intent": {
                    "goal": "Identify photosynthesis inputs.",
                    "structure_rationale": "Move from identification to transfer.",
                },
                "anchor": {
                    "example": "A plant in a sealed chamber",
                    "reuse_scope": "model only",
                },
                "voice": {
                    "register_name": "simple",
                    "tone": "encouraging",
                    "notation": "Use word equations.",
                },
                "prior_knowledge": [],
                "cards": [],
                "sections": [],
                "question_plan": [],
                "answer_key_style": "brief_explanations",
            },
            "context": {
                "signals": {
                    "topic": "Photosynthesis",
                    "subtopic": None,
                    "prior_knowledge": [],
                    "learner_needs": [],
                    "teacher_goal": "Diagnose misconceptions",
                    "inferred_lesson_mode": "first_exposure",
                    "lesson_mode_confidence": "high",
                },
                "form": {
                    "grade_level": "Form 2",
                    "subject": "Biology",
                    "duration_minutes": 45,
                    "resource_type": "lesson",
                    "topic": "Photosynthesis",
                    "subtopics": [],
                    "prior_knowledge": "",
                    "outcome": "Identify photosynthesis inputs.",
                    "struggle": "",
                    "learner_level": "on_grade",
                    "reading_level": "on_grade",
                    "language_support": "none",
                    "prior_knowledge_level": "new_topic",
                    "free_text": "",
                },
                "resource_spec": {"resource_type": "lesson"},
            },
        },
    )
    async with async_session_factory() as session:
        session.add(
            ConceptCardModel(
                id=card_id,
                pack_id=generation_id,
                slug=card_id,
                title="Inputs to photosynthesis",
                objective="Identify the inputs plants use to make glucose.",
                prereqs=[],
                misconceptions=[
                    {"id": "M1", "description": "Plants get food from soil.", "source": "drafted"},
                    {"id": "M2", "description": "Oxygen is an input.", "source": "drafted"},
                ],
            )
        )
        for index in range(1, 6):
            session.add(
                PackItemModel(
                    id=f"{generation_id}:{card_id}.i{index}",
                    pack_id=generation_id,
                    card_id=card_id,
                    stem=f"Question {index}",
                    options=[
                        {
                            "key": "a",
                            "text": "Correct",
                            "correct": True,
                            "diagnoses": None,
                            "teacher_edited": False,
                        },
                        {
                            "key": "b",
                            "text": "Distractor",
                            "correct": False,
                            "diagnoses": "M1" if index < 5 else None,
                            "teacher_edited": False,
                        },
                    ],
                    correct_key="a",
                    diagnoses={"a": None, "b": "M1" if index < 5 else None},
                    stale=False,
                )
            )
        await session.commit()
    return generation_id, card_id


@pytest.fixture(autouse=True)
def _auth_override():
    app.dependency_overrides[get_current_user] = _override_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_pack_items_surfaces_coverage_and_unmapped_options() -> None:
    pack_id, card_id = await _seed_pack()

    async with _client() as client:
        response = await client.get(f"/api/v1/v3/packs/{pack_id}/items")

    assert response.status_code == 200
    review = response.json()[0]
    assert review["card_id"] == card_id
    assert len(review["items"]) == 5
    assert review["coverage"] == {"M1": 4, "M2": 0}
    assert review["missing_misconceptions"] == ["M2"]
    assert review["unmapped_options"] == 1


@pytest.mark.asyncio
async def test_patch_pack_item_marks_teacher_edit_and_validates_diagnosis() -> None:
    pack_id, card_id = await _seed_pack()
    item_id = f"{pack_id}:{card_id}.i1"
    body = {
        "prompt_text": "Teacher revised question",
        "options": [
            {"key": "a", "text": "Correct", "correct": True, "diagnoses": None},
            {"key": "b", "text": "Revised distractor", "correct": False, "diagnoses": "M2"},
        ],
    }

    async with _client() as client:
        response = await client.patch(
            f"/api/v1/v3/packs/{pack_id}/items/{item_id}",
            json=body,
        )

    assert response.status_code == 200
    saved = next(item for item in response.json()["items"] if item["id"] == item_id)
    assert saved["prompt_text"] == "Teacher revised question"
    assert saved["teacher_edited"] is True
    assert saved["options"][1]["diagnoses"] == "M2"


@pytest.mark.asyncio
async def test_regenerate_preserves_teacher_item_and_marks_it_stale() -> None:
    pack_id, card_id = await _seed_pack()
    edited_id = f"{pack_id}:{card_id}.i1"
    async with async_session_factory() as session:
        edited = await session.get(PackItemModel, edited_id)
        assert edited is not None
        edited.stem = "Teacher wording"
        edited.options = [
            {
                "key": "a",
                "text": "Teacher correct",
                "correct": True,
                "diagnoses": None,
                "teacher_edited": True,
            },
            {
                "key": "b",
                "text": "Teacher distractor",
                "correct": False,
                "diagnoses": "M2",
                "teacher_edited": True,
            },
        ]
        await session.commit()

    generated = ItemGenerationResult.model_validate(
        {
            "card_id": card_id,
            "items": [
                {
                    "question_id": f"{card_id}.i{index}",
                    "prompt_text": f"Regenerated {index}",
                    "options": [
                        {"key": "a", "text": "New correct", "correct": True, "diagnoses": None},
                        {"key": "b", "text": "New distractor", "correct": False, "diagnoses": "M1"},
                    ],
                    "expected_answer": "New correct",
                }
                for index in range(1, 6)
            ],
            "coverage": {"M1": 5},
            "unmapped_options": 0,
        }
    )

    with patch(
        "generation.v3_studio.router.execute_items",
        new=AsyncMock(return_value=generated),
    ):
        async with _client() as client:
            response = await client.post(
                f"/api/v1/v3/packs/{pack_id}/cards/{card_id}/items/regenerate"
            )

    assert response.status_code == 200
    review = response.json()
    preserved = next(item for item in review["items"] if item["id"] == edited_id)
    refreshed = next(
        item for item in review["items"] if item["question_id"].endswith(".i2")
    )
    assert preserved["prompt_text"] == "Teacher wording"
    assert preserved["teacher_edited"] is True
    assert preserved["stale"] is True
    assert refreshed["prompt_text"] == "Regenerated 2"
    assert refreshed["stale"] is False

    async with async_session_factory() as session:
        rows = await session.execute(
            select(PackItemModel).where(PackItemModel.pack_id == pack_id)
        )
        assert len(list(rows.scalars())) == 5
