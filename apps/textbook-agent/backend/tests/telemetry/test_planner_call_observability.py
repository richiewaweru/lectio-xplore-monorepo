"""Planner-side LLM calls (semantic reviewer, backbone writer) must be attributable.

`TelemetryMonitor` only persists an `llm_calls` row when it can resolve a user,
which for these callers means the event must carry the real generation id.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from tests.planning.test_teaching_plan_semantic_review import (
    _draft,
    _make_snapshot,
    _packet,
)

from curriculum import agents
from curriculum.teaching_plan import semantic_review
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import materialize_teaching_plan
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticReviewDraft,
    TeachingPlanSemanticReviewResult,
    review_teaching_plan_draft,
)
from infra.events import LLMCallSucceededEvent
from infra.telemetry.service import TelemetryMonitor

GENERATION_ID = "gen-123"
USER_ID = "user-1"


@pytest.mark.asyncio
async def test_run_structured_forwards_generation_id_to_run_llm(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run_llm(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(output=TeachingPlanSemanticReviewDraft(reviewed=True, findings=[]))

    monkeypatch.setattr(
        agents,
        "prepare_structured_agent",
        lambda **_: (object(), TeachingPlanSemanticReviewDraft, None, object(), None),
    )
    monkeypatch.setattr(agents, "Agent", lambda **_: object())
    monkeypatch.setattr(agents, "run_llm", _fake_run_llm)

    await agents._run_structured(
        node="teaching_plan_semantic_reviewer",
        caller="c",
        output_type=TeachingPlanSemanticReviewDraft,
        system_prompt="s",
        user_payload={},
        trace_id="t",
        generation_id=GENERATION_ID,
    )
    assert captured["generation_id"] == GENERATION_ID

    await agents._run_structured(
        node="teaching_plan_semantic_reviewer",
        caller="c",
        output_type=TeachingPlanSemanticReviewDraft,
        system_prompt="s",
        user_payload={},
        trace_id="t",
    )
    assert captured["generation_id"] is None


@pytest.mark.asyncio
async def test_review_teaching_plan_draft_forwards_generation_id(monkeypatch) -> None:
    draft = _draft()
    plan = materialize_teaching_plan(draft, slot_ids=["orient", "explain"])
    seen: list[dict[str, Any]] = []

    async def _fake_structured(**kwargs):
        seen.append(kwargs)
        return TeachingPlanSemanticReviewDraft(reviewed=True, findings=[])

    monkeypatch.setattr(semantic_review, "_run_structured", _fake_structured)

    await review_teaching_plan_draft(
        draft=draft,
        plan=plan,
        lesson_context={},
        trace_id="t",
        generation_id=GENERATION_ID,
    )
    assert seen[0]["generation_id"] == GENERATION_ID


class _Repo:
    def __init__(self) -> None:
        self.saved: list[dict[str, Any]] = []

    async def save_call(self, **kwargs) -> None:
        self.saved.append(kwargs)


@pytest.mark.asyncio
async def test_monitor_persists_backbone_and_reviewer_calls_by_generation(monkeypatch) -> None:
    """Rows are written when the event carries a real generation id.

    The backbone path already does (``run.source_artifact_id`` is the
    GenerationModel id, and its trace ids are ``backbone:...`` with no
    registration), so user resolution falls through to the generation lookup.
    """
    repo = _Repo()
    monitor = TelemetryMonitor()

    async def _factory():
        return repo

    monitor.configure(llm_call_repository_factory=_factory)

    async def _user_for_generation(generation_id: str):
        return USER_ID if generation_id == GENERATION_ID else None

    monkeypatch.setattr(monitor, "_user_id_for_generation", _user_for_generation)

    def _event(trace_id: str, caller: str, node: str, generation_id: str | None):
        return LLMCallSucceededEvent(
            trace_id=trace_id,
            generation_id=generation_id,
            caller=caller,
            slot="standard",
            node=node,
            attempt=2,
            latency_ms=1234.0,
            tokens_in=10,
            tokens_out=5,
        ).model_dump(mode="json")

    await monitor._handle_event(
        _event(f"backbone:{GENERATION_ID[:12]}:abcd1234:attempt2", "v3_backbone_writer", "bb", GENERATION_ID)
    )
    await monitor._handle_event(
        _event("rand:semantic-review:attempt1", "teaching_plan_semantic_reviewer", "rev", GENERATION_ID)
    )
    # Without a generation id (the old reviewer behaviour) nothing is persisted.
    await monitor._handle_event(
        _event("rand2:semantic-review:attempt1", "teaching_plan_semantic_reviewer", "rev", None)
    )

    assert [(r["caller"], r["node"], r["attempt"], r["generation_id"], r["user_id"]) for r in repo.saved] == [
        ("v3_backbone_writer", "bb", 2, GENERATION_ID, USER_ID),
        ("teaching_plan_semantic_reviewer", "rev", 2, GENERATION_ID, USER_ID),
    ]
    assert repo.saved[0]["latency_ms"] == 1234.0
    assert repo.saved[0]["tokens_in"] == 10
