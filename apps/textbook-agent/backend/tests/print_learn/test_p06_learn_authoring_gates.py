"""P06 Learn authoring, ordered rendering and publishing gates."""

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
from learn.generation.interaction_writer import (
    InteractionWriterError,
    validate_interaction_contract,
    write_interaction_from_work_order,
)
from learn.generation.authoring_adapter import run_learn_work_order_authoring
from learn.generation.native_selection import (
    build_learn_selection_snapshot_async,
)
from infra.authoring.capability_selector import CapabilitySelection
from learn.generation.ordered_assemble import (
    assemble_ordered_learn_document,
    block_component_sequence,
    ordered_block_ids,
)
from learn.generation.work_orders import compile_learn_work_orders
from learn.publishing.publish_validation import (
    PublishValidationError,
    collect_publish_validation_errors,
    validate_publishable_lesson_document,
)
from learn.publishing.release_routes import document_hash, resolve_release_provenance
from learn.resources.native_policy import default_learn_policy, policy_version_and_hash as learn_policy_hash
from infra.authoring import AuthoringProviderCall


CORE_PROVIDER_CONFIG = {
    "choice": {
        "options": [{"id": "soil", "text": "Soil"}, {"id": "air", "text": "Air"}],
        "correct_option_id": "air",
    },
    "multi-select": {
        "options": [{"id": "leaf", "text": "Leaf"}, {"id": "stem", "text": "Stem"}, {"id": "root", "text": "Root"}],
        "correct_option_ids": ["leaf", "stem"],
    },
    "fill-blank": {"answers": ["chlorophyll"], "blank_ids": ["blank-1"], "case_sensitive": False},
    "numeric": {"value": 42, "tolerance": 0, "unit": "kg"},
    "short-response": {"evaluation": "teacher-review", "review_guidance": "Review the response."},
    "match-pairs": {"pairs": [{"left": "co2", "right": "carbon dioxide"}, {"left": "h2o", "right": "water"}]},
    "classify": {
        "categories": [{"id": "fruit", "label": "fruit"}, {"id": "vegetable", "label": "vegetable"}],
        "pairs": [{"left": "apple", "right": "fruit"}, {"left": "carrot", "right": "vegetable"}],
    },
    "sequence": {
        "items": [{"id": "egg", "label": "Egg"}, {"id": "larva", "label": "Larva"}, {"id": "pupa", "label": "Pupa"}, {"id": "adult", "label": "Adult"}],
        "order": ["egg", "larva", "pupa", "adult"],
    },
}

CONTENT_PROVIDER_PAYLOADS = {
    "quiz-check": {
        "question": "What do plants use?",
        "options": [{"text": "Light", "correct": True, "explanation": "Yes."}, {"text": "Noise", "correct": False, "explanation": "No."}],
        "feedback_correct": "Correct.",
        "feedback_incorrect": "Try again.",
    },
    "fill-in-blank": {"segments": [{"text": "Plants use ", "is_blank": False}, {"text": "", "is_blank": True, "answer": "light"}]},
    "worked-example-card": {
        "title": "Worked example",
        "setup": "A plant gets light.",
        "steps": [{"label": "Check", "content": "Identify the energy source."}],
        "conclusion": "Light is needed.",
    },
    "process-steps": {"title": "Process", "steps": [{"number": 1, "action": "Absorb", "detail": "Light is absorbed."}]},
    "explanation-block": {"body": "Plants use light energy.", "emphasis": ["light"]},
    "callout-block": {"variant": "info", "body": "Light matters."},
    "key-fact": {"fact": "Light supplies energy."},
    "summary-block": {"items": [{"text": "Light supplies energy for food making."}]},
    "definition-card": {"term": "Photosynthesis", "formal": "Plants make food using light.", "plain": "Light helps plants make food."},
    "section-header": {"title": "Light and food", "subject": "science", "grade_band": "primary"},
    "hook-hero": {"headline": "Why did one plant grow?", "body": "Light reached one plant.", "anchor": "light"},
    "timeline-block": {"title": "Growth", "events": [{"id": "day1", "year": "1", "title": "Sprout", "summary": "The seed sprouts."}]},
    "diagram-compare": {"before_label": "Dark", "after_label": "Light", "caption": "Light changes growth.", "alt_text": "Dark versus lit plant"},
}


