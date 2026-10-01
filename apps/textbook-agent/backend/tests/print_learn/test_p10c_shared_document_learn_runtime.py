"""P10C: Learn runtime v2 indexing over a published SharedLessonDocument release.

Covers the audit's v2 aggregation gap (``_contracts_index`` previously only
indexed legacy v1 ``blocks``): instance create/reload, direct attempt
evaluation, score aggregation, section completion, and progress rebuild
against a real published LearnDocument v2 release built from a verified
SharedLessonDocument through the P10B adapter — one interaction per kind the
adapter can emit (choice, classify, short-response/teacher-review,
match-pairs, sequence, fill-blank).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from app import app
from core.entities.user import User
from infra.auth.middleware import get_current_user, get_optional_user
from infra.database.session import get_async_session
from tests.print_learn._p10c_fixtures import seed_ready_shared_document_lesson

OWNER_ID = "p10c-runtime-owner"


@pytest.fixture(autouse=True)
def _install_overrides(db_session_factory):
    user = User(
        id=OWNER_ID,
        email=f"{OWNER_ID}@example.invalid",
        name="P10C Runtime",
        picture_url=None,
        has_profile=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    async def override_current_user():
        return user

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_optional_user] = override_current_user
    app.dependency_overrides[get_async_session] = override_session
    yield
    app.dependency_overrides.clear()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _publish_and_start(db_session_factory, *, suffix: str) -> dict:
    seeded = await seed_ready_shared_document_lesson(
        db_session_factory, owner_id=OWNER_ID, suffix=suffix
    )
    async with await _client() as client:
        pub = await client.post(
            f"/api/v1/learn/lessons/{seeded['lesson_id']}/releases", json={}
        )
        assert pub.status_code == 201, pub.text
        release_id = pub.json()["id"]
        assert pub.json()["shared_document_id"] == seeded["document_id"]

        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Learner"})
        assert learner.status_code == 200, learner.text
        learner_id = learner.json()["id"]

        started = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
        )
        assert started.status_code == 200, started.text
        instance_id = started.json()["id"]

    return {**seeded, "release_id": release_id, "learner_id": learner_id, "instance_id": instance_id}


_CORRECT_RESPONSES = {
    "choice": {"selected_option_id": "b"},
    "classify": {"matches": [{"left": "a", "right": "g1"}, {"left": "b", "right": "g2"}]},
    "short-response": {"text": "Because the evidence supports it."},
    "match-pairs": {"matches": [{"left": "Sun", "right": "Star"}]},
    "sequence": {"order": ["egg", "larva", "pupa", "adult"]},
    "fill-blank": {"blanks": ["Paris"]},
}

# (outcome, score_earned, score_possible) for each kind's correct submission.
_EXPECTED_OUTCOME = {
    "choice": ("correct", 1.0, 1.0),
    "classify": ("correct", 2.0, 2.0),
    "short-response": ("pending-review", 0.0, 1.0),
    "match-pairs": ("correct", 1.0, 1.0),
    "sequence": ("correct", 4.0, 4.0),
    "fill-blank": ("correct", 1.0, 1.0),
}


@pytest.mark.asyncio
async def test_v2_release_evaluates_every_adapter_interaction_kind(db_session_factory):
    ctx = await _publish_and_start(db_session_factory, suffix="eval-kinds")
    interaction_ids = ctx["interaction_ids"]
    assert set(interaction_ids) == set(_CORRECT_RESPONSES)

    async with await _client() as client:
        for kind, interaction_id in interaction_ids.items():
            resp = await client.post(
                f"/api/v1/learn/instances/{ctx['instance_id']}/attempts",
                json={
                    "interaction_id": interaction_id,
                    "client_submission_id": f"sub-{kind}",
                    "response_json": _CORRECT_RESPONSES[kind],
                    "section_id": ctx["section_id"],
                },
            )
            assert resp.status_code == 200, f"{kind}: {resp.text}"
            body = resp.json()
            expected_outcome, expected_earned, expected_possible = _EXPECTED_OUTCOME[kind]
            assert body["outcome"] == expected_outcome, kind
            assert body["score_earned"] == expected_earned, kind
            assert body["score_possible"] == expected_possible, kind
            assert body["completed"] is True, kind

        detail = await client.get(f"/api/v1/learn/instances/{ctx['instance_id']}")
        assert detail.status_code == 200, detail.text
        detail_body = detail.json()
        # v2 nodes must be indexed for score aggregation (the audit gap): all
        # six graded interactions land in the "graded" bucket, not "practice".
        assert detail_body["graded"]["score_possible"] == 10.0
        assert detail_body["graded"]["score_earned"] == 9.0
        assert detail_body["practice"]["score_possible"] == 0.0
        assert set(detail_body["progress"]["completed_interaction_ids"]) == set(
            interaction_ids.values()
        )
        assert ctx["section_id"] in detail_body["progress"]["completed_section_ids"]
        assert detail_body["progress"]["score_possible"] == 10.0
        assert detail_body["progress"]["score_earned"] == 9.0


@pytest.mark.asyncio
async def test_v2_rebuild_progress_and_completion(db_session_factory):
    ctx = await _publish_and_start(db_session_factory, suffix="rebuild")
    interaction_ids = ctx["interaction_ids"]

    async with await _client() as client:
        for kind, interaction_id in interaction_ids.items():
            resp = await client.post(
                f"/api/v1/learn/instances/{ctx['instance_id']}/attempts",
                json={
                    "interaction_id": interaction_id,
                    "client_submission_id": f"sub-{kind}",
                    "response_json": _CORRECT_RESPONSES[kind],
                    "section_id": ctx["section_id"],
                },
            )
            assert resp.status_code == 200, f"{kind}: {resp.text}"

        rebuilt = await client.post(
            f"/api/v1/learn/instances/{ctx['instance_id']}/rebuild-progress"
        )
        assert rebuilt.status_code == 200, rebuilt.text
        progress = rebuilt.json()
        assert set(progress["completed_interaction_ids"]) == set(interaction_ids.values())
        assert ctx["section_id"] in progress["completed_section_ids"]
        assert progress["score_earned"] == 9.0
        assert progress["score_possible"] == 10.0

        # v2 completion must resolve required sections/interactions from
        # ordered `nodes`/`sections`, not the legacy v1 requirement extractor.
        completed = await client.post(f"/api/v1/learn/instances/{ctx['instance_id']}/complete")
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_v2_completion_rejects_missing_required_interactions(db_session_factory):
    ctx = await _publish_and_start(db_session_factory, suffix="incomplete")
    interaction_ids = ctx["interaction_ids"]
    first_kind = next(iter(interaction_ids))

    async with await _client() as client:
        # Only one of six graded interactions attempted.
        resp = await client.post(
            f"/api/v1/learn/instances/{ctx['instance_id']}/attempts",
            json={
                "interaction_id": interaction_ids[first_kind],
                "client_submission_id": "sub-partial",
                "response_json": _CORRECT_RESPONSES[first_kind],
                "section_id": ctx["section_id"],
            },
        )
        assert resp.status_code == 200, resp.text

        completed = await client.post(f"/api/v1/learn/instances/{ctx['instance_id']}/complete")
        assert completed.status_code == 422, completed.text
        missing = completed.json()["detail"]["missing_interactions"]
        assert set(missing) == set(interaction_ids.values()) - {interaction_ids[first_kind]}
