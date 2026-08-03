from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app import app
from core.auth.middleware import get_current_user
from core.database.models import UserModel
from core.dependencies import get_async_session
from core.entities.user import User
from core.prompts import loader
from planning.agents import run_constructor
from planning.models import ConstructorOutput, UnitCreate
from planning.service import create_unit


CONSTRUCTOR_PROMPT_ID = "constructor"


@pytest.fixture
async def owner(db_session):
    user = UserModel(
        id="constructor-owner", email="constructor-owner@example.invalid", name="Constructor Owner"
    )
    db_session.add(user)
    await db_session.flush()
    return user


def _fake_readback(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Comparing Fractions",
        "topic": "comparing fractions with unlike denominators",
        "destination_objective": (
            "Compare two fractions with unlike denominators and justify which is larger."
        ),
        "starting_knowledge": ["can compare fractions with like denominators"],
        "curriculum_context": None,
        "class_notes": None,
        "clarifying_question": None,
    }
    payload.update(overrides)
    return payload


async def test_run_constructor_returns_at_most_one_clarifying_question(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_structured(
        *, node, caller, output_type, system_prompt, user_payload, trace_id
    ):
        captured["node"] = node
        captured["payload"] = user_payload
        return output_type.model_validate(
            _fake_readback(
                clarifying_question="Do you mean like or unlike denominators?",
            )
        )

    monkeypatch.setattr("planning.agents._run_structured", fake_run_structured)

    result = await run_constructor(
        "Maths", "Grade 5", "teaching comparing fractions", trace_id="test-trace"
    )

    assert isinstance(result, ConstructorOutput)
    assert result.clarifying_question == "Do you mean like or unlike denominators?"
    assert captured["node"] == "v3_constructor"
    assert captured["payload"] == {
        "subject": "Maths",
        "grade_level": "Grade 5",
        "raw_text": "teaching comparing fractions",
    }


async def test_run_constructor_forwards_correction_and_clarifying_answer(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_structured(
        *, node, caller, output_type, system_prompt, user_payload, trace_id
    ):
        captured["payload"] = user_payload
        return output_type.model_validate(_fake_readback(clarifying_question=None))

    monkeypatch.setattr("planning.agents._run_structured", fake_run_structured)

    result = await run_constructor(
        "Maths",
        "Grade 5",
        "teaching comparing fractions",
        correction="Actually it's unlike denominators only.",
        clarifying_answer="Unlike denominators.",
        trace_id="test-trace",
    )

    assert result.clarifying_question is None
    assert captured["payload"]["correction"] == "Actually it's unlike denominators only."
    assert captured["payload"]["clarifying_answer"] == "Unlike denominators."


def test_constructor_output_rejects_multiple_clarifying_questions() -> None:
    with pytest.raises(ValidationError):
        ConstructorOutput.model_validate(
            _fake_readback(clarifying_question=["one question", "two question"])
        )


async def test_constructor_prompt_overlay_and_default_both_load(db_session_factory) -> None:
    async with db_session_factory() as session:
        default_text, default_hash = await loader.resolve_prompt(
            CONSTRUCTOR_PROMPT_ID, "constructor-overlay-user", session
        )
        assert default_text
        assert default_hash == loader.hash_prompt(default_text)
        assert (
            await loader.is_modified(CONSTRUCTOR_PROMPT_ID, "constructor-overlay-user", session)
            is False
        )

        await loader.save_override(
            CONSTRUCTOR_PROMPT_ID,
            "constructor-overlay-user",
            "Custom constructor instructions for this teacher.",
            session,
        )

        overlay_text, overlay_hash = await loader.resolve_prompt(
            CONSTRUCTOR_PROMPT_ID, "constructor-overlay-user", session
        )
        assert overlay_text == "Custom constructor instructions for this teacher."
        assert overlay_hash != default_hash


async def test_create_unit_with_legacy_fields_still_works(db_session, owner) -> None:
    request = UnitCreate(
        title="Cells",
        topic="Cells",
        subject="Science",
        grade_level="Grade 6",
        destination_objective="Explain the role of the cell membrane.",
        starting_knowledge=["cells are the basic unit of life"],
    )

    unit = await create_unit(db_session, owner_id=owner.id, request=request)

    assert unit.title == "Cells"
    assert unit.topic == "Cells"
    assert unit.class_notes is None
    assert unit.curriculum_context is None


async def test_create_unit_from_constructor_filled_fields_works(db_session, owner) -> None:
    readback = ConstructorOutput.model_validate(
        _fake_readback(
            curriculum_context="Key Stage 2 maths curriculum, fractions unit",
            class_notes="Mixed-ability class; some pupils still confuse numerator and denominator.",
        )
    )

    request = UnitCreate(
        title=readback.title,
        topic=readback.topic,
        subject="Maths",
        grade_level="Grade 5",
        destination_objective=readback.destination_objective,
        starting_knowledge=readback.starting_knowledge,
        curriculum_context=readback.curriculum_context,
        class_notes=readback.class_notes,
    )

    unit = await create_unit(db_session, owner_id=owner.id, request=request)

    assert unit.title == readback.title
    assert unit.topic == readback.topic
    assert unit.curriculum_context == readback.curriculum_context
    assert unit.class_notes == readback.class_notes


TEST_USER = User(
    id="constructor-route-user",
    email="constructor-route@example.invalid",
    name="Constructor Route Teacher",
    created_at="2026-08-03T00:00:00+00:00",
    updated_at="2026-08-03T00:00:00+00:00",
)


async def test_constructor_readback_route_returns_llm_output(
    db_session_factory, monkeypatch
) -> None:
    async def fake_run_constructor(
        subject, grade_level, raw_text, *, correction=None, clarifying_answer=None, trace_id=None
    ):
        assert subject == "Maths"
        assert grade_level == "Grade 5"
        assert raw_text == "comparing fractions with unlike denominators"
        return ConstructorOutput.model_validate(_fake_readback())

    monkeypatch.setattr("planning.routes.run_constructor", fake_run_constructor)

    async def override_user() -> User:
        return TEST_USER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/units/constructor/readback",
                json={
                    "subject": "Maths",
                    "grade_level": "Grade 5",
                    "raw_text": "comparing fractions with unlike denominators",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Comparing Fractions"
    assert body["clarifying_question"] is None