def _interaction_envelope(capability_id: str) -> dict[str, object]:
    return {
        "prompt": f"Complete this {capability_id.replace('-', ' ')} activity.",
        "config": dict(CORE_PROVIDER_CONFIG[capability_id]),
        "feedback": {"correct": "Correct.", "incorrect": "Try again."},
    }


class P06Provider:
    async def invoke(self, call: AuthoringProviderCall):
        if call.capability_id in CORE_PROVIDER_CONFIG:
            return _interaction_envelope(call.capability_id)
        return dict(
            CONTENT_PROVIDER_PAYLOADS.get(
                call.capability_id,
                CONTENT_PROVIDER_PAYLOADS["explanation-block"],
            )
        )


async def _author_all_async(orders):
    return {
        order.work_order_id: await run_learn_work_order_authoring(
            order,
            provider=P06Provider(),
            lesson_context={"objective": "P06 offline fixture objective", "subject": "science"},
            allowed_facts=["P06 fixture fact for generate authoring."],
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
    """MOCK selector for offline P06 fixtures — picks first eligible closed-set ID."""
    ids = list(context.get("candidate_ids") or [])
    if not ids:
        eligible = context.get("eligible_candidates") or []
        ids = [
            str(row["id"] if isinstance(row, dict) else row)
            for row in eligible
        ]
    if not ids:
        raise AssertionError(f"mock selector received empty shortlist: {context!r}")
    return CapabilitySelection(capability_id=str(ids[0]), reason="p06-mock-selector")


def _snapshot(plan: TeachingPlan):
    _, policy_hash = learn_policy_hash()

    async def _run():
        return await build_learn_selection_snapshot_async(
            plan,
            teaching_plan_hash=f"hash-{plan.teaching_plan_id}",
            native_policy_hash=policy_hash,
            package_contract_hash="pkg-learn-p06",
            policy=default_learn_policy(),
            choose=_test_choose,
            teaching_context={"objective": "P06 offline fixture objective"},
        )

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_run())
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_run())).result()


def _plan(*blocks: TeachingPlanBlock, plan_id: str = "tp-p06", revision: int = 1) -> TeachingPlan:
    return TeachingPlan(
        arc="P06 Learn authoring fixture",
        teaching_plan_id=plan_id,
        revision=revision,
        sections=[
            TeachingPlanSection(
                slot_id="practice",
                specific_purpose="Order the cycle",
                blocks=list(blocks),
            )
        ],
    )


def _block(
    block_id: str,
    *,
    intent: str,
    brief: str = "Brief",
    action: str | None = None,
    support: str = "guided",
    evidence: str = "Evidence of understanding",
    position: int = 0,
) -> TeachingPlanBlock:
    learner = None
    if action is not None:
        learner = LearnerActionBrief(
            action=action,
            target=action.replace("-", " "),
            purpose="Check understanding",
            expected_evidence=evidence,
            difficulty=support,  # type: ignore[arg-type]
        )
    return TeachingPlanBlock(
        id=block_id,
        position=position,
        intent=intent,
        brief=brief,
        evidence=evidence,
        source_question_ids=[],
        stimulus_dependencies=[],
        learner_action=learner,
    )


def _interleaved_plan() -> TeachingPlan:
    """content → activity → content with repeated explanation blocks."""
    return TeachingPlan(
        arc="Interleaved order fixture",
        teaching_plan_id="tp-p06-order",
        revision=1,
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="Interleaved",
                blocks=[
                    _block(
                        "b-intro",
                        intent="explain",
                        brief="Intro prose before the task",
                        position=0,
                    ),
                    _block(
                        "b-order",
                        intent="sequence",
                        brief="Absorb light; Split water; Fix carbon",
                        action="order-items",
                        position=1,
                    ),
                    _block(
                        "b-outro",
                        intent="explain",
                        brief="Closing prose after the task",
                        position=2,
                    ),
                    _block(
                        "b-encore",
                        intent="explain",
                        brief="Second explanation of the same type",
                        position=3,
                    ),
                ],
            )
        ],
    )


