"""Doc 38 3.2/3.3: topic path state rule, /topics endpoint, and home bucket de-duplication."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from tests.routes.test_learn_runtime import OTHER, TEACHER, _doc

from app import app
from core.database.models import (
    LearnReleaseModel,
    PathLessonModel,
    PathLessonPrerequisiteModel,
    PathVersionModel,
    UnitModel,
    UserModel,
)
from infra.auth.middleware import get_current_user, get_optional_user
from infra.database.session import get_async_session
from learn.runtime.runtime_models import LearningInstanceModel
from learn.runtime.topic_service import LessonInput, compute_topic_lessons, is_touched

# ---------------------------------------------------------------------------
# Pure state rule
# ---------------------------------------------------------------------------


def _li(pid: str, pos: int, **kw) -> LessonInput:
    return LessonInput(path_lesson_id=pid, position=pos, title=f"L{pos}", **kw)


def _released(pid: str, pos: int, status: str = "active", touched: bool = False, **kw):
    return _li(
        pid,
        pos,
        release_id=f"r-{pid}",
        instance_id=f"i-{pid}",
        instance_status=status,
        touched=touched,
        sections_total=4,
        **kw,
    )


def _states(result: dict) -> list[str]:
    return [row["state"] for row in result["lessons"]]


def test_is_touched_any_signal():
    assert not is_touched(completed_section_ids=[], has_attempt=False, current_section_id=None)
    assert is_touched(completed_section_ids=["s1"], has_attempt=False, current_section_id=None)
    assert is_touched(completed_section_ids=[], has_attempt=True, current_section_id=None)
    assert is_touched(completed_section_ids=None, has_attempt=False, current_section_id="s2")


def test_state_rule_table():
    result = compute_topic_lessons(
        [
            _released("a", 1, status="completed"),
            _released("b", 2, status="completed"),
            _released("c", 3, touched=True, sections_done=2),
            _released("d", 4),
            _li("e", 5),  # no release -> pending
        ]
    )
    assert _states(result) == ["done", "done", "current", "ready", "pending"]
    assert result["lessons_total"] == 5
    assert result["lessons_done"] == 2
    assert result["next_lesson_id"] == "c"
    by_id = {row["path_lesson_id"]: row for row in result["lessons"]}
    assert by_id["a"]["sections_done"] == 4 == by_id["a"]["sections_total"]
    assert by_id["c"]["sections_done"] == 2
    assert by_id["e"]["instance_id"] is None and by_id["e"]["release_id"] is None


def test_ready_untouched_and_pending_denominator():
    result = compute_topic_lessons([_released("a", 1), _released("b", 2), _li("c", 3)])
    assert _states(result) == ["ready", "ready", "pending"]
    assert result["lessons_total"] == 3  # pending counts in the denominator
    assert result["lessons_done"] == 0
    assert result["next_lesson_id"] == "a"


def test_completed_instance_wins_over_touched():
    result = compute_topic_lessons([_released("a", 1, status="completed", touched=True)])
    assert _states(result) == ["done"]
    assert result["next_lesson_id"] is None


def test_only_highest_in_progress_is_current():
    result = compute_topic_lessons(
        [
            _released("a", 1, touched=True, sections_done=1),
            _released("b", 2, touched=True, sections_done=3),
        ]
    )
    assert _states(result) == ["ready", "current"]
    assert result["next_lesson_id"] == "b"


def test_next_is_first_ready_after_last_done():
    result = compute_topic_lessons(
        [
            _released("a", 1),
            _released("b", 2, status="completed"),
            _released("c", 3),
            _released("d", 4),
        ]
    )
    assert _states(result) == ["ready", "done", "ready", "ready"]
    assert result["next_lesson_id"] == "c"


def test_best_after_position_uses_first_unmet_prerequisite_position():
    result = compute_topic_lessons(
        [
            _released("a", 1, status="completed"),
            _released("b", 2),
            _released("c", 3),
            _released("d", 4, prerequisite_ids=("a", "c", "b")),  # b (pos 2) is first unmet
            _li("e", 5, prerequisite_ids=("d",)),
            _released("f", 6, prerequisite_ids=("a",)),  # met -> None
        ]
    )
    by_id = {row["path_lesson_id"]: row for row in result["lessons"]}
    assert by_id["d"]["best_after_position"] == 2
    assert by_id["e"]["best_after_position"] == 4
    assert by_id["f"]["best_after_position"] is None
    assert by_id["a"]["best_after_position"] is None


def test_best_after_ignores_prerequisites_outside_the_topic():
    result = compute_topic_lessons([_released("a", 1, prerequisite_ids=("skipped-or-gone",))])
    assert result["lessons"][0]["best_after_position"] is None


def test_lessons_sorted_by_position():
    result = compute_topic_lessons([_li("b", 2), _li("a", 1)])
    assert [row["position"] for row in result["lessons"]] == [1, 2]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _overrides(db_session_factory):
    state: dict = {"user": TEACHER}

    async def optional_user():
        return state["user"]

    async def required_user():
        if state["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return state["user"]

    async def override_session():
        async with db_session_factory() as session:
            yield session

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = required_user
    app.dependency_overrides[get_optional_user] = optional_user
    app.dependency_overrides[get_async_session] = override_session
    yield state
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
async def _seed(db_session_factory):
    async with db_session_factory() as session:
        session.add(UserModel(id=TEACHER.id, email=TEACHER.email, name=TEACHER.name))
        session.add(UserModel(id=OTHER.id, email=OTHER.email, name=OTHER.name))
        await session.commit()


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _h(token: str) -> dict[str, str]:
    return {"X-Learner-Session": token}


async def _publish(client: AsyncClient, title: str) -> str:
    created = await client.post("/api/v1/builder/lessons", json={"title": title, "document": _doc()})
    assert created.status_code == 201, created.text
    pub = await client.post(f"/api/v1/learn/lessons/{created.json()['id']}/releases", json={})
    assert pub.status_code == 201, pub.text
    return pub.json()["id"]


async def _seed_unit(db_session_factory, n: int = 5) -> dict:
    """Unit with an approved active path of ``n`` lessons; lesson 4 requires lesson 3."""
    async with db_session_factory() as session:
        unit = UnitModel(
            id="unit-1",
            owner_id=TEACHER.id,
            title="Photosynthesis",
            topic="Photosynthesis topic",
            subject="biology",
            grade_level="7",
            destination_objective="Understand how plants make their own food",
            status="approved",
            active_path_version_id="pv-1",
        )
        session.add(unit)
        session.add(
            PathVersionModel(
                id="pv-1",
                unit_id="unit-1",
                version=1,
                status="approved",
                source_plan_json={},
            )
        )
        ids = []
        for pos in range(1, n + 1):
            pl_id = f"pl-{pos}"
            ids.append(pl_id)
            session.add(
                PathLessonModel(
                    id=pl_id,
                    path_version_id="pv-1",
                    concept_id=f"c-{pos}",
                    concept_slug=f"concept-{pos}",
                    title=f"Path lesson {pos}",
                    objective=f"Objective {pos}",
                    objective_hash=f"h{pos}",
                    primary_knowledge_type="concept",
                    position=pos,
                    skipped=False,
                )
            )
        # A skipped lesson must be ignored.
        session.add(
            PathLessonModel(
                id="pl-skip",
                path_version_id="pv-1",
                concept_id="c-skip",
                concept_slug="concept-skip",
                title="Skipped",
                objective="x",
                objective_hash="hs",
                primary_knowledge_type="concept",
                position=n + 1,
                skipped=True,
            )
        )
        session.add(
            PathLessonPrerequisiteModel(path_lesson_id="pl-4", prerequisite_lesson_id="pl-3")
        )
        await session.commit()
    return {"path_lesson_ids": ids}


async def _link(db_session_factory, release_id: str, path_lesson_id: str) -> None:
    async with db_session_factory() as session:
        release = await session.get(LearnReleaseModel, release_id)
        release.path_lesson_id = path_lesson_id
        await session.commit()


async def _setup(client: AsyncClient, state: dict, db_session_factory, linked: int = 4) -> dict:
    """4 linked+assigned lessons (1 pending), plus one unlinked assigned lesson."""
    await _seed_unit(db_session_factory)
    state["user"] = TEACHER
    klass = await client.post("/api/v1/learn/classes", json={"name": "Demo class"})
    assert klass.status_code == 200, klass.text
    release_ids: dict[str, str] = {}
    for pos in range(1, linked + 1):
        rid = await _publish(client, f"Lesson {pos}")
        await _link(db_session_factory, rid, f"pl-{pos}")
        release_ids[f"pl-{pos}"] = rid
    unlinked = await _publish(client, "Manual lesson")
    for rid in [*release_ids.values(), unlinked]:
        res = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": rid,
                "title": "Assigned",
                "class_id": klass.json()["id"],
                "mode": "rolling",
            },
        )
        assert res.status_code == 200, res.text
    state["user"] = None
    return {
        "invite": klass.json()["invite_code"],
        "class_id": klass.json()["id"],
        "release_ids": release_ids,
        "unlinked": unlinked,
    }


async def _join(client: AsyncClient, invite: str, name: str = "Ann") -> dict:
    res = await client.post(
        "/api/v1/learn/classes/join", json={"invite_code": invite, "display_name": name}
    )
    assert res.status_code == 200, res.text
    return res.json()


async def _topics(client: AsyncClient, joined: dict) -> dict:
    res = await client.get(
        f"/api/v1/learn/learners/{joined['learner_id']}/topics", headers=_h(joined["token"])
    )
    assert res.status_code == 200, res.text
    return res.json()


@pytest.mark.asyncio
async def test_four_ready_one_pending_contract(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        joined = await _join(client, ctx["invite"])
        body = await _topics(client, joined)

        assert body["learner_id"] == joined["learner_id"]
        assert body["display_name"] == "Ann"
        async with db_session_factory() as session:
            from learn.runtime.runtime_models import LearnerIdentityModel

            learner = await session.get(LearnerIdentityModel, joined["learner_id"])
            assert body["code"] == learner.invite_code and body["code"]

        assert len(body["topics"]) == 1
        topic = body["topics"][0]
        assert topic["unit_id"] == "unit-1"
        assert topic["title"] == "Photosynthesis"
        assert topic["summary"] == "Understand how plants make their own food"
        assert topic["class_id"] == ctx["class_id"]
        assert topic["lessons_total"] == 5  # skipped lesson ignored
        assert topic["lessons_done"] == 0
        assert [row["state"] for row in topic["lessons"]] == [
            "ready", "ready", "ready", "ready", "pending",
        ]
        assert topic["next_lesson_id"] == "pl-1"
        pending = topic["lessons"][4]
        assert pending["instance_id"] is None and pending["release_id"] is None
        for row in topic["lessons"][:4]:
            assert row["instance_id"] and row["release_id"]
            assert row["sections_total"] == 1 and row["sections_done"] == 0
        # prerequisite pl-3 -> pl-4 not done yet: "Best after Lesson 3", still ready.
        assert topic["lessons"][3]["best_after_position"] == 3
        assert topic["lessons"][3]["state"] == "ready"
        assert topic["lessons"][0]["best_after_position"] is None

        # The unlinked assigned lesson is only under other_lessons.
        assert len(body["other_lessons"]) == 1
        other = body["other_lessons"][0]
        assert other["title"] == "Manual lesson" and other["state"] == "ready"
        topic_instance_ids = {r["instance_id"] for r in topic["lessons"] if r["instance_id"]}
        assert other["instance_id"] not in topic_instance_ids


@pytest.mark.asyncio
async def test_progress_moves_state_and_counts(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        joined = await _join(client, ctx["invite"])
        topic = (await _topics(client, joined))["topics"][0]
        first, third = topic["lessons"][0], topic["lessons"][2]

        done = await client.post(
            f"/api/v1/learn/instances/{first['instance_id']}/sections/complete",
            json={"section_id": "s1"},
            headers=_h(joined["token"]),
        )
        assert done.status_code == 200, done.text
        topic = (await _topics(client, joined))["topics"][0]
        assert topic["lessons"][0]["state"] == "current"
        assert topic["lessons"][0]["sections_done"] == 1
        assert topic["next_lesson_id"] == "pl-1"

        # Mark lesson 1 completed, lesson 3 completed -> lesson 4 no longer "best after".
        async with db_session_factory() as session:
            for iid in (first["instance_id"], third["instance_id"]):
                inst = await session.get(LearningInstanceModel, iid)
                inst.status = "completed"
            await session.commit()
        topic = (await _topics(client, joined))["topics"][0]
        assert [r["state"] for r in topic["lessons"]] == [
            "done", "ready", "done", "ready", "pending",
        ]
        assert topic["lessons_done"] == 2
        assert topic["lessons"][0]["sections_done"] == topic["lessons"][0]["sections_total"] == 1
        assert topic["lessons"][3]["best_after_position"] is None
        assert topic["next_lesson_id"] == "pl-4"


@pytest.mark.asyncio
async def test_late_published_lesson_appears_in_place(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        joined = await _join(client, ctx["invite"])
        topic = (await _topics(client, joined))["topics"][0]
        assert topic["lessons"][4]["state"] == "pending"

        _overrides["user"] = TEACHER
        rid = await _publish(client, "Lesson 5")
        await _link(db_session_factory, rid, "pl-5")
        res = await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": rid,
                "title": "Lesson 5",
                "class_id": ctx["class_id"],
                "mode": "rolling",
            },
        )
        assert res.status_code == 200, res.text
        _overrides["user"] = None

        topic = (await _topics(client, joined))["topics"][0]
        assert topic["lessons"][4]["state"] == "ready"
        assert topic["lessons"][4]["instance_id"]


@pytest.mark.asyncio
async def test_other_class_release_not_counted(_overrides, db_session_factory):
    """A linked release assigned only to a class the learner is not in does not show."""
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory, linked=2)
        _overrides["user"] = TEACHER
        klass2 = await client.post("/api/v1/learn/classes", json={"name": "Other class"})
        rid = await _publish(client, "Lesson 3")
        await _link(db_session_factory, rid, "pl-3")
        await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": rid,
                "title": "Lesson 3",
                "class_id": klass2.json()["id"],
                "mode": "rolling",
            },
        )
        _overrides["user"] = None
        joined = await _join(client, ctx["invite"])
        topic = (await _topics(client, joined))["topics"][0]
        assert [r["state"] for r in topic["lessons"]] == [
            "ready", "ready", "pending", "pending", "pending",
        ]


@pytest.mark.asyncio
async def test_latest_published_release_per_path_lesson(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory, linked=1)
        _overrides["user"] = TEACHER
        newer = await _publish(client, "Lesson 1 v2")
        await _link(db_session_factory, newer, "pl-1")
        async with db_session_factory() as session:
            old = await session.get(LearnReleaseModel, ctx["release_ids"]["pl-1"])
            new = await session.get(LearnReleaseModel, newer)
            old.published_at = datetime(2026, 1, 1, tzinfo=UTC).replace(tzinfo=None)
            new.published_at = datetime(2026, 2, 1, tzinfo=UTC).replace(tzinfo=None)
            await session.commit()
        await client.post(
            "/api/v1/learn/assignments",
            json={
                "learn_release_id": newer,
                "title": "v2",
                "class_id": ctx["class_id"],
                "mode": "rolling",
            },
        )
        _overrides["user"] = None
        joined = await _join(client, ctx["invite"])
        body = await _topics(client, joined)
        assert body["topics"][0]["lessons"][0]["release_id"] == newer
        # The superseded release's instance is not listed as an "other" lesson.
        titles = [o["title"] for o in body["other_lessons"]]
        assert "Lesson 1" not in titles


@pytest.mark.asyncio
async def test_learner_without_classes_gets_empty_topics(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        _overrides["user"] = TEACHER
        learner = await client.post("/api/v1/learn/learners", json={"display_name": "Loner"})
        assert learner.status_code in (200, 201), learner.text
        lid = learner.json().get("id") or learner.json().get("learner_id")
        _overrides["user"] = TEACHER
        res = await client.get(f"/api/v1/learn/learners/{lid}/topics")
        assert res.status_code == 200
        assert res.json()["topics"] == [] and res.json()["other_lessons"] == []
        assert ctx  # setup used


@pytest.mark.asyncio
async def test_topics_auth(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        ann = await _join(client, ctx["invite"], "Ann")
        bob = await _join(client, ctx["invite"], "Bob")
        url = f"/api/v1/learn/learners/{ann['learner_id']}/topics"
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=_h(bob["token"]))).status_code in (401, 403, 404)
        assert (await client.get(url, headers=_h(ann["token"]))).status_code == 200
        missing = await client.get("/api/v1/learn/learners/nope/topics", headers=_h(ann["token"]))
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_home_buckets_do_not_duplicate(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        joined = await _join(client, ctx["invite"])
        home = await client.get(
            f"/api/v1/learn/learners/{joined['learner_id']}/home", headers=_h(joined["token"])
        )
        assert home.status_code == 200, home.text
        buckets = home.json()["buckets"]
        due = {i["id"] for i in buckets["due_soon"]}
        assert len(due) == 5  # 4 topic lessons + 1 unlinked, all assigned
        assert due.isdisjoint({i["id"] for i in buckets["in_progress"]})
        assert due.isdisjoint({i["id"] for i in buckets["completed"]})


@pytest.mark.asyncio
async def test_home_in_progress_keeps_unassigned_active_instances(_overrides, db_session_factory):
    async with _client() as client:
        ctx = await _setup(client, _overrides, db_session_factory)
        joined = await _join(client, ctx["invite"])
        async with db_session_factory() as session:
            inst = (
                await session.execute(
                    select(LearningInstanceModel).where(
                        LearningInstanceModel.learner_id == joined["learner_id"]
                    )
                )
            ).scalars().first()
            inst.assignment_id = None  # self-started, not tied to an assignment
            await session.commit()
            iid = inst.id
        home = await client.get(
            f"/api/v1/learn/learners/{joined['learner_id']}/home", headers=_h(joined["token"])
        )
        buckets = home.json()["buckets"]
        assert iid in {i["id"] for i in buckets["in_progress"]}
        assert iid not in {i["id"] for i in buckets["due_soon"]}
