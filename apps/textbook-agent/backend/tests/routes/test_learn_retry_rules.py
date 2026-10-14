"""Server-side retry rules for shared-document Learn tasks (policy, reveal, item results)."""

from __future__ import annotations

import copy

import pytest

from core.database.models import LearnReleaseModel
from learn.runtime.attempt_rules import policy_for, reveal_for
from learn.runtime.evaluation import evaluate_interaction
from tests.routes.test_learn_runtime import (  # noqa: F401  (autouse fixtures)
    _client,
    _doc,
    _overrides,
    _publish_release,
    _seed,
)

_FEEDBACK = {"correct": "Yes.", "incorrect": "Not quite.", "partial": "Close.", "saved": "Locked in."}
_OPTIONS = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}, {"id": "c", "label": "C"}]


def _contract(cid: str, kind: str, config: dict, *, role: str | None = None, shared=True, **extra):
    contract = {
        "id": cid,
        "kind": kind,
        "prompt": "Q",
        "config": config,
        "feedback": _FEEDBACK,
        "assessment_mode": "graded" if role in (None, "check") else "practice",
        "attempt_policy": {},
        "completion": {"type": "submitted"},
        "ai_config_rule": "config-only",
    }
    if role is not None:
        contract["role"] = role
    if shared:
        contract["shared_task"] = {"id": cid}
    contract.update(extra)
    return contract


_CONTRACTS = [
    _contract("chk", "choice", {"options": _OPTIONS, "correct_option_id": "b"}, role="check"),
    _contract(
        "prac",
        "multi-select",
        {"options": [*_OPTIONS, {"id": "d", "label": "D"}], "correct_option_ids": ["a", "c"]},
        role="practice",
    ),
    _contract("pred", "choice", {"options": _OPTIONS, "correct_option_id": "b"}, role="predict"),
    _contract(
        "tr",
        "short-response",
        {"evaluation": "teacher-review"},
        role="practice",
    ),
    _contract(
        "legacy-graded",
        "choice",
        {"options": _OPTIONS, "correct_option_id": "b"},
        shared=False,
        attempt_policy={"max_attempts": 3, "allow_retry_after_correct": True},
    ),
    _contract(
        "legacy-nopolicy",
        "choice",
        {"options": _OPTIONS, "correct_option_id": "b"},
        shared=False,
        attempt_policy={"max_attempts": 1, "allow_retry_after_correct": False},
    ),
]


async def _start(client, db_session_factory) -> str:
    _lesson_id, release_id = await _publish_release(client)
    document = copy.deepcopy(_doc())
    for index, contract in enumerate(_CONTRACTS):
        document["blocks"][f"x{index}"] = {
            "id": f"x{index}",
            "component_id": "explanation-block",
            "position": index + 1,
            "content": {"prompt": "Q", "body": "Q", "callouts": []},
            "learn_interaction": contract,
        }
    async with db_session_factory() as session:
        row = await session.get(LearnReleaseModel, release_id)
        row.document_json = document
        await session.commit()
    learner = await client.post("/api/v1/learn/learners", json={"display_name": "Ada"})
    started = await client.post(
        "/api/v1/learn/instances",
        json={"learner_id": learner.json()["id"], "learn_release_id": release_id},
    )
    assert started.status_code == 200, started.text
    return started.json()["id"]


async def _submit(client, instance_id, interaction_id, sub, response):
    return await client.post(
        f"/api/v1/learn/instances/{instance_id}/attempts",
        json={
            "interaction_id": interaction_id,
            "client_submission_id": sub,
            "response_json": response,
        },
    )


# ---------------------------------------------------------------- policy_for


def test_policy_for_each_role():
    check = policy_for({"role": "check", "kind": "choice"})
    assert check == {
        "max_attempts": 2,
        "allow_retry_after_correct": False,
        "score_aggregation": "first",
        "reveal_after": None,
    }
    practice = policy_for({"role": "practice", "kind": "choice"})
    assert practice == {
        "max_attempts": None,
        "allow_retry_after_correct": True,
        "score_aggregation": "latest",
        "reveal_after": 2,
    }
    predict = policy_for({"role": "predict", "kind": "choice"})
    assert predict["max_attempts"] == 1 and predict["reveal_after"] is None
    review = policy_for(
        {"role": "practice", "kind": "short-response", "config": {"evaluation": "teacher-review"}}
    )
    assert review["max_attempts"] == 1 and review["reveal_after"] is None


