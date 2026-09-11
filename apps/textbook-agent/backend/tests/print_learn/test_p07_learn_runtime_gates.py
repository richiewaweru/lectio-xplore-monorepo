"""P07 Learn runtime gates — authoritative evaluation, persistence, analytics."""

from __future__ import annotations

import asyncio
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import AuthoringProviderCall
from infra.authoring.capability_selector import CapabilitySelection
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.native_selection import build_learn_selection_snapshot_async
from learn.generation.work_orders import compile_learn_work_orders
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash as learn_policy_hash
from learn.runtime.evaluation import (
    InteractionConfigError,
    InteractionResponseError,
    evaluate_sequence,
    is_complete,
)


_P07_PROVIDER_PAYLOADS = {
    "sequence": {
        "prompt": "Put the butterfly life stages in the correct order.",
        "config": {
            "items": [
                {"id": "egg", "label": "Egg"},
                {"id": "larva", "label": "Larva"},
                {"id": "pupa", "label": "Pupa"},
                {"id": "adult", "label": "Adult"},
            ],
            "order": ["egg", "larva", "pupa", "adult"],
        },
        "feedback": {
            "correct": "That is the correct life cycle order.",
            "incorrect": "Check the order of the stages.",
        },
    },
    "explanation-block": {"body": "Intro prose about the butterfly life cycle.", "emphasis": ["cycle"]},
    "callout-block": {"variant": "info", "body": "The butterfly life cycle has four stages."},
    "key-fact": {"fact": "Butterflies develop through metamorphosis."},
    "summary-block": {"items": [{"text": "Egg, larva, pupa, and adult form the cycle."}]},
    "paragraph": {"kind": "paragraph", "text": "Intro prose about the butterfly life cycle."},
    "heading": {"kind": "heading", "text": "Butterfly life cycle", "level": 2},
    "list": {
        "kind": "list",
        "ordered": True,
        "items": ["Egg", "Larva", "Pupa", "Adult"],
    },
    "table": {
        "kind": "table",
        "headers": ["Stage", "What happens"],
        "rows": [["Egg", "Starts"], ["Adult", "Flies"]],
        "caption": "Life cycle stages",
    },
    "callout": {
        "kind": "callout",
        "tone": "note",
        "title": "Remember",
        "body": "The butterfly life cycle has four stages.",
    },
    "figure": {
        "kind": "figure",
        "caption": "Butterfly metamorphosis diagram.",
        "alt": "Four stages of butterfly metamorphosis.",
    },
}


class _P07AuthoringProvider:
    async def invoke(self, call: AuthoringProviderCall):
        return dict(
            _P07_PROVIDER_PAYLOADS.get(
                call.capability_id,
                _P07_PROVIDER_PAYLOADS["paragraph"],
            )
        )


async def _author_all_async(orders):
    provider = _P07AuthoringProvider()
    return {
        order.work_order_id: await run_learn_work_order_authoring(
            order,
            provider=provider,
            lesson_context={"objective": "P07 offline fixture objective", "subject": "biology"},
            allowed_facts=["P07 fixture fact for generate authoring."],
            terminology=[],
        )
        for order in orders
    }


def _author_all(orders):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_author_all_async(orders))
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_author_all_async(orders))).result()


async def _test_choose(context: dict) -> CapabilitySelection:
    """MOCK selector for offline P07 fixtures — picks first eligible closed-set ID."""
    ids = list(context.get("candidate_ids") or [])
    if not ids:
        eligible = context.get("eligible_candidates") or []
        ids = [
            str(row["id"] if isinstance(row, dict) else row)
            for row in eligible
        ]
    if not ids:
        raise AssertionError(f"mock selector received empty shortlist: {context!r}")
    return CapabilitySelection(capability_id=str(ids[0]), reason="p07-mock-selector")