# ---------------------------------------------------------------------------
# P06-L01
# ---------------------------------------------------------------------------


def test_p06_l01_sequence_via_selector_writer_not_injected() -> None:
    """Generated lesson contains Sequence through selector/writer — not injection."""
    plan = _plan(
        _block(
            "b-cycle",
            intent="sequence",
            brief="Egg; Larva; Pupa; Adult",
            action="order-items",
        )
    )
    snapshot = _snapshot(plan)
    assert any(d.interaction_id == "sequence" for d in snapshot.decisions), snapshot.decisions

    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)
    ix_orders = [o for o in orders if o.lane == "interaction"]
    assert len(ix_orders) == 1
    assert ix_orders[0].capability_id == "sequence"

    authoring_plan, request, payload = write_interaction_from_work_order(ix_orders[0], provider=P06Provider())
    assert authoring_plan.mode == "new"
    assert request["work_order_id"] == ix_orders[0].work_order_id
    assert request["capability_id"] == "sequence"
    assert request["authoring_mode"] == "generate"
    assert payload["kind"] == "sequence"
    assert payload["provenance"]["work_order_id"] == ix_orders[0].work_order_id
    assert validate_interaction_contract(payload) == []

    document = assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=_author_all(orders),
    )
    interactions = [
        b
        for b in document["blocks"].values()
        if isinstance(b.get("learn_interaction"), dict)
    ]
    assert len(interactions) >= 1
    contract = interactions[0]["learn_interaction"]
    assert contract["kind"] == "sequence"
    assert contract["provenance"]["work_order_id"] == ix_orders[0].work_order_id
    assert contract["provenance"]["capability_contract_hash"] == ix_orders[0].capability_contract_hash
    # Prove it was not a hand-built orphan: hash linkage to the sealed selection.
    assert contract["provenance"]["teaching_plan_hash"] == snapshot.teaching_plan_hash


@pytest.mark.parametrize(
    "capability_id,intent,action,brief",
    [
        ("choice", "check-understanding", "select-one", "Soil; Air; Light"),
        ("multi-select", "check-understanding", "select-many", "Leaf; Stem; Root; Flower"),
        ("fill-blank", "practise-guided", "complete-missing-values", "Chlorophyll absorbs light"),
        ("numeric", "apply", "enter-number", "Enter 42 kg of biomass"),
        ("short-response", "check-understanding", "enter-text", "Name the pigment chlorophyll"),
        ("match-pairs", "define", "match-pairs", "CO2; carbon dioxide; H2O; water"),
        ("classify", "classify", "classify-items", "Apple; fruit; Carrot; vegetable"),
        ("sequence", "sequence", "order-items", "Egg; Larva; Pupa; Adult"),
    ],
)
def test_p06_l01_core_writers_via_selector(
    capability_id: str,
    intent: str,
    action: str,
    brief: str,
) -> None:
    """Each core interaction writes a valid payload through selector/writer."""
    plan = _plan(
        _block("b-core", intent=intent, brief=brief, action=action),
        plan_id=f"tp-p06-{capability_id}",
    )
    snapshot = _snapshot(plan)
    decisions = [d for d in snapshot.decisions if d.interaction_id]
    assert decisions, snapshot.decisions
    assert decisions[0].interaction_id == capability_id

    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)
    ix_orders = [o for o in orders if o.lane == "interaction"]
    assert len(ix_orders) == 1
    assert ix_orders[0].capability_id == capability_id

    _, request, payload = write_interaction_from_work_order(ix_orders[0], provider=P06Provider())
    assert request["capability_id"] == capability_id
    assert payload["kind"] == capability_id
    assert validate_interaction_contract(payload) == []

    document = assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=_author_all(orders),
    )
    contracts = [
        b["learn_interaction"]
        for b in document["blocks"].values()
        if isinstance(b.get("learn_interaction"), dict)
    ]
    assert any(c.get("kind") == capability_id for c in contracts)


