"""Policy cleanup v4 — runtime, Builder, and persistence gates (G18–G21)."""

from __future__ import annotations

import pytest

from learn.runtime.evaluation import evaluate_interaction
from tests.remaining_fixes.r04_fixtures import (
    install_api_overrides,
    publish_lesson,
    r04_client,
    seed_r04_user,
)


def _short_response_document(
    *,
    evaluation: str,
    accepted_answers: list[str] | None = None,
    review_guidance: str | None = None,
    completion: dict | None = None,
    title: str = "Policy short-response",
) -> dict:
    config: dict = {"evaluation": evaluation}
    if accepted_answers is not None:
        config["accepted_answers"] = accepted_answers
        config["case_sensitive"] = False
    if review_guidance is not None:
        config["review_guidance"] = review_guidance
    contract = {
        "id": "ix-sr-policy",
        "kind": "short-response",
        "prompt": "What is the green pigment in leaves?",
        "assessment_mode": "graded",
        "attempt_policy": {
            "max_attempts": None,
            "show_feedback_after_submit": True,
            "allow_retry_after_correct": True,
        },
        "feedback": {
            "correct": "Correct.",
            "incorrect": "Not yet.",
            "partial": "Submitted for teacher review.",
        },
        "completion": completion or {"type": "submitted"},
        "config": config,
        "accessibility": {
            "aria_label": "What is the green pigment in leaves?",
            "narration": "optional",
            "keyboard_operable": True,
        },
        "ai_config_rule": "config-only",
        "concept_refs": [],
        "provenance": {
            "policy": {
                "policy_version": "1.0.0",
                "effective_assessment_policy": (
                    "teacher_review" if evaluation == "teacher-review" else "automatic_required"
                ),
                "executed_evaluation_mode": evaluation,
            }
        },
    }
    return {
        "version": 1,
        "id": "lesson-policy-sr",
        "title": title,
        "subject": "science",
        "sections": [
            {
                "id": "sec-1",
                "position": 0,
                "title": "Check",
                "block_ids": ["b-sr"],
                "assessment_mode": "graded",
            }
        ],
        "blocks": {
            "b-sr": {
                "id": "b-sr",
                "component_id": "explanation-block",
                "content": {"body": "Chlorophyll absorbs light."},
                "learn_interaction": contract,
                "assessment_mode": "graded",
            }
        },
        "media": {},
    }


async def _start_instance(client, *, learner_id: str, release_id: str) -> str:
    resp = await client.post(
        "/api/v1/learn/instances",
        json={"learner_id": learner_id, "learn_release_id": release_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


@pytest.fixture
def _api(db_session_factory):
    install_api_overrides(db_session_factory)
    yield
    from app import app

    app.dependency_overrides.clear()


@pytest.fixture
async def _seed(db_session_factory):
    await seed_r04_user(db_session_factory)


@pytest.mark.asyncio
async def test_g18_automatic_and_teacher_review_runtime(db_session_factory, _api, _seed) -> None:
    auto_doc = _short_response_document(
        evaluation="accepted-answers",
        accepted_answers=["chlorophyll"],
        title="Policy auto",
    )
    review_doc = _short_response_document(
        evaluation="teacher-review",
        review_guidance="Assess whether the response links observation to claim.",
        completion={"type": "submitted"},
        title="Policy review",
    )
    contract = auto_doc["blocks"]["b-sr"]["learn_interaction"]
    assert evaluate_interaction(contract, {"text": "chlorophyll"}).outcome == "correct"
    assert evaluate_interaction(contract, {"text": "wrong"}).outcome == "incorrect"

    async with await r04_client() as client:
        _, release_id = await publish_lesson(client, auto_doc, title="Policy auto")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Policy"})
        learner_id = learner.json()["id"]
        instance_id = await _start_instance(
            client, learner_id=learner_id, release_id=release_id
        )

        correct = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": "ix-sr-policy",
                "client_submission_id": "auto-correct-1",
                "response_json": {"text": "chlorophyll"},
                "expected_release_id": release_id,
            },
        )
        assert correct.status_code == 200, correct.text
        assert correct.json()["outcome"] == "correct"

        wrong = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": "ix-sr-policy",
                "client_submission_id": "auto-wrong-1",
                "response_json": {"text": "carotene"},
            },
        )
        assert wrong.status_code == 200, wrong.text
        assert wrong.json()["outcome"] == "incorrect"

        _, review_release = await publish_lesson(client, review_doc, title="Policy review")
        learner2 = await client.post(
            "/api/v1/learn/learners", json={"display_name": "Policy2"}
        )
        instance2 = await _start_instance(
            client, learner_id=learner2.json()["id"], release_id=review_release
        )
        review_attempt = await client.post(
            f"/api/v1/learn/instances/{instance2}/attempts",
            json={
                "interaction_id": "ix-sr-policy",
                "client_submission_id": "review-1",
                "response_json": {"text": "The glass fogged because vapour condensed."},
                "expected_release_id": review_release,
            },
        )
        assert review_attempt.status_code == 200, review_attempt.text
        body = review_attempt.json()
        assert body["outcome"] == "pending-review"
        assert body["score_earned"] == 0
        assert body.get("completed") is True


@pytest.mark.asyncio
async def test_g20_g21_publish_builder_policy_validation(db_session_factory, _api, _seed) -> None:
    document = _short_response_document(
        evaluation="accepted-answers",
        accepted_answers=["chlorophyll"],
        title="Policy publish",
    )
    async with await r04_client() as client:
        lesson_id, release_v1 = await publish_lesson(client, document, title="Policy publish")
        v1 = await client.get(f"/api/v1/learn/releases/{release_v1}")
        assert v1.status_code == 200
        hash_v1 = v1.json()["document_hash"]

        draft = dict(v1.json()["document"])
        block = draft["blocks"]["b-sr"]
        block["learn_interaction"]["prompt"] = "Name the green pigment in leaves."
        block["learn_interaction"]["provenance"] = {
            **(block["learn_interaction"].get("provenance") or {}),
            "policy": {
                "policy_version": "1.0.0",
                "effective_assessment_policy": "automatic_required",
                "executed_evaluation_mode": "accepted-answers",
            },
        }
        ok = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Policy publish edited", "document": draft},
        )
        assert ok.status_code == 200, ok.text

        bad = dict(draft)
        bad_block = bad["blocks"]["b-sr"]
        bad_block["learn_interaction"]["config"] = {
            "evaluation": "accepted-answers",
            "accepted_answers": [],
        }
        rejected = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Policy publish bad", "document": bad},
        )
        assert rejected.status_code == 422, rejected.text

        pub2 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub2.status_code == 201, pub2.text
        release_v2 = pub2.json()["id"]

        v1_again = await client.get(f"/api/v1/learn/releases/{release_v1}")
        assert v1_again.json()["document_hash"] == hash_v1
        v2 = await client.get(f"/api/v1/learn/releases/{release_v2}")
        assert v2.status_code == 200
        assert v2.json()["document_hash"] != hash_v1
        prompt = v2.json()["document"]["blocks"]["b-sr"]["learn_interaction"]["prompt"]
        assert prompt == "Name the green pigment in leaves."
        policy = (
            v2.json()["document"]["blocks"]["b-sr"]["learn_interaction"]
            .get("provenance", {})
            .get("policy", {})
        )
        assert policy.get("executed_evaluation_mode") == "accepted-answers"