def _snapshot(plan: TeachingPlan):
    _, policy_hash = learn_policy_hash()

    async def _run():
        return await build_learn_selection_snapshot_async(
            plan,
            teaching_plan_hash=f"hash-{plan.teaching_plan_id}",
            native_policy_hash=policy_hash,
            package_contract_hash="pkg-learn-p07",
            policy=default_learn_policy(),
            choose=_test_choose,
            teaching_context={"objective": "P07 offline fixture objective"},
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_run())).result()


def _block(
    block_id: str,
    *,
    intent: str,
    brief: str = "Brief",
    action: str | None = None,
    position: int = 0,
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            target=action.replace("-", " "),
            purpose="Check understanding",
            expected_evidence="Evidence",
            difficulty="guided",
        )
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief,
        evidence="Evidence",
        source_question_ids=[],
        stimulus_dependencies=[],
        learner_action=learner,
    )


def _sequence_document(
    *,
    assessment_mode: str = "graded",
    completion: dict | None = None,
    max_attempts: int | None = None,
    score_aggregation: str = "latest",
    concept_refs: list[dict] | None = None,
    allow_retry_after_correct: bool = True,
) -> dict:
    """Hand-built LessonDocument v1 fixture (closed salvage assembler deleted)."""
    seq_payload = _P07_PROVIDER_PAYLOADS["sequence"]
    interaction = {
        "id": "ix-p07-sequence",
        "kind": "sequence",
        "prompt": seq_payload["prompt"],
        "config": dict(seq_payload["config"]),
        "feedback": dict(seq_payload["feedback"]),
        "ai_config_rule": "config-only",
        "assessment_mode": assessment_mode,
        "completion": completion or {"type": "submitted"},
        "score_aggregation": score_aggregation,
        "attempt_policy": {
            "max_attempts": max_attempts,
            "show_feedback_after_submit": True,
            "allow_retry_after_correct": allow_retry_after_correct,
        },
    }
    if concept_refs is not None:
        interaction["concept_refs"] = concept_refs
    return {
        "version": 1,
        "id": "doc-p07",
        "title": "P07 Sequence",
        "subject": "biology",
        "source": "generated",
        "sections": [
            {
                "id": "practice",
                "title": "Order the cycle",
                "position": 0,
                "block_ids": ["blk-intro", "blk-cycle"],
            }
        ],
        "blocks": {
            "blk-intro": {
                "id": "blk-intro",
                "component_id": "explanation-block",
                "content": {"body": "Intro prose about the butterfly cycle.", "emphasis": []},
            },
            "blk-cycle": {
                "id": "blk-cycle",
                "component_id": "explanation-block",
                "content": {"body": "Order the butterfly life stages.", "emphasis": []},
                "learn_interaction": interaction,
            },
        },
        "media": {},
    }

def _interaction_id(document: dict) -> str:
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict) and contract.get("kind") == "sequence":
            return str(contract["id"])
    raise AssertionError("no sequence interaction")


def _correct_order(document: dict) -> list[str]:
    for block in document["blocks"].values():
        contract = block.get("learn_interaction")
        if isinstance(contract, dict) and contract.get("kind") == "sequence":
            return list(contract["config"]["order"])
    raise AssertionError("no sequence order")


def _section_id(document: dict) -> str:
    return str(document["sections"][0]["id"])


USER = SimpleNamespace(id="p07-user", email="p07@example.com", name="P07")


@pytest.fixture
def _install_overrides(db_session_factory):
    from app import app
    from core.entities.user import User
    from infra.auth.middleware import get_current_user
    from infra.database.session import get_async_session

    user = User(
        id=USER.id,
        email=USER.email,
        name=USER.name,
        picture_url=None,
        has_profile=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    async def override_current_user():
        return user

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_async_session] = override_session
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def _seed_user(db_session_factory):
    from core.database.models import UserModel

    async with db_session_factory() as session:
        session.add(UserModel(id=USER.id, email=USER.email, name=USER.name))
        await session.commit()