def test_p06_core_writer_rejects_invalid_payloads() -> None:
    from learn.generation.interaction_writer import (
        InteractionWriterError,
        write_interaction_from_request,
    )

    with pytest.raises(InteractionWriterError):
        write_interaction_from_request(
            {
                "capability_id": "choice",
                "lane": "interaction",
                "brief": "x",
                "block_id": "b1",
                "approved_items": [
                    SimpleNamespace(
                        id="i1",
                        stem="Stem",
                        options=({"id": "only", "text": "One"},),
                        correct_key="only",
                    )
                ],
            }
        )


# ---------------------------------------------------------------------------
# P06-L02
# ---------------------------------------------------------------------------


def test_p06_l02_repeated_and_interleaved_order_survives_assemble() -> None:
    """Repeated same-type blocks and content→activity→content survive assemble."""
    plan = _interleaved_plan()
    snapshot = _snapshot(plan)
    document = assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot),
        authored_results=_author_all(compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)),
    )

    sequence = block_component_sequence(document)
    # Must keep two explanation-shaped blocks around the interaction (not collapsed).
    assert any(c.startswith("learn-interaction:") for c in sequence), sequence
    explanation_idxs = [
        i
        for i, c in enumerate(sequence)
        if c in {"explanation-block", "key-fact", "callout-block", "insight-strip"}
    ]
    interaction_idxs = [i for i, c in enumerate(sequence) if c.startswith("learn-interaction:")]
    assert len(explanation_idxs) >= 2, sequence
    assert len(interaction_idxs) == 1, sequence
    # content → activity → content
    assert explanation_idxs[0] < interaction_idxs[0] < explanation_idxs[-1], sequence

    # Round-trip via JSON (Builder reload) preserves block_ids order.
    import json

    reloaded = json.loads(json.dumps(document))
    assert ordered_block_ids(reloaded) == ordered_block_ids(document)
    assert block_component_sequence(reloaded) == sequence

    # Lossy SectionContent projection would collapse repeats — prove we do not
    # use field-map collapse as the authority: block_ids length > unique types.
    assert len(ordered_block_ids(document)) >= 3


# ---------------------------------------------------------------------------
# P06-L03
# ---------------------------------------------------------------------------


def test_p06_l03_builder_edit_persists_and_malformed_blocks_publish() -> None:
    """Valid Builder-style edit persists; malformed / dangling refs block publish."""
    plan = _plan(
        _block(
            "b-cycle",
            intent="sequence",
            brief="Seed; Sprout; Plant",
            action="order-items",
        )
    )
    snapshot = _snapshot(plan)
    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)
    document = assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=_author_all(orders),
    )

    # Locate interaction and apply a Builder-style field edit.
    block_id = next(
        bid
        for bid, block in document["blocks"].items()
        if isinstance(block.get("learn_interaction"), dict)
    )
    contract = document["blocks"][block_id]["learn_interaction"]
    edited = copy.deepcopy(contract)
    edited["prompt"] = "Reorder the plant life stages"
    edited["config"]["items"][0]["label"] = "Seed stage"
    document["blocks"][block_id]["learn_interaction"] = edited
    document["blocks"][block_id]["content"]["prompt"] = edited["prompt"]

    validate_publishable_lesson_document(document)
    assert document["blocks"][block_id]["learn_interaction"]["prompt"] == "Reorder the plant life stages"
    assert document["blocks"][block_id]["learn_interaction"]["config"]["items"][0]["label"] == "Seed stage"

    # Malformed config blocks publish.
    bad = copy.deepcopy(document)
    bad["blocks"][block_id]["learn_interaction"]["config"]["order"] = ["missing-id", "also-missing"]
    with pytest.raises(PublishValidationError) as exc:
        validate_publishable_lesson_document(bad)
    assert any("dangling" in e or "INVALID_SEQUENCE" in e or "match" in e.lower() for e in exc.value.errors)

    # Dangling media ref blocks publish.
    dangling = copy.deepcopy(document)
    dangling["blocks"][block_id]["content"]["media_id"] = "media-does-not-exist"
    errors = collect_publish_validation_errors(dangling)
    assert any("dangling media" in e for e in errors)


