"""D6C — LearnRelease → Assignment → Runtime → Analytics closeout.

Uses current production semantics (including over-broad analytics LRN-007).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app import app
from core.database.models import (
    LearnAssignmentRecipientModel,
    LearningInstanceModel,
    LearnReleaseModel,
    UserModel,
)
from core.entities.user import User
from infra.auth.middleware import get_current_user
from infra.database.session import get_async_session


def _now() -> datetime:
    return datetime.now(timezone.utc)


TEACHER = User(
    id="d6c-teacher",
    email="d6c-teacher@example.invalid",
    name="D6C Teacher",
    picture_url=None,
    has_profile=True,
    created_at=_now(),
    updated_at=_now(),
)


def _doc(doc_id: str = "d6c-doc") -> dict:
    return {
        "version": 1,
        "id": doc_id,
        "title": "D6C Runtime lesson",
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
                "content": {"prompt": "Order", "body": "Order", "callouts": []},
                "learn_interaction": {
                    "id": "quiz-1",
                    "kind": "sequence",
                    "prompt": "Order",
                    "assessment_mode": "graded",
                    "attempt_policy": {
                        "max_attempts": None,
                        "show_feedback_after_submit": True,
                        "allow_retry_after_correct": True,
                    },
                    "feedback": {"correct": "ok", "incorrect": "no", "partial": "part"},
                    "completion": {"type": "submitted"},
                    "config": {
                        "order": ["p", "q"],
                        "items": [{"id": "p", "label": "P"}, {"id": "q", "label": "Q"}],
                    },
                    "accessibility": {"keyboard_operable": True},
                    "ai_config_rule": "config-only",
                    "concept_refs": [
                        {
                            "concept_id": "c-d6c",
                            "weight": 1.0,
                            "unit_id": "u-d6c",
                            "path_lesson_id": "pl-d6c",
                        }
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
    async def override_user():
        return TEACHER

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_async_session] = override_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=TEACHER.id, email=TEACHER.email, name=TEACHER.name))
        await session.commit()


async def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _publish(client: AsyncClient, *, title: str, doc_id: str) -> tuple[str, str, str]:
    created = await client.post(
        "/api/v1/builder/lessons",
        json={"title": title, "document": _doc(doc_id)},
    )
    assert created.status_code == 201, created.text
    lesson_id = created.json()["id"]
    pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
    assert pub.status_code == 201, pub.text
    body = pub.json()
    return lesson_id, body["id"], body["document_hash"]


@pytest.mark.asyncio
async def test_d6c_assignment_runtime_analytics_chain(db_session_factory):
    async with await _client() as client:
        _lesson_id, release_a, hash_a = await _publish(
            client, title="D6C A", doc_id="d6c-a"
        )
        _lesson_b, release_b, _hash_b = await _publish(
            client, title="D6C B", doc_id="d6c-b"
        )

        class_resp = await client.post(
            "/api/v1/learn/classes", json={"name": "D6C Class"}
        )
        assert class_resp.status_code == 200, class_resp.text
        class_id = class_resp.json()["id"]

        a = await client.post(
            f"/api/v1/learn/classes/{class_id}/learners",
            json={"display_name": "Learner A"},
        )
        b = await client.post(
            f"/api/v1/learn/classes/{class_id}/learners",
            json={"display_name": "Learner B"},
        )
        assert a.status_code == 200 and b.status_code == 200
        learner_a = a.json()["learner_id"]
        learner_b = b.json()["learner_id"]

        assign = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_a,
                "title": "D6C HW",
                "class_id": class_id,
                "mode": "rolling",
            },
        )
        assert assign.status_code == 200, assign.text
        assignment_id = assign.json()["id"]

        home_a = await client.get(f"/api/v1/learn/learners/{learner_a}/home")
        assert home_a.status_code == 200, home_a.text
        assigned = [
            item
            for item in home_a.json()["instances"]
            if item.get("assignment_id") == assignment_id
        ]
        assert len(assigned) == 1
        instance_a = assigned[0]["id"]
        assert assigned[0]["learn_release_id"] == release_a

        # Recipient ↔ instance linkage under current DATA-002 semantics.
        async with db_session_factory() as session:
            recipients = list(
                (
                    await session.scalars(
                        select(LearnAssignmentRecipientModel).where(
                            LearnAssignmentRecipientModel.assignment_id == assignment_id
                        )
                    )
                ).all()
            )
            assert len(recipients) >= 2
            by_learner = {row.learner_id: row for row in recipients}
            assert by_learner[learner_a].learning_instance_id == instance_a
            assert by_learner[learner_b].learning_instance_id
            inst = await session.get(LearningInstanceModel, instance_a)
            assert inst is not None
            assert inst.assignment_id == assignment_id
            assert inst.learn_release_id == release_a

        release_get = await client.get(f"/api/v1/learn/releases/{release_a}")
        assert release_get.status_code == 200
        assert release_get.json()["document_hash"] == hash_a
        assert release_get.json()["id"] == release_a

        # Attempt/progress via assignment-created instance (server-authoritative).
        attempt = await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            json={
                "interaction_id": "quiz-1",
                "client_submission_id": "d6c-sub-1",
                "response_json": {"order": ["p", "q"]},
                "section_id": "s1",
            },
        )
        assert attempt.status_code == 200, attempt.text

        detail = await client.get(f"/api/v1/learn/instances/{instance_a}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["learn_release_id"] == release_a
        assert body["score_earned"] == 2
        assert len(body["attempts"]) >= 1

        done = await client.post(f"/api/v1/learn/instances/{instance_a}/complete")
        assert done.status_code == 200
        assert done.json()["status"] == "completed"

        async with db_session_factory() as session:
            recipient = await session.scalar(
                select(LearnAssignmentRecipientModel).where(
                    LearnAssignmentRecipientModel.assignment_id == assignment_id,
                    LearnAssignmentRecipientModel.learner_id == learner_a,
                )
            )
            assert recipient is not None
            assert recipient.status in {"completed", "started", "assigned"}

        # Analytics returns assignment-scoped class data (LRN-007 fixed in P07).
        overview = await client.get(
            f"/api/v1/learn/analytics/classes/{class_id}/overview"
        )
        assert overview.status_code == 200, overview.text
        assert overview.json()["class_id"] == class_id

        lesson_overview = await client.get(
            f"/api/v1/learn/analytics/classes/{class_id}/lessons/{release_a}"
        )
        assert lesson_overview.status_code == 200, lesson_overview.text

        # Cross-learner isolation on instance read with learner sessions.
        sess_a = await client.post(
            "/api/v1/learn/sessions", json={"learner_id": learner_a}
        )
        sess_b = await client.post(
            "/api/v1/learn/sessions", json={"learner_id": learner_b}
        )
        assert sess_a.status_code == 200 and sess_b.status_code == 200
        token_a = sess_a.json()["token"]
        token_b = sess_b.json()["token"]

        ok = await client.get(
            f"/api/v1/learn/instances/{instance_a}",
            headers={"X-Learner-Session": token_a},
        )
        assert ok.status_code == 200
        denied = await client.get(
            f"/api/v1/learn/instances/{instance_a}",
            headers={"X-Learner-Session": token_b},
        )
        assert denied.status_code == 403

        # Self-started instance for learner A on release B must NOT inflate
        # assignment analytics (P07-U06 / LRN-007).
        self_started = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_a, "learn_release_id": release_b},
        )
        assert self_started.status_code == 200, self_started.text
        self_id = self_started.json()["id"]

        overview2 = await client.get(
            f"/api/v1/learn/analytics/classes/{class_id}/overview"
        )
        assert overview2.status_code == 200
        # Only assignment-bound instances counted (learner B also has one assigned).
        assert overview2.json()["completion"]["completed"] + overview2.json()["completion"]["active"] == 2

        async with db_session_factory() as session:
            instances = list(
                (
                    await session.scalars(
                        select(LearningInstanceModel).where(
                            LearningInstanceModel.learner_id == learner_a
                        )
                    )
                ).all()
            )
            ids = {row.id for row in instances}
            assert instance_a in ids
            assert self_id in ids
            assert {row.learn_release_id for row in instances} >= {release_a, release_b}

        # Release A document remains the assigned release (immutable).
        release_again = await client.get(f"/api/v1/learn/releases/{release_a}")
        assert release_again.json()["document_hash"] == hash_a
        async with db_session_factory() as session:
            row = await session.get(LearnReleaseModel, release_a)
            assert row is not None
            assert row.document_hash == hash_a