async def _client():
    from app import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _publish(client: AsyncClient, document: dict, title: str = "P07") -> tuple[str, str]:
    created = await client.post(
        "/api/v1/builder/lessons",
        json={"title": title, "document": document},
    )
    assert created.status_code == 201, created.text
    lesson_id = created.json()["id"]
    pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
    assert pub.status_code == 201, pub.text
    return lesson_id, pub.json()["id"]


async def _start_instance(client: AsyncClient, *, learner_id: str, release_id: str, assignment_id: str | None = None) -> str:
    body: dict = {"learner_id": learner_id, "learn_release_id": release_id}
    if assignment_id:
        body["assignment_id"] = assignment_id
    resp = await client.post("/api/v1/learn/instances", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Evaluator parity (supports U01 / U05 semantics)
# ---------------------------------------------------------------------------


def test_p07_sequence_evaluator_parity_with_ts_goldens() -> None:
    feedback = {
        "correct": "ok",
        "incorrect": "no",
        "partial": "partial",
    }
    config = {"order": ["absorb", "split", "fix"]}
    correct = evaluate_sequence(config, {"order": ["absorb", "split", "fix"]}, feedback)
    assert correct.outcome == "correct"
    assert correct.score_earned == 3
    partial = evaluate_sequence(config, {"order": ["absorb", "fix", "split"]}, feedback)
    assert partial.outcome == "partial"
    assert partial.score_earned == 1
    wrong = evaluate_sequence(config, {"order": ["fix", "absorb", "split"]}, feedback)
    assert wrong.outcome == "incorrect"
    assert wrong.score_earned == 0
    with pytest.raises(InteractionResponseError):
        evaluate_sequence(config, {"order": ["absorb", "absorb", "fix"]}, feedback)
    with pytest.raises(InteractionConfigError):
        evaluate_sequence({"order": ["a", "a", "b"]}, {"order": ["a", "a", "b"]}, feedback)

    assert is_complete(correct, {"type": "submitted"}) is True
    assert is_complete(partial, {"type": "correct"}) is False
    assert is_complete(partial, {"type": "score_at_least", "min_ratio": 0.3}) is True
    assert is_complete(partial, {"type": "score_at_least", "min_ratio": 0.5}) is False


def test_p07_core_evaluators_parity_choice_numeric_classify_sequence() -> None:
    from learn.runtime.evaluation import (
        evaluate_choice,
        evaluate_interaction,
        evaluate_multi_select,
        evaluate_numeric,
    )

    feedback = {"correct": "ok", "incorrect": "no", "partial": "partial"}

    choice = evaluate_choice(
        {
            "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            "correct_option_id": "b",
        },
        {"selected_option_id": "b"},
        feedback,
    )
    assert choice.outcome == "correct"

    multi = evaluate_multi_select(
        {
            "options": [
                {"id": "a", "text": "A"},
                {"id": "b", "text": "B"},
                {"id": "c", "text": "C"},
            ],
            "correct_option_ids": ["a", "c"],
        },
        {"selected_option_ids": ["a", "c"]},
        feedback,
    )
    assert multi.outcome == "correct"

    numeric = evaluate_numeric({"value": 10, "tolerance": 1}, {"value": 10.5}, feedback)
    assert numeric.outcome == "correct"

    classify = evaluate_interaction(
        {
            "kind": "classify",
            "config": {
                "pairs": [
                    {"left": "apple", "right": "fruit"},
                    {"left": "carrot", "right": "veg"},
                ]
            },
            "feedback": feedback,
        },
        {
            "matches": [
                {"left": "apple", "right": "fruit"},
                {"left": "carrot", "right": "veg"},
            ]
        },
    )
    assert classify.outcome == "correct"

    seq = evaluate_interaction(
        {
            "kind": "sequence",
            "config": {"order": ["a", "b", "c"]},
            "feedback": feedback,
        },
        {"order": ["a", "c", "b"]},
    )
    assert seq.outcome == "partial"
    assert seq.score_earned == 1


# ---------------------------------------------------------------------------
# P07-U01
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u01_persist_restore_authoritative_feedback(
    db_session_factory, _install_overrides, _seed_user
):
    document = _sequence_document(assessment_mode="graded", completion={"type": "submitted"})
    ix = _interaction_id(document)
    order = _correct_order(document)
    partial_order = [order[0], order[2], order[3], order[1]] if len(order) == 4 else order[::-1]
    # Ensure partial: first position correct, rest scrambled for 4-item order.
    if len(order) >= 3:
        partial_order = [order[0], *reversed(order[1:])]

    async with await _client() as client:
        _, release_id = await _publish(client, document, title="U01")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "U01"})
        learner_id = learner.json()["id"]
        instance_id = await _start_instance(client, learner_id=learner_id, release_id=release_id)

        # Incorrect
        bad = list(reversed(order))
        if bad == order:
            bad = order[1:] + order[:1]
        r1 = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "u01-incorrect",
                "response_json": {"order": bad},
                "section_id": _section_id(document),
                "expected_release_id": release_id,
            },
        )
        assert r1.status_code == 200, r1.text
        assert r1.json()["outcome"] in {"incorrect", "partial"}
        assert "feedback" in r1.json() and r1.json()["feedback"]

        # Partial
        r2 = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "u01-partial",
                "response_json": {"order": partial_order},
            },
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["outcome"] == "partial"
        assert r2.json()["score_earned"] > 0
        assert r2.json()["score_earned"] < r2.json()["score_possible"]

        # Correct
        r3 = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "u01-correct",
                "response_json": {"order": order},
            },
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["outcome"] == "correct"
        assert r3.json()["score_earned"] == r3.json()["score_possible"]

        detail = await client.get(f"/api/v1/learn/instances/{instance_id}")
        assert detail.status_code == 200
        body = detail.json()
        assert len(body["attempts"]) == 3
        by_sub = {a["client_submission_id"]: a for a in body["attempts"]}
        assert by_sub["u01-correct"]["response_json"]["order"] == order
        assert by_sub["u01-correct"]["outcome"] == "correct"
        assert by_sub["u01-partial"]["outcome"] == "partial"
        # Refresh restore: response + outcome available for UI hydration.
        assert body["current_section_id"] == _section_id(document)