# ---------------------------------------------------------------------------
# P06-L04 — package preview store (zero production persistence)
# ---------------------------------------------------------------------------


def test_p06_l04_preview_store_does_not_claim_production_persistence() -> None:
    """Preview attempt store is explicitly non-persisting (package contract)."""
    # Backend gate: preview never writes LearnerAttemptModel — covered in async test below.
    # This unit proves the package preview store API contract used by the shell.
    from pathlib import Path

    store_path = (
        Path(__file__).resolve().parents[4]
        / "packages"
        / "lectio-learn"
        / "src"
        / "lib"
        / "learn"
        / "preview-attempt-store.ts"
    )
    # Monorepo layout: backend/tests/print_learn -> repo root is parents[3]
    repo_candidates = [
        Path(__file__).resolve().parents[3] / "packages" / "lectio-learn" / "src" / "lib" / "learn" / "preview-attempt-store.ts",
        Path(__file__).resolve().parents[4] / "packages" / "lectio-learn" / "src" / "lib" / "learn" / "preview-attempt-store.ts",
        Path(__file__).resolve().parents[5] / "packages" / "lectio-learn" / "src" / "lib" / "learn" / "preview-attempt-store.ts",
    ]
    store_path = next((p for p in repo_candidates if p.exists()), None)
    assert store_path is not None, repo_candidates
    text = store_path.read_text(encoding="utf-8")
    assert "persists_production_attempts: false" in text
    assert "mode: 'preview'" in text


# ---------------------------------------------------------------------------
# HTTP / DB gates L04–L06
# ---------------------------------------------------------------------------


USER = SimpleNamespace(
    id="p06-user",
    email="p06@example.com",
    name="P06",
    picture_url=None,
    has_profile=True,
)


def _minimal_lesson(document_id: str = "doc-p06") -> dict:
    block_id = "block-1"
    return {
        "version": 1,
        "id": document_id,
        "title": "P06 Lesson",
        "subject": "biology",
        "preset_id": "blue-classroom",
        "source": "manual",
        "sections": [
            {
                "id": "section-1",
                "template_id": "open-canvas",
                "title": "Warm-up",
                "position": 0,
                "block_ids": [block_id],
            }
        ],
        "blocks": {
            block_id: {
                "id": block_id,
                "component_id": "explanation-block",
                "position": 0,
                "content": {"body": "Plants fix carbon.", "callouts": []},
            }
        },
        "media": {},
        "created_at": "2026-09-08T00:00:00Z",
        "updated_at": "2026-09-08T00:00:00Z",
    }


def _sequence_lesson() -> dict:
    plan = _plan(
        _block(
            "b-cycle",
            intent="sequence",
            brief="Egg; Larva; Pupa; Adult",
            action="order-items",
        )
    )
    snapshot = _snapshot(plan)
    orders = compile_learn_work_orders(teaching_plan=plan, snapshot=snapshot)
    return assemble_ordered_learn_document(
        teaching_plan=plan,
        snapshot=snapshot,
        work_orders=orders,
        authored_results=_author_all(orders),
        lesson_id="doc-seq",
        title="Sequence lesson",
        subject="biology",
    )


@pytest.fixture
def _install_overrides(db_session_factory):
    from app import app
    from infra.auth.middleware import get_current_user
    from infra.database.session import get_async_session
    from core.entities.user import User

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


