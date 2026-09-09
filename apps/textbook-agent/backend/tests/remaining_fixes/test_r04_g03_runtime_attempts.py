"""R04-G03 — runtime attempts via API; authoritative DB (REGRESSION_SCENARIOS §9)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.remaining_fixes.r04_fixtures import (
    build_envelope_sequence_document,
    correct_order,
    install_api_overrides,
    interaction_id,
    publish_lesson,
    r04_client,
    seed_r04_user,
    section_id,
)


@pytest.fixture
def _api(db_session_factory):
    install_api_overrides(db_session_factory)
    yield
    from app import app

    app.dependency_overrides.clear()


@pytest.fixture
async def _seed(db_session_factory):
    await seed_r04_user(db_session_factory)


async def _start_instance(client, *, learner_id: str, release_id: str) -> str:
    resp = await client.post(
        "/api/v1/learn/instances",
        json={"learner_id": learner_id, "learn_release_id": release_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_r04_g03_correct_incorrect_attempts_fresh_db(
    db_session_factory, _api, _seed
) -> None:
    """Envelope document; runtime API; fresh session reload verifies stored outcomes."""
    from core.database.models import ConceptEvidenceModel, LearnerAttemptModel

    document = build_envelope_sequence_document(
        concept_refs=[{"concept_id": "c-r04-release", "weight": 1.0, "unit_id": "u1"}]
    )
    ix = interaction_id(document)
    order = correct_order(document)
    bad = list(reversed(order))

    async with await r04_client() as client:
        _, release_id = await publish_lesson(client, document, title="R04-G03")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "R04"})
        learner_id = learner.json()["id"]
        instance_id = await _start_instance(client, learner_id=learner_id, release_id=release_id)

        incorrect = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "r04-incorrect",
                "response_json": {"order": bad},
                "section_id": section_id(document),
                "expected_release_id": release_id,
            },
        )
        assert incorrect.status_code == 200, incorrect.text
        assert incorrect.json()["outcome"] in {"incorrect", "partial"}
        assert incorrect.json()["score_earned"] < incorrect.json()["score_possible"]

        correct = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "r04-correct",
                "response_json": {"order": order},
            },
        )
        assert correct.status_code == 200, correct.text
        assert correct.json()["outcome"] == "correct"
        assert correct.json()["score_earned"] == correct.json()["score_possible"]

    async with db_session_factory() as session:
        attempts = (
            await session.execute(
                select(LearnerAttemptModel).where(
                    LearnerAttemptModel.learning_instance_id == instance_id
                )
            )
        ).scalars().all()
        assert len(attempts) == 2
        by_key = {a.client_submission_id: a for a in attempts}
        assert by_key["r04-correct"].outcome == "correct"
        assert by_key["r04-incorrect"].outcome in {"incorrect", "partial"}

        from core.database.models import LearningInstanceModel

        instance = await session.get(LearningInstanceModel, instance_id)
        assert instance is not None
        assert instance.learn_release_id == release_id

        evidence = (
            await session.execute(
                select(ConceptEvidenceModel).where(
                    ConceptEvidenceModel.learning_instance_id == instance_id
                )
            )
        ).scalars().all()
        assert {e.concept_id for e in evidence} == {"c-r04-release"}


@pytest.mark.asyncio
async def test_r04_g03_reject_forged_client_score(db_session_factory, _api, _seed) -> None:
    """Server rejects forged outcome/score; DB has no forged evidence."""
    from core.database.models import ConceptEvidenceModel

    document = build_envelope_sequence_document()
    ix = interaction_id(document)
    order = correct_order(document)

    async with await r04_client() as client:
        _, release_id = await publish_lesson(client, document, title="R04-forge")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Forge"})
        instance_id = await _start_instance(client, learner_id=learner.json()["id"], release_id=release_id)

        forged = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "forge-r04",
                "response_json": {"order": order},
                "outcome": "correct",
                "score_earned": 99,
                "score_possible": 1,
                "concept_bindings": [{"concept_id": "c-forged", "weight": 9}],
            },
        )
        assert forged.status_code == 422, forged.text

        ok = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "ok-r04",
                "response_json": {"order": order},
            },
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["score_earned"] == ok.json()["score_possible"]

    async with db_session_factory() as session:
        evidence = (
            await session.execute(
                select(ConceptEvidenceModel).where(
                    ConceptEvidenceModel.learning_instance_id == instance_id
                )
            )
        ).scalars().all()
        assert "c-forged" not in {e.concept_id for e in evidence}