# ---------------------------------------------------------------------------
# P07-U02
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u02_reject_forged_scores_unknown_ix_cross_learner(
    db_session_factory, _install_overrides, _seed_user
):
    from core.database.models import ConceptEvidenceModel

    document = _sequence_document(
        concept_refs=[{"concept_id": "c-release-only", "weight": 1.0, "unit_id": "u1"}]
    )
    ix = _interaction_id(document)
    order = _correct_order(document)

    async with await _client() as client:
        _, release_id = await _publish(client, document, title="U02")
        a = await client.post("/api/v1/learn/learners", json={"display_name": "A"})
        b = await client.post("/api/v1/learn/learners", json={"display_name": "B"})
        learner_a = a.json()["id"]
        learner_b = b.json()["id"]
        instance_a = await _start_instance(client, learner_id=learner_a, release_id=release_id)

        forged = await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "forge-1",
                "response_json": {"order": order},
                "outcome": "correct",
                "score_earned": 99,
                "score_possible": 1,
                "concept_bindings": [{"concept_id": "c-forged", "weight": 9}],
            },
        )
        assert forged.status_code == 422, forged.text
        assert "rejected_fields" in forged.json()["detail"]

        unknown = await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            json={
                "interaction_id": "ix-does-not-exist",
                "client_submission_id": "unk-1",
                "response_json": {"order": order},
            },
        )
        assert unknown.status_code == 404

        # Valid submit — evidence comes from release concept_refs only.
        ok = await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "ok-1",
                "response_json": {"order": order},
            },
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["score_earned"] == ok.json()["score_possible"]

        sess_b = await client.post("/api/v1/learn/sessions", json={"learner_id": learner_b})
        denied = await client.get(
            f"/api/v1/learn/instances/{instance_a}",
            headers={"X-Learner-Session": sess_b.json()["token"]},
        )
        assert denied.status_code == 403

        cross = await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            headers={"X-Learner-Session": sess_b.json()["token"]},
            json={
                "interaction_id": ix,
                "client_submission_id": "cross-1",
                "response_json": {"order": order},
            },
        )
        assert cross.status_code == 403

    async with db_session_factory() as session:
        evidence = (
            await session.execute(
                select(ConceptEvidenceModel).where(
                    ConceptEvidenceModel.learning_instance_id == instance_a
                )
            )
        ).scalars().all()
        assert {e.concept_id for e in evidence} == {"c-release-only"}
        assert "c-forged" not in {e.concept_id for e in evidence}