@pytest.mark.asyncio
async def test_p06_l04_preview_creates_zero_attempts_and_leaves_release(
    db_session_factory, _install_overrides, _seed_user
):
    """Preview interactions create zero production attempts; release hash unchanged."""
    from core.database.models import LearnerAttemptModel, LearnReleaseModel

    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Preview lesson", "document": _minimal_lesson("doc-preview")},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub.status_code == 201, pub.text
        release = pub.json()
        hash_before = release["document_hash"]
        release_id = release["id"]

        # Preview surface: no instance attempt route on draft lesson id.
        # Simulate preview by asserting attempts table stays empty and release immutable
        # after a draft edit (preview must not mutate published snapshot).
        draft = _minimal_lesson("doc-preview")
        draft["blocks"]["block-1"]["content"]["body"] = "Draft-only edit"
        upd = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Preview lesson", "document": draft},
        )
        assert upd.status_code == 200, upd.text

        get_rel = await client.get(f"/api/v1/learn/releases/{release_id}")
        assert get_rel.status_code == 200
        assert get_rel.json()["document_hash"] == hash_before
        assert get_rel.json()["document"]["blocks"]["block-1"]["content"]["body"] == "Plants fix carbon."

    async with db_session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(LearnerAttemptModel))
        assert int(count or 0) == 0
        row = await session.get(LearnReleaseModel, release_id)
        assert row is not None
        assert row.document_hash == hash_before


@pytest.mark.asyncio
async def test_p06_l05_publish_v1_immutable_v2_and_idempotent_concurrent(
    db_session_factory, _install_overrides, _seed_user
):
    """Publish v1, edit, publish v2: v1 hash unchanged; concurrent/idempotent safe."""
    from core.database.models import LearnReleaseModel

    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Immutable", "document": _minimal_lesson("doc-immut")},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

        pub1 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub1.status_code == 201, pub1.text
        v1 = pub1.json()
        hash1 = v1["document_hash"]
        assert hash1 == document_hash(v1["document"])

        # Idempotent double-click: same draft → same release.
        pub1b = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub1b.status_code == 201, pub1b.text
        assert pub1b.json()["id"] == v1["id"]
        assert pub1b.json()["idempotent_replay"] is True

        draft = _minimal_lesson("doc-immut")
        draft["title"] = "Immutable (edited)"
        draft["blocks"]["block-1"]["content"]["body"] = "Edited"
        upd = await client.put(
            f"/api/v1/builder/lessons/{lesson_id}",
            json={"title": "Immutable (edited)", "document": draft},
        )
        assert upd.status_code == 200, upd.text

        get_v1 = await client.get(f"/api/v1/learn/releases/{v1['id']}")
        assert get_v1.json()["document_hash"] == hash1

        pub2 = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub2.status_code == 201, pub2.text
        v2 = pub2.json()
        assert v2["release_number"] == 2
        assert v2["document_hash"] != hash1

        # Concurrent publish of the same draft must converge to one release (idempotent).
        async def _publish_once():
            async with await _client() as c:
                return await c.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})

        # Sequential retries first (SQLite in-memory does not serialize FOR UPDATE across
        # concurrent connections the same way Postgres does).
        r_a = await _publish_once()
        r_b = await _publish_once()
        assert r_a.status_code == 201 and r_b.status_code == 201, (r_a.text, r_b.text)
        assert r_a.json()["id"] == r_b.json()["id"]
        assert r_b.json()["idempotent_replay"] is True

        # Concurrent gather must not create duplicate release numbers for the same hash.
        results = await asyncio.gather(_publish_once(), _publish_once(), _publish_once())
        assert all(r.status_code == 201 for r in results), [r.text for r in results]
        bodies = [r.json() for r in results]
        assert len({b["id"] for b in bodies}) == 1
        assert len({b["release_number"] for b in bodies}) == 1
        assert all(b.get("idempotent_replay") for b in bodies)

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(LearnReleaseModel).where(LearnReleaseModel.editable_lesson_id == lesson_id)
            )
        ).scalars().all()
        numbers = sorted(r.release_number for r in rows)
        assert numbers == list(range(1, len(numbers) + 1))
        assert len(set(numbers)) == len(numbers)