def test_policy_for_legacy_contract_without_role():
    assert policy_for({"kind": "choice", "assessment_mode": "graded"})["max_attempts"] == 2
    legacy_practice = policy_for({"kind": "choice", "assessment_mode": "practice"})
    assert legacy_practice["max_attempts"] is None and legacy_practice["reveal_after"] == 2


# ----------------------------------------------------------------- reveal_for


@pytest.mark.parametrize(
    ("kind", "config", "expected"),
    [
        ("choice", {"correct_option_id": "b"}, {"selected_option_id": "b"}),
        ("multi-select", {"correct_option_ids": ["a", "c"]}, {"selected_option_ids": ["a", "c"]}),
        ("fill-blank", {"answers": [["Paris", "paris"], "France"]}, {"blanks": ["Paris", "France"]}),
        ("numeric", {"value": 4.5}, {"value": 4.5}),
        (
            "short-response",
            {"evaluation": "accepted-answers", "accepted_answers": ["dna", "DNA"]},
            {"text": "dna"},
        ),
        ("short-response", {"evaluation": "teacher-review"}, None),
        (
            "match-pairs",
            {"pairs": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}]},
            {"matches": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}]},
        ),
        ("classify", {"pairs": [{"left": "x", "right": "g"}]}, {"matches": [{"left": "x", "right": "g"}]}),
        ("sequence", {"order": ["a", "b"]}, {"order": ["a", "b"]}),
    ],
)
def test_reveal_for_shapes(kind, config, expected):
    assert reveal_for({"kind": kind, "config": config}) == expected


# --------------------------------------------------------------- item_results


def _eval(kind, config, response):
    result = evaluate_interaction({"kind": kind, "config": config, "feedback": {}}, response)
    return (result.details or {}).get("item_results")


def test_item_results_shapes():
    assert _eval(
        "match-pairs",
        {"pairs": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}]},
        {"matches": [{"left": "l1", "right": "r1"}]},
    ) == {"l1": True, "l2": False}
    assert _eval(
        "match-pairs",
        {"pairs": [{"left": "l1", "right": "r1"}, {"left": "l2", "right": "r2"}]},
        {"matches": [{"left": "l1", "right": "r2"}, {"left": "l2", "right": "r2"}]},
    ) == {"l1": False, "l2": True}
    assert _eval("sequence", {"order": ["a", "b", "c"]}, {"order": ["a", "c", "b"]}) == [
        True,
        False,
        False,
    ]
    assert _eval(
        "fill-blank", {"answers": ["x", ["y", "z"]]}, {"blanks": ["x", "nope"]}
    ) == [True, False]
    assert _eval(
        "multi-select",
        {"options": [*_OPTIONS, {"id": "d"}], "correct_option_ids": ["a", "c"]},
        {"selected_option_ids": ["a", "b"]},
    ) == {"a": True, "b": False, "c": False, "d": True}
    assert _eval(
        "choice", {"options": _OPTIONS, "correct_option_id": "b"}, {"selected_option_id": "a"}
    ) == {"a": False}
    assert _eval("numeric", {"value": 2}, {"value": 3}) is None
    assert (
        _eval(
            "short-response",
            {"evaluation": "accepted-answers", "accepted_answers": ["a"]},
            {"text": "b"},
        )
        is None
    )


# --------------------------------------------------------------- runtime flow