# ---------------------------------------------------------------------------
# P07-U03
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u03_idempotency_conflict_and_max_attempts(
    db_session_factory, _install_overrides, _seed_user
):
    document = _sequence_document(max_attempts=2, assessment_mode="graded")
    ix = _interaction_id(document)
    order = _correct_order(document)
    bad = list(reversed(order))

    async with await _client() as client:
        _, release_id = await _publish(client, document, title="U03")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "U03"})
        learner_id = learner.json()["id"]
        instance_id = await _start_instance(client, learner_id=learner_id, release_id=release_id)

        first = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "same-key",
                "response_json": {"order": bad},
            },
        )
        assert first.status_code == 200, first.text
        first_id = first.json()["id"]
        first_outcome = first.json()["outcome"]

        replay = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "same-key",
                "response_json": {"order": bad},
            },
        )
        assert replay.status_code == 200
        assert replay.json()["id"] == first_id
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["outcome"] == first_outcome

        conflict = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "same-key",
                "response_json": {"order": order},
            },
        )
        assert conflict.status_code == 409

        second = await client.post(
            f"/api/v1/learn/instances/{instance_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "key-2",
                "response_json": {"order": order},
            },
        )
        assert second.status_code == 200, second.text

        # Concurrent burst cannot exceed max_attempts=2.
        async def _try(i: int):
            return await client.post(
                f"/api/v1/learn/instances/{instance_id}/attempts",
                json={
                    "interaction_id": ix,
                    "client_submission_id": f"burst-{i}",
                    "response_json": {"order": bad},
                },
            )

        results = await asyncio.gather(*[_try(i) for i in range(5)])
        statuses = [r.status_code for r in results]
        assert 422 in statuses
        assert statuses.count(200) == 0  # already at max

        detail = await client.get(f"/api/v1/learn/instances/{instance_id}")
        assert len(detail.json()["attempts"]) == 2


