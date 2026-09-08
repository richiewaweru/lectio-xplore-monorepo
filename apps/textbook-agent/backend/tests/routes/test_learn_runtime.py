"""Phases 06–11: runtime, evidence, classes, assignments, insight."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from infra.auth.middleware import get_current_user
from core.database.models import LearnReleaseModel, UserModel
from infra.database.session import get_async_session
from core.entities.user import User
from learn.runtime_models import LearnerAttemptModel, LearningInstanceModel
from learn.runtime_service import classify_concept, rebuild_progress


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEACHER = User(
    id="rt-teacher",
    email="rt-teacher@example.com",
    name="Runtime Teacher",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)

OTHER = User(
    id="rt-other",
    email="rt-other@example.com",
    name="Other Teacher",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


def _doc() -> dict:
    """Publishable lesson with a Sequence interaction for authoritative evaluation."""
    return {
        "version": 1,
        "id": "doc-rt",
        "title": "Runtime lesson",
        "subject": "biology",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "s1",
                "template_id": "open-canvas",
                "title": "Check",
                "position": 0,
                "block_ids": ["b1"],
            }
        ],
        "blocks": {
            "b1": {
                "id": "b1",
                "component_id": "explanation-block",
                "position": 0,
                "content": {"prompt": "Order the stages", "body": "Order the stages", "callouts": []},
                "learn_interaction": {
                    "id": "ix-rt-sequence",
                    "kind": "sequence",
                    "prompt": "Order the stages",
                    "assessment_mode": "graded",
                    "attempt_policy": {
                        "max_attempts": None,
                        "show_feedback_after_submit": True,
                        "allow_retry_after_correct": True,
                    },
                    "feedback": {
                        "correct": "Correct",
                        "incorrect": "Incorrect",
                        "partial": "Partial",
                    },
                    "completion": {"type": "submitted"},
                    "score_aggregation": "latest",
                    "config": {
                        "order": ["a", "b", "c"],
                        "items": [
                            {"id": "a", "label": "A"},
                            {"id": "b", "label": "B"},
                            {"id": "c", "label": "C"},
                        ],
                    },
                    "accessibility": {"keyboard_operable": True},
                    "ai_config_rule": "config-only",
                    "concept_refs": [
                        {"concept_id": "c-photo", "weight": 0.6, "unit_id": "u1", "path_lesson_id": "pl1"},
                        {"concept_id": "c-carbon", "weight": 0.4, "unit_id": "u1"},
                    ],
                },
            }
        },
        "media": {},
        "created_at": "2026-09-06T00:00:00Z",
        "updated_at": "2026-09-06T00:00:00Z",
    }


@pytest.fixture(autouse=True)
def _overrides(db_session_factory):
    state = {"user": TEACHER}

    async def override_user():
        return state["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    yield state
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=TEACHER.id, email=TEACHER.email, name=TEACHER.name))
        session.add(UserModel(id=OTHER.id, email=OTHER.email, name=OTHER.name))
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _publish_release(client: AsyncClient) -> tuple[str, str]:
    created = await client.post(
        "/api/v1/builder/lessons",
        json={"title": "Runtime lesson", "document": _doc()},
    )
    assert created.status_code == 201, created.text
    lesson_id = created.json()["id"]
    pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
    assert pub.status_code == 201, pub.text
    return lesson_id, pub.json()["id"]


@pytest.mark.asyncio
async def test_runtime_attempts_idempotency_resume_and_evidence(db_session_factory, _overrides):
    async with await _client() as client:
        _lesson_id, release_id = await _publish_release(client)
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Ada"})
        assert learner.status_code == 200, learner.text
        learner_id = learner.json()["id"]

        i1 = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
        )
        assert i1.status_code == 200, i1.text
        instance_id = i1.json()["id"]

        # Separate instance for same release
        i2 = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
        )
        assert i2.status_code == 200
        assert i2.json()["id"] != instance_id

        # Incorrect, incorrect, then correct — aggregation is latest (no score inflation).
        responses = [
            ["c", "b", "a"],
            ["c", "b", "a"],
            ["a", "b", "c"],
        ]
        for idx, order in enumerate(responses, start=1):
            resp = await client.post(
                f"/api/v1/learn/instances/{instance_id}/attempts",
                json={
                    "interaction_id": "ix-rt-sequence",
                    "client_submission_id": f"sub-{idx}",
                    "response_json": {"order": order},
                    "section_id": "s1",
                },
            )
            assert resp.status_code == 200, resp.text

        # Duplicate submission id with same response is idempotent.
        dup = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": "ix-rt-sequence",
                "client_submission_id": "sub-3",
                "response_json": {"order": ["a", "b", "c"]},
            },
        )
        assert dup.status_code == 200
        assert dup.json()["idempotent_replay"] is True

        # Same key / different response conflicts.
        conflict = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": "ix-rt-sequence",
                "client_submission_id": "sub-3",
                "response_json": {"order": ["c", "b", "a"]},
            },
        )
        assert conflict.status_code == 409

        detail = await client.get(f"/api/v1/learn/instances/{instance_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert len(body["attempts"]) == 3
        assert body["score_earned"] == 3
        assert body["score_possible"] == 3

        rebuilt = await client.post(f"/api/v1/learn/instances/{instance_id}/rebuild-progress")
        assert rebuilt.status_code == 200
        assert rebuilt.json()["score_earned"] == 3

        states = await client.post(f"/api/v1/learn/learners/{learner_id}/rebuild-concept-states")
        assert states.status_code == 200
        assert {s["concept_id"] for s in states.json()} == {"c-photo", "c-carbon"}

        done = await client.post(f"/api/v1/learn/instances/{instance_id}/complete")
        assert done.status_code == 200
        assert done.json()["status"] == "completed"

        # Release still immutable / present
        release = await client.get(f"/api/v1/learn/releases/{release_id}")
        assert release.status_code == 200

    async with db_session_factory() as session:
        attempts = (
            await session.execute(
                select(LearnerAttemptModel).where(
                    LearnerAttemptModel.learning_instance_id == instance_id
                )
            )
        ).scalars().all()
        assert len(attempts) == 3


@pytest.mark.asyncio
async def test_classes_assignments_permissions_and_rolling(db_session_factory, _overrides):
    async with await _client() as client:
        _lesson_id, release_id = await _publish_release(client)
        c1 = await client.post("/api/v1/learn/classes", json={"name": "Period 1"})
        c2 = await client.post("/api/v1/learn/classes", json={"name": "Period 2"})
        assert c1.status_code == 200 and c2.status_code == 200
        class_id = c1.json()["id"]
        invite = c1.json()["invite_code"]

        add = await client.post(
            f"/api/v1/learn/classes/{class_id}/learners",
            json={"display_name": "Sam"},
        )
        assert add.status_code == 200
        learner_id = add.json()["learner_id"]

        # Second class membership for same learner
        add2 = await client.post(
            f"/api/v1/learn/classes/{c2.json()['id']}/learners",
            json={"learner_id": learner_id},
        )
        assert add2.status_code == 200

        rolling = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "HW1",
                "class_id": class_id,
                "mode": "rolling",
            },
        )
        assert rolling.status_code == 200, rolling.text
        rolling_id = rolling.json()["id"]

        snapshot = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "Quiz now",
                "class_id": class_id,
                "mode": "snapshot",
            },
        )
        assert snapshot.status_code == 200
        snapshot_id = snapshot.json()["id"]

        # Late joiner
        late = await client.post("/api/v1/learn/learners", json={"display_name": "Late"})
        late_id = late.json()["id"]
        join = await client.post(
            "/api/v1/learn/classes/accept-invite",
            json={"invite_code": invite, "learner_id": late_id},
        )
        assert join.status_code == 200

        home = await client.get(f"/api/v1/learn/learners/{late_id}/home")
        assert home.status_code == 200
        assignment_ids = {i["assignment_id"] for i in home.json()["instances"]}
        assert rolling_id in assignment_ids
        assert snapshot_id not in assignment_ids

        selected = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "Selected",
                "mode": "selected",
                "selected_learner_ids": [learner_id],
            },
        )
        assert selected.status_code == 200

        # Unauthorized teacher cannot read insight
        _overrides["user"] = OTHER
        denied = await client.get(f"/api/v1/learn/classes/{class_id}/insight")
        assert denied.status_code == 404
        _overrides["user"] = TEACHER

        insight = await client.get(f"/api/v1/learn/classes/{class_id}/insight")
        assert insight.status_code == 200
        assert insight.json()["class_id"] == class_id


def test_concept_classification_thresholds():
    assert classify_concept(9, 10) == "Strong"
    assert classify_concept(6, 10) == "Developing"
    assert classify_concept(5, 10) == "Needs Practice"
    assert classify_concept(1, 10) == "Needs Practice"
    assert classify_concept(0, 0) == "Needs Practice"


@pytest.mark.asyncio
async def test_learner_session_own_data_and_resume(_overrides):
    async with await _client() as client:
        _lesson_id, release_id = await _publish_release(client)
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Ada"})
        learner_id = learner.json()["id"]
        other = await client.post("/api/v1/learn/learners", json={"display_name": "Bob"})
        other_id = other.json()["id"]

        sess = await client.post("/api/v1/learn/sessions", json={"learner_id": learner_id})
        assert sess.status_code == 200, sess.text
        token = sess.json()["token"]

        other_sess = await client.post("/api/v1/learn/sessions", json={"learner_id": other_id})
        other_token = other_sess.json()["token"]

        inst = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_id},
            headers={"X-Learner-Session": token},
        )
        assert inst.status_code == 200, inst.text
        instance_id = inst.json()["id"]

        resume = await client.post(
            f"/api/v1/learn/instances/{instance_id}/resume",
            json={"section_id": "s1"},
            headers={"X-Learner-Session": token},
        )
        assert resume.status_code == 200
        assert resume.json()["current_section_id"] == "s1"

        attempt = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": "ix-rt-sequence",
                "client_submission_id": "s1",
                "response_json": {"order": ["a", "b", "c"]},
                "section_id": "s1",
            },
            headers={"X-Learner-Session": token},
        )
        assert attempt.status_code == 200

        denied = await client.get(
            f"/api/v1/learn/instances/{instance_id}",
            headers={"X-Learner-Session": other_token},
        )
        assert denied.status_code == 403

        detail = await client.get(
            f"/api/v1/learn/instances/{instance_id}",
            headers={"X-Learner-Session": token},
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["current_section_id"] == "s1"
        assert body["graded"]["attempts"] == 1
        assert body["practice"]["attempts"] == 0

        done = await client.post(
            f"/api/v1/learn/instances/{instance_id}/complete",
            headers={"X-Learner-Session": token},
        )
        assert done.status_code == 200


@pytest.mark.asyncio
async def test_multi_class_assignment_recipients(_overrides):
    async with await _client() as client:
        _lesson_id, release_id = await _publish_release(client)
        c1 = await client.post("/api/v1/learn/classes", json={"name": "A"})
        c2 = await client.post("/api/v1/learn/classes", json={"name": "B"})
        class_a = c1.json()["id"]
        class_b = c2.json()["id"]
        a1 = await client.post(
            f"/api/v1/learn/classes/{class_a}/learners", json={"display_name": "A1"}
        )
        b1 = await client.post(
            f"/api/v1/learn/classes/{class_b}/learners", json={"display_name": "B1"}
        )
        assert a1.status_code == 200 and b1.status_code == 200

        assign = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_id,
                "title": "Multi",
                "class_ids": [class_a, class_b],
                "mode": "rolling",
            },
        )
        assert assign.status_code == 200, assign.text
        home_a = await client.get(f"/api/v1/learn/learners/{a1.json()['learner_id']}/home")
        home_b = await client.get(f"/api/v1/learn/learners/{b1.json()['learner_id']}/home")
        assert any(i["assignment_id"] == assign.json()["id"] for i in home_a.json()["instances"])
        assert any(i["assignment_id"] == assign.json()["id"] for i in home_b.json()["instances"])