@pytest.mark.asyncio
async def test_check_two_tries_first_counts_and_reveals(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        first = await _submit(client, iid, "chk", "c1", {"selected_option_id": "a"})
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["outcome"] == "incorrect"
        assert body["attempts_used"] == 1 and body["attempts_left"] == 1
        assert body["reveal"] is None
        assert body["item_results"] == {"a": False}

        second = await _submit(client, iid, "chk", "c2", {"selected_option_id": "b"})
        body = second.json()
        assert body["outcome"] == "correct"
        assert body["attempts_used"] == 2 and body["attempts_left"] == 0
        assert body["reveal"] is None  # correct: nothing to reveal

        third = await _submit(client, iid, "chk", "c3", {"selected_option_id": "b"})
        assert third.status_code == 422

        detail = (await client.get(f"/api/v1/learn/instances/{iid}")).json()
        # First attempt (wrong) is the one that counts.
        assert detail["graded"]["score_earned"] == 0.0
        assert detail["graded"]["score_possible"] == 1.0
        state = detail["interaction_states"]["chk"]
        assert state["attempts_used"] == 2 and state["attempts_left"] == 0
        assert state["outcome"] == "correct" and state["feedback"] == "Yes."
        assert state["reveal"] is None
        assert [a["feedback"] for a in detail["attempts"] if a["interaction_id"] == "chk"] == [
            "Not quite.",
            "Yes.",
        ]


@pytest.mark.asyncio
async def test_check_reveals_after_two_wrong_and_blocks_third(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        one = await _submit(client, iid, "chk", "w1", {"selected_option_id": "a"})
        assert one.json()["reveal"] is None
        two = await _submit(client, iid, "chk", "w2", {"selected_option_id": "c"})
        body = two.json()
        assert body["attempts_left"] == 0
        assert body["reveal"] == {"selected_option_id": "b"}
        replay = await _submit(client, iid, "chk", "w2", {"selected_option_id": "c"})
        assert replay.status_code == 200
        assert replay.json()["idempotent_replay"] is True
        assert replay.json()["reveal"] == {"selected_option_id": "b"}
        assert replay.json()["attempts_used"] == 2
        assert (await _submit(client, iid, "chk", "w3", {"selected_option_id": "b"})).status_code == 422
        state = (await client.get(f"/api/v1/learn/instances/{iid}")).json()["interaction_states"]["chk"]
        assert state["reveal"] == {"selected_option_id": "b"}
        assert state["item_results"] == {"c": False}


@pytest.mark.asyncio
async def test_check_correct_first_try_blocks_retry(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        ok = await _submit(client, iid, "chk", "k1", {"selected_option_id": "b"})
        assert ok.json()["attempts_left"] == 0
        assert ok.json()["reveal"] is None
        again = await _submit(client, iid, "chk", "k2", {"selected_option_id": "a"})
        assert again.status_code == 422


@pytest.mark.asyncio
async def test_practice_unlimited_with_reveal_from_second_miss(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        first = (await _submit(client, iid, "prac", "p1", {"selected_option_ids": ["a"]})).json()
        assert first["outcome"] == "partial"
        assert first["attempts_left"] is None and first["reveal"] is None
        assert first["item_results"] == {"a": True, "b": True, "c": False, "d": True}
        second = (await _submit(client, iid, "prac", "p2", {"selected_option_ids": ["b"]})).json()
        assert second["reveal"] == {"selected_option_ids": ["a", "c"]}
        for n in range(3, 7):
            res = await _submit(client, iid, "prac", f"p{n}", {"selected_option_ids": ["d"]})
            assert res.status_code == 200
        done = (await _submit(client, iid, "prac", "p9", {"selected_option_ids": ["a", "c"]})).json()
        assert done["outcome"] == "correct" and done["reveal"] is None
        assert done["attempts_left"] is None
        # Practice may retry even after correct.
        assert (
            await _submit(client, iid, "prac", "p10", {"selected_option_ids": ["a"]})
        ).status_code == 200


@pytest.mark.asyncio
async def test_predict_single_submission_no_reveal(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        first = await _submit(client, iid, "pred", "d1", {"selected_option_id": "a"})
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["reveal"] is None and body["item_results"] is None
        assert body["attempts_used"] == 1 and body["attempts_left"] == 0
        assert body["feedback"] == "Locked in."
        assert (await _submit(client, iid, "pred", "d2", {"selected_option_id": "b"})).status_code == 422
        detail = (await client.get(f"/api/v1/learn/instances/{iid}")).json()
        state = detail["interaction_states"]["pred"]
        assert state["reveal"] is None and state["item_results"] is None
        assert state["feedback"] == "Locked in."
        assert [a["feedback"] for a in detail["attempts"] if a["interaction_id"] == "pred"] == [
            "Locked in."
        ]


@pytest.mark.asyncio
async def test_teacher_review_is_single_attempt_without_reveal(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        first = await _submit(client, iid, "tr", "t1", {"text": "my answer"})
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["reveal"] is None and body["attempts_left"] == 0
        assert (await _submit(client, iid, "tr", "t2", {"text": "again"})).status_code == 422


@pytest.mark.asyncio
async def test_legacy_contracts_keep_stored_policy(db_session_factory):
    async with await _client() as client:
        iid = await _start(client, db_session_factory)
        for n in range(1, 4):
            res = await _submit(client, iid, "legacy-graded", f"g{n}", {"selected_option_id": "a"})
            assert res.status_code == 200
            assert res.json()["reveal"] is None
        assert (
            await _submit(client, iid, "legacy-graded", "g4", {"selected_option_id": "a"})
        ).status_code == 422
        once = await _submit(client, iid, "legacy-nopolicy", "n1", {"selected_option_id": "a"})
        assert once.json()["attempts_left"] == 0
        assert once.json()["reveal"] is None
        assert (
            await _submit(client, iid, "legacy-nopolicy", "n2", {"selected_option_id": "b"})
        ).status_code == 422