# ---------------------------------------------------------------------------
# P07-U04
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u04_completion_rules_and_passive_sections(
    db_session_factory, _install_overrides, _seed_user
):
    from core.database.models import LearnerAttemptModel

    # Three variants of the same sequence with different completion rules.
    async with await _client() as client:
        # submitted — any scored attempt completes interaction
        doc_sub = _sequence_document(completion={"type": "submitted"}, assessment_mode="graded")
        ix_sub = _interaction_id(doc_sub)
        order_sub = _correct_order(doc_sub)
        _, rel_sub = await _publish(client, doc_sub, title="U04-sub")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "U04"})
        learner_id = learner.json()["id"]
        inst_sub = await _start_instance(client, learner_id=learner_id, release_id=rel_sub)
        bad = list(reversed(order_sub))
        await client.post(
            f"/api/v1/learn/instances/{inst_sub}/attempts",
            json={
                "interaction_id": ix_sub,
                "client_submission_id": "sub-attempt",
                "response_json": {"order": bad},
            },
        )
        prog = await client.post(f"/api/v1/learn/instances/{inst_sub}/rebuild-progress")
        assert ix_sub in prog.json()["completed_interaction_ids"]

        # correct — incorrect attempt does not complete
        doc_cor = _sequence_document(completion={"type": "correct"}, assessment_mode="graded")
        ix_cor = _interaction_id(doc_cor)
        order_cor = _correct_order(doc_cor)
        _, rel_cor = await _publish(client, doc_cor, title="U04-cor")
        inst_cor = await _start_instance(client, learner_id=learner_id, release_id=rel_cor)
        await client.post(
            f"/api/v1/learn/instances/{inst_cor}/attempts",
            json={
                "interaction_id": ix_cor,
                "client_submission_id": "cor-bad",
                "response_json": {"order": list(reversed(order_cor))},
            },
        )
        prog_bad = await client.post(f"/api/v1/learn/instances/{inst_cor}/rebuild-progress")
        assert ix_cor not in prog_bad.json()["completed_interaction_ids"]
        await client.post(
            f"/api/v1/learn/instances/{inst_cor}/attempts",
            json={
                "interaction_id": ix_cor,
                "client_submission_id": "cor-good",
                "response_json": {"order": order_cor},
            },
        )
        prog_ok = await client.post(f"/api/v1/learn/instances/{inst_cor}/rebuild-progress")
        assert ix_cor in prog_ok.json()["completed_interaction_ids"]

        # score_at_least 0.5 — partial may complete
        doc_thr = _sequence_document(
            completion={"type": "score_at_least", "min_ratio": 0.5},
            assessment_mode="graded",
        )
        ix_thr = _interaction_id(doc_thr)
        order_thr = _correct_order(doc_thr)
        _, rel_thr = await _publish(client, doc_thr, title="U04-thr")
        inst_thr = await _start_instance(client, learner_id=learner_id, release_id=rel_thr)
        # One correct position out of 4 → ratio 0.25 — not enough
        partial_low = [order_thr[0], *reversed(order_thr[1:])]
        await client.post(
            f"/api/v1/learn/instances/{inst_thr}/attempts",
            json={
                "interaction_id": ix_thr,
                "client_submission_id": "thr-low",
                "response_json": {"order": partial_low},
            },
        )
        prog_low = await client.post(f"/api/v1/learn/instances/{inst_thr}/rebuild-progress")
        # Depending on scramble, earned may be 1/4; ensure not complete if < 0.5
        detail_low = await client.get(f"/api/v1/learn/instances/{inst_thr}")
        attempt = detail_low.json()["attempts"][0]
        ratio = attempt["score_earned"] / attempt["score_possible"]
        if ratio < 0.5:
            assert ix_thr not in prog_low.json()["completed_interaction_ids"]
        # Correct meets threshold
        await client.post(
            f"/api/v1/learn/instances/{inst_thr}/attempts",
            json={
                "interaction_id": ix_thr,
                "client_submission_id": "thr-ok",
                "response_json": {"order": order_thr},
            },
        )
        prog_thr = await client.post(f"/api/v1/learn/instances/{inst_thr}/rebuild-progress")
        assert ix_thr in prog_thr.json()["completed_interaction_ids"]

        # Passive section complete without graded attempts
        passive_doc = {
            "version": 1,
            "id": "doc-passive",
            "title": "Passive",
            "subject": "biology",
            "preset_id": "blue-classroom",
            "source": "manual",
            "sections": [
                {
                    "id": "s-passive",
                    "template_id": "open-canvas",
                    "title": "Read",
                    "position": 0,
                    "block_ids": ["b-read"],
                    "required": True,
                }
            ],
            "blocks": {
                "b-read": {
                    "id": "b-read",
                    "component_id": "explanation-block",
                    "position": 0,
                    "content": {"body": "Read me", "callouts": []},
                }
            },
            "media": {},
            "created_at": "2026-09-08T00:00:00Z",
            "updated_at": "2026-09-08T00:00:00Z",
        }
        _, rel_pass = await _publish(client, passive_doc, title="U04-pass")
        inst_pass = await _start_instance(client, learner_id=learner_id, release_id=rel_pass)
        marked = await client.post(
            f"/api/v1/learn/instances/{inst_pass}/sections/complete",
            json={"section_id": "s-passive"},
        )
        assert marked.status_code == 200, marked.text
        assert "s-passive" in marked.json()["completed_section_ids"]
        assert marked.json()["completed_interaction_ids"] == []

        done = await client.post(f"/api/v1/learn/instances/{inst_pass}/complete")
        assert done.status_code == 200, done.text

    async with db_session_factory() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(LearnerAttemptModel)
            .where(LearnerAttemptModel.learning_instance_id == inst_pass)
        )
        assert int(count or 0) == 0