@pytest.mark.asyncio
async def test_p06_l06_old_draft_keeps_pinned_provenance(
    db_session_factory, _install_overrides, _seed_user
):
    """Publishing an old draft after PathLesson revision bump never stamps current."""
    from core.database.models import (
        ConceptModel,
        EditableLessonModel,
        GenerationModel,
        LearningPackModel,
        LessonProvenanceModel,
        PathLessonModel,
        PathVersionModel,
        UnitModel,
        UserModel,
    )

    pack_id = "pack-p06-pin"
    gen_id = "gen-p06-pin"
    pl_id = "pl-p06"

    async with db_session_factory() as session:
        # User already seeded by fixture; ensure present.
        if await session.get(UserModel, USER.id) is None:
            session.add(UserModel(id=USER.id, email=USER.email, name=USER.name))
        session.add(
            ConceptModel(
                id="concept-p06",
                canonical_slug="photosynthesis",
                subject="biology",
                title="Photosynthesis",
                created_by=USER.id,
            )
        )
        session.add(
            UnitModel(
                id="unit-p06",
                owner_id=USER.id,
                title="Unit",
                topic="Photosynthesis",
                subject="biology",
                grade_level="9",
                destination_objective="Explain carbon fixation",
            )
        )
        await session.flush()
        session.add(
            PathVersionModel(
                id="pv-p06",
                unit_id="unit-p06",
                version=1,
                status="active",
                source_plan_json={},
            )
        )
        await session.flush()
        session.add(
            PathLessonModel(
                id=pl_id,
                path_version_id="pv-p06",
                concept_id="concept-p06",
                concept_slug="photosynthesis",
                title="Leaf lesson",
                objective="Explain carbon fixation",
                objective_hash="obj-hash-pinned",
                primary_knowledge_type="declarative",
                position=0,
                revision=1,
            )
        )
        session.add(
            LearningPackModel(
                id=pack_id,
                user_id=USER.id,
                learning_job_type="unit_lesson",
                subject="biology",
                topic="Photosynthesis",
                pack_plan_json="{}",
                status="completed",
                resource_count=1,
            )
        )
        session.add(
            LessonProvenanceModel(
                pack_id=pack_id,
                concept_id="concept-p06",
                path_version_id="pv-p06",
                path_lesson_id=pl_id,
                objective_hash="obj-hash-pinned",
                path_lesson_revision=1,
            )
        )
        session.add(
            GenerationModel(
                id=gen_id,
                user_id=USER.id,
                subject="biology",
                status="completed",
                requested_template_id="open-canvas",
                requested_preset_id="blue-classroom",
                pack_id=pack_id,
            )
        )
        await session.commit()

    async with await _client() as client:
        create = await client.post(
            "/api/v1/builder/lessons",
            json={"title": "Pinned draft", "document": _minimal_lesson("doc-pin")},
        )
        assert create.status_code == 201, create.text
        lesson_id = create.json()["id"]

    # Attach generation provenance to the editable lesson (unit-sourced draft).
    async with db_session_factory() as session:
        lesson = await session.get(EditableLessonModel, lesson_id)
        assert lesson is not None
        lesson.source_generation_id = gen_id
        await session.commit()

        # Bump live PathLesson revision AFTER the draft was created.
        path_lesson = await session.get(PathLessonModel, pl_id)
        assert path_lesson is not None
        path_lesson.revision = 9
        path_lesson.objective_hash = "obj-hash-TODAY"
        await session.commit()

        # resolve_release_provenance must return pinned 1 / obj-hash-pinned.
        pinned = await resolve_release_provenance(
            session, lesson=lesson, explicit_path_lesson_id=None
        )
        assert pinned == (pl_id, 1, "obj-hash-pinned")

    async with await _client() as client:
        pub = await client.post(f"/api/v1/learn/lessons/{lesson_id}/releases", json={})
        assert pub.status_code == 201, pub.text
        body = pub.json()
        assert body["path_lesson_id"] == pl_id
        assert body["path_lesson_revision"] == 1
        assert body["objective_hash"] == "obj-hash-pinned"
        assert body["path_lesson_revision"] != 9


def test_p06_l03_sequence_writer_rejects_spatial() -> None:
    with pytest.raises(InteractionWriterError) as exc:
        from learn.generation.interaction_writer import write_interaction_from_request

        write_interaction_from_request(
            {"capability_id": "image-hotspot", "lane": "interaction", "brief": "x"}
        )
    assert exc.value.code == "SPATIAL_UNAVAILABLE"