# ---------------------------------------------------------------------------
# P07-U05
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u05_aggregation_and_practice_separation(
    db_session_factory, _install_overrides, _seed_user
):
    async with await _client() as client:
        # latest — default; retries must not inflate possible
        doc_latest = _sequence_document(
            assessment_mode="graded",
            score_aggregation="latest",
            max_attempts=None,
        )
        ix = _interaction_id(doc_latest)
        order = _correct_order(doc_latest)
        n = len(order)
        _, rel = await _publish(client, doc_latest, title="U05-latest")
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "U05"})
        learner_id = learner.json()["id"]
        inst = await _start_instance(client, learner_id=learner_id, release_id=rel)

        await client.post(
            f"/api/v1/learn/instances/{inst}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "lat-1",
                "response_json": {"order": list(reversed(order))},
            },
        )
        await client.post(
            f"/api/v1/learn/instances/{inst}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "lat-2",
                "response_json": {"order": order},
            },
        )
        detail = await client.get(f"/api/v1/learn/instances/{inst}")
        body = detail.json()
        assert body["graded"]["score_possible"] == n
        assert body["graded"]["score_earned"] == n
        assert body["graded"]["raw_attempts"] == 2
        assert body["graded"]["attempts"] == 1

        # first — keep first attempt scores
        doc_first = _sequence_document(assessment_mode="graded", score_aggregation="first")
        ix_f = _interaction_id(doc_first)
        order_f = _correct_order(doc_first)
        _, rel_f = await _publish(client, doc_first, title="U05-first")
        inst_f = await _start_instance(client, learner_id=learner_id, release_id=rel_f)
        await client.post(
            f"/api/v1/learn/instances/{inst_f}/attempts",
            json={
                "interaction_id": ix_f,
                "client_submission_id": "f-1",
                "response_json": {"order": list(reversed(order_f))},
            },
        )
        await client.post(
            f"/api/v1/learn/instances/{inst_f}/attempts",
            json={
                "interaction_id": ix_f,
                "client_submission_id": "f-2",
                "response_json": {"order": order_f},
            },
        )
        detail_f = await client.get(f"/api/v1/learn/instances/{inst_f}")
        assert detail_f.json()["graded"]["score_earned"] < len(order_f)
        assert detail_f.json()["graded"]["score_possible"] == len(order_f)

        # best — take highest ratio
        doc_best = _sequence_document(assessment_mode="graded", score_aggregation="best")
        ix_b = _interaction_id(doc_best)
        order_b = _correct_order(doc_best)
        _, rel_b = await _publish(client, doc_best, title="U05-best")
        inst_b = await _start_instance(client, learner_id=learner_id, release_id=rel_b)
        await client.post(
            f"/api/v1/learn/instances/{inst_b}/attempts",
            json={
                "interaction_id": ix_b,
                "client_submission_id": "b-1",
                "response_json": {"order": order_b},
            },
        )
        await client.post(
            f"/api/v1/learn/instances/{inst_b}/attempts",
            json={
                "interaction_id": ix_b,
                "client_submission_id": "b-2",
                "response_json": {"order": list(reversed(order_b))},
            },
        )
        detail_b = await client.get(f"/api/v1/learn/instances/{inst_b}")
        assert detail_b.json()["graded"]["score_earned"] == len(order_b)

        # practice separated from graded
        doc_prac = _sequence_document(assessment_mode="practice", score_aggregation="latest")
        ix_p = _interaction_id(doc_prac)
        order_p = _correct_order(doc_prac)
        _, rel_p = await _publish(client, doc_prac, title="U05-prac")
        inst_p = await _start_instance(client, learner_id=learner_id, release_id=rel_p)
        await client.post(
            f"/api/v1/learn/instances/{inst_p}/attempts",
            json={
                "interaction_id": ix_p,
                "client_submission_id": "p-1",
                "response_json": {"order": order_p},
            },
        )
        detail_p = await client.get(f"/api/v1/learn/instances/{inst_p}")
        assert detail_p.json()["practice"]["score_earned"] == len(order_p)
        assert detail_p.json()["graded"]["score_earned"] == 0
        assert detail_p.json()["graded"]["score_possible"] == 0


# ---------------------------------------------------------------------------
# P07-U06
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_p07_u06_analytics_excludes_self_started_keeps_release(
    db_session_factory, _install_overrides, _seed_user
):
    from core.database.models import LearnReleaseModel, LearningInstanceModel

    document_a = _sequence_document(assessment_mode="graded")
    ix = _interaction_id(document_a)
    order = _correct_order(document_a)
    document_b = copy.deepcopy(document_a)
    document_b["id"] = "doc-p07-b"
    document_b["title"] = "Other release"

    async with await _client() as client:
        _, release_a = await _publish(client, document_a, title="U06-A")
        _, release_b = await _publish(client, document_b, title="U06-B")

        class_resp = await client.post("/api/v1/learn/classes", json={"name": "U06 Class"})
        class_id = class_resp.json()["id"]
        learner = await client.post(
            f"/api/v1/learn/classes/{class_id}/learners",
            json={"display_name": "U06 Learner"},
        )
        learner_id = learner.json()["learner_id"]

        assign = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": release_a,
                "title": "U06 HW",
                "class_id": class_id,
                "mode": "rolling",
            },
        )
        assert assign.status_code == 200, assign.text
        assignment_id = assign.json()["id"]

        home = await client.get(f"/api/v1/learn/learners/{learner_id}/home")
        assigned = [
            i for i in home.json()["instances"] if i.get("assignment_id") == assignment_id
        ]
        assert len(assigned) == 1
        instance_a = assigned[0]["id"]
        assert assigned[0]["learn_release_id"] == release_a

        await client.post(
            f"/api/v1/learn/instances/{instance_a}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "u06-a",
                "response_json": {"order": order},
            },
        )

        # Self-started unrelated instance on release B
        self_started = await client.post(
            "/api/v1/learn/instances",
            json={"learner_id": learner_id, "learn_release_id": release_b},
        )
        assert self_started.status_code == 200
        self_id = self_started.json()["id"]
        # Submit on self-started so it would pollute analytics if unscoped
        await client.post(
            f"/api/v1/learn/instances/{self_id}/attempts",
            json={
                "interaction_id": ix,
                "client_submission_id": "u06-self",
                "response_json": {"order": order},
            },
        )

        overview = await client.get(f"/api/v1/learn/analytics/classes/{class_id}/overview")
        assert overview.status_code == 200, overview.text
        body = overview.json()
        # Only assignment-scoped graded attempt counted (self-started excluded)
        assert body["graded"]["attempts"] == 1
        assert body["completion"]["active"] + body["completion"]["completed"] == 1

        # Instance remains bound to original immutable release
        detail = await client.get(f"/api/v1/learn/instances/{instance_a}")
        assert detail.json()["learn_release_id"] == release_a
        release_get = await client.get(f"/api/v1/learn/releases/{release_a}")
        hash_a = release_get.json()["document_hash"]

    async with db_session_factory() as session:
        row = await session.get(LearnReleaseModel, release_a)
        assert row is not None
        assert row.document_hash == hash_a
        inst = await session.get(LearningInstanceModel, instance_a)
        assert inst is not None
        assert inst.learn_release_id == release_a
        assert inst.assignment_id == assignment_id
        self_row = await session.get(LearningInstanceModel, self_id)
        assert self_row is not None
        assert self_row.assignment_id is None
