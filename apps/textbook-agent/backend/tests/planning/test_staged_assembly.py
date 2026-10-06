"""Staged planner end to end: assembly, review routing, final gate, mode switch."""

from __future__ import annotations

import json
from typing import Any

import pytest

from application.unit_lesson import staged_teaching_planner as stp
from curriculum.approved_items import ItemPoolEmptyError
from curriculum.teaching_plan import semantic_review, service
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlanDraftBlock, materialize_teaching_plan
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticFinding,
    TeachingPlanSemanticReviewDraft,
)
from curriculum.teaching_plan.staged import (
    TeachingSectionDraft,
    assemble_teaching_plan_draft,
    materialize_teaching_spine,
)
from infra.config import settings
from print.generation.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError
from tests.planning.legality_fixtures import make_snapshot
from tests.planning.test_staged_sections import _block, _good, _over
from tests.planning.test_staged_spine import _draft_dict, _packet

SLOTS = ["orient", "explain", "check"]


@pytest.fixture(autouse=True)
def _blocking_gate(monkeypatch):
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")
    monkeypatch.setattr(settings, "staged_section_review", True)
    monkeypatch.setattr(settings, "staged_lesson_review", True)


def _snapshot():
    return make_snapshot(
        permitted_intents=["orient", "explain-cause", "check-understanding"],
        typical_by_slot={
            "orient": ["orient"],
            "explain": ["explain-cause"],
            "check": ["check-understanding"],
        },
        permitted_objects=["prose", "list", "table", "figure", "questions"],
        compatible_objects_by_intent={
            "orient": ["prose"],
            "explain-cause": ["prose"],
            "check-understanding": ["questions"],
        },
    )


class Harness:
    """Fake spine, section and reviewer models with call counters."""

    def __init__(self, monkeypatch, *, scripts=None, lesson_reviews=None, section_reviews=None):
        self.scripts = scripts or {s: [_good(s)] for s in SLOTS}
        self.section_calls: dict[str, list[dict]] = {}
        self.spine_calls = 0
        self.lesson_review_calls = 0
        self.section_review_calls = 0
        self.lesson_reviews = list(lesson_reviews or [])
        self.section_reviews = list(section_reviews or [])
        monkeypatch.setattr(stp, "_call_spine_model", self._spine)
        monkeypatch.setattr(stp, "_call_section_model", self._section)
        monkeypatch.setattr(semantic_review, "_run_structured", self._review)

    async def _spine(self, *, system_prompt, user_payload, trace_id, generation_id,
                     attempt_start=1):
        self.spine_calls += 1
        draft = _draft_dict()
        return draft, draft.model_dump_json()

    async def _section(self, *, system_prompt, user_payload, trace_id, generation_id,
                       attempt_start=1):
        slot = user_payload["section"]["slot_id"]
        self.section_calls.setdefault(slot, []).append(user_payload)
        queue = self.scripts[slot]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        return item, item.model_dump_json()

    async def _review(self, **kwargs):
        if kwargs["caller"] == "teaching_lesson_reviewer":
            self.lesson_review_calls += 1
            queue = self.lesson_reviews
        else:
            self.section_review_calls += 1
            queue = self.section_reviews
        findings = (queue.pop(0) if len(queue) > 1 else (queue[0] if queue else [])) or []
        return TeachingPlanSemanticReviewDraft(reviewed=True, findings=list(findings))

    def calls(self, slot: str) -> int:
        return len(self.section_calls.get(slot, []))


def _finding(
    code: str, sections: list[str], blocks: list[str] | None = None
) -> TeachingPlanSemanticFinding:
    return TeachingPlanSemanticFinding(
        code=code,
        section_ids=sections,
        block_ids=blocks or [],
        message=f"Concrete {code} defect across the lesson.",
        repair_instruction=f"Repair the {code} defect in the named section.",
    )


async def _run(**kw):
    return await stp.run_staged_teaching_planner(
        _packet(), legality=_snapshot(), trace_id="t", generation_id="g", **kw
    )


def _bad_explain() -> TeachingSectionDraft:
    """Two blocks (within budget) but one brief is too short: fails every attempt."""
    return TeachingSectionDraft.model_validate(
        {"blocks": [_block("explain-cause", brief="Area in few words only."),
                    _block("explain-cause")]}
    )


def _hash_of(result) -> str:
    return teaching_plan_content_hash(result.plan)


# ------------------------------------------------------------------ happy path


async def test_end_to_end_matches_materialize_and_binds_review(monkeypatch) -> None:
    h = Harness(monkeypatch)
    result = await _run()
    plan = result.plan

    assert [s.slot_id for s in plan.sections] == SLOTS
    for section in plan.sections:
        assert [b.id for b in section.blocks] == [
            f"{section.slot_id}-b{i + 1}" for i in range(len(section.blocks))
        ]
    # Same ids as materialize_teaching_plan over the same assembled draft.
    blocks = {
        s.slot_id: [
            TeachingPlanDraftBlock.model_validate(b.model_dump(exclude={"id", "position"}))
            for b in s.blocks
        ]
        for s in plan.sections
    }
    spine_draft = _draft_dict()
    spine_obj = materialize_teaching_spine(
        spine_draft, slot_ids=SLOTS, item_backbone_refs=_packet().item_backbone_refs
    )
    expected = materialize_teaching_plan(
        assemble_teaching_plan_draft(spine_obj, blocks), slot_ids=SLOTS
    )
    assert [b.id for s in plan.sections for b in s.blocks] == [
        b.id for s in expected.sections for b in s.blocks
    ]
    assert [a.slot_id for a in plan.anchor_usage] == SLOTS

    assert result.validation.ok
    assert result.semantic_review.content_hash == _hash_of(result)
    assert {"code": "TEACHING_PLAN_SEMANTIC_REVIEW_PASS",
            "content_hash": _hash_of(result)} in result.qc
    assert result.flags == []
    assert result.attempts[-1].plan is plan and result.attempts[-1].semantic_review is not None
    assert [a.attempt for a in result.attempts] == list(range(1, len(result.attempts) + 1))
    assert set(json.loads(result.raw_response)) == {"spine", "sections"}
    assert h.spine_calls == 1 and all(h.calls(s) == 1 for s in SLOTS)
    assert h.lesson_review_calls == 1 and h.section_review_calls == 3
    timings = result.stage_timings
    assert timings["spine"]["attempts"] == 1
    assert set(timings["sections"]) == set(SLOTS)
    assert timings["lesson_review"]["blocking"] == 0 and timings["fix_round"] == {}


async def test_require_items(monkeypatch) -> None:
    Harness(monkeypatch)
    packet = _packet().model_copy(update={"approved_items": []})
    with pytest.raises(ItemPoolEmptyError):
        await stp.run_staged_teaching_planner(packet, legality=_snapshot())


# ------------------------------------------------------------------ flag, don't fail


async def test_always_failing_section_ships_flagged(monkeypatch) -> None:
    # A too-short brief fails the section checks on every attempt.
    short = _bad_explain()
    h = Harness(monkeypatch, scripts={"orient": [_good("orient")], "explain": [short],
                                      "check": [_good("check")]})
    result = await _run()
    assert h.calls("explain") == 3
    codes = {(f["code"], tuple(f["section_ids"])) for f in result.flags}
    assert ("TEACHING_SECTION_UNRESOLVED", ("explain",)) in codes
    assert [s.slot_id for s in result.plan.sections] == SLOTS
    assert result.validation.ok
    assert result.semantic_review.content_hash == _hash_of(result)
    assert result.stage_timings["sections"]["explain"]["unresolved"] is True


async def test_unresolved_section_error_becomes_flag_but_resolved_section_fails(
    monkeypatch,
) -> None:
    short = _bad_explain()
    Harness(monkeypatch, scripts={"orient": [_good("orient")], "explain": [short],
                                  "check": [_good("check")]})
    monkeypatch.setattr(
        stp, "_task_source_contract_errors",
        lambda plan: ["TEACHING_FORMATIVE_ACTION_REQUIRED: block 'explain-b1' must act."],
    )
    result = await _run()
    assert any(f["code"] == "TEACHING_FORMATIVE_ACTION_REQUIRED"
               and f["section_ids"] == ["explain"] and f["block_ids"] == ["explain-b1"]
               for f in result.flags)

    Harness(monkeypatch)  # explain resolves this time
    monkeypatch.setattr(
        stp, "_task_source_contract_errors",
        lambda plan: ["TEACHING_FORMATIVE_ACTION_REQUIRED: block 'explain-b1' must act."],
    )
    with pytest.raises(TeachingPlanOutputInvalidError) as exc:
        await _run()
    assert "explain-b1" in str(exc.value)


# ------------------------------------------------------------------ review routing


async def test_blocking_lesson_finding_reroutes_only_named_section(monkeypatch) -> None:
    changed = TeachingSectionDraft.model_validate(
        {"blocks": [dict(_block("explain-cause"), brief=_block("explain-cause")["brief"]
                         + " Add a short worked comparison."),
                    _block("explain-cause")]}
    )
    h = Harness(
        monkeypatch,
        scripts={"orient": [_good("orient")], "explain": [_good("explain"), changed],
                 "check": [_good("check")]},
        lesson_reviews=[[_finding("progression_gap", ["explain"])], []],
    )
    result = await _run()
    assert h.calls("explain") == 2 and h.calls("orient") == 1 and h.calls("check") == 1
    errors = h.section_calls["explain"][1]["repair"]["validation_errors"]
    assert errors[0].startswith("SEMANTIC_PROGRESSION_GAP sections=['explain']")
    assert "Repair the progression_gap defect" in errors[0]
    assert h.lesson_review_calls == 2
    assert "worked comparison" in result.plan.sections[1].blocks[0].brief
    # The bound review is the second one, for the reassembled plan.
    assert result.semantic_review.content_hash == _hash_of(result)
    assert result.flags == []
    fix = result.stage_timings["fix_round"]
    assert fix["sections"] == ["explain"] and fix["replaced"] == ["explain"]
    assert result.stage_timings["lesson_review"]["blocking"] == 1


async def test_still_blocking_after_fix_round_becomes_flag(monkeypatch) -> None:
    h = Harness(monkeypatch, lesson_reviews=[[_finding("progression_gap", ["explain"])]])
    result = await _run()
    assert h.calls("explain") == 2  # one bounded fix round, no more
    assert h.lesson_review_calls == 2
    flag = next(f for f in result.flags if f["code"] == "progression_gap")
    assert flag["section_ids"] == ["explain"] and flag["source"] == "reviewer"
    assert "Still unresolved after one fix round" in flag["message"]
    assert result.semantic_review.content_hash == _hash_of(result)
    assert result.validation.ok


async def test_advisory_only_code_is_flag_without_fix_round(monkeypatch) -> None:
    h = Harness(monkeypatch, lesson_reviews=[[
        _finding("visual_missing_for_figure_objective", ["check"])]])
    result = await _run()
    assert h.lesson_review_calls == 1 and all(h.calls(s) == 1 for s in SLOTS)
    assert [f["code"] for f in result.flags] == ["visual_missing_for_figure_objective"]


async def test_advisory_gate_flags_every_lesson_finding(monkeypatch) -> None:
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "advisory")
    h = Harness(monkeypatch, lesson_reviews=[[_finding("progression_gap", ["explain"])]])
    result = await _run()
    assert h.lesson_review_calls == 1 and h.calls("explain") == 1
    assert any(f["code"] == "progression_gap" for f in result.flags)


# ------------------------------------------------------------------ mode switch


async def test_plan_shared_teaching_picks_runner_by_mode(monkeypatch) -> None:
    seen: list[str] = []

    async def single(packet, **kw):
        seen.append("single")
        return "S"

    async def staged(packet, **kw):
        seen.append("staged")
        return "T"

    monkeypatch.setattr(service, "_shared_teaching_runner", single)
    monkeypatch.setattr(service, "_staged_teaching_runner", staged)

    assert settings.teaching_planner_mode == "single"
    assert await service.plan_shared_teaching(object()) == "S"
    monkeypatch.setattr(settings, "teaching_planner_mode", "staged")
    assert await service.plan_shared_teaching(object()) == "T"
    assert seen == ["single", "staged"]

    monkeypatch.setattr(service, "_staged_teaching_runner", None)
    with pytest.raises(RuntimeError, match="no staged teaching planner is bound"):
        await service.plan_shared_teaching(object())


def test_composition_root_binds_staged_runner() -> None:
    from application.unit_lesson import teaching_plan_service  # noqa: F401

    assert service._staged_teaching_runner is stp.run_staged_teaching_planner


# ------------------------------------------------------------------ visuals integration


async def test_staged_plan_visuals_reach_figure_nodes_and_plan_figure_spec(monkeypatch) -> None:
    """staged plan -> composer figure items -> FigureNode -> media._plan_figure_spec.

    Covered: the composer places exactly one code-owned figure item per block with a
    ``visual`` (stable ids, validate_composition_plan passes), and ``_plan_figure_spec``
    resolves each FigureNode to that block's VisualSpec (the backbone-copied one for
    the figure_ref block). Not covered: the section writer and
    ``build_figure_work_order`` (need an accepted section, source revision and DB-backed
    runtime), which are unchanged and plan-source-agnostic.
    """
    from document.shared_lesson.composer import (
        CompositionChoice,
        validate_and_build_composition,
        validate_composition_plan,
    )
    from document.shared_lesson.media import _plan_figure_spec
    from document.shared_lesson.models import FigureNode

    explain_visual = {
        "mode": "diagram",
        "purpose": "Show squares covering the garden bed.",
        "must_show": ["squares cover surfaces"],
        "labels_required": [],
    }
    explain = TeachingSectionDraft.model_validate(
        {"blocks": [dict(_block("explain-cause"), visual=explain_visual),
                    _block("explain-cause")]}
    )
    Harness(monkeypatch, scripts={"orient": [_good("orient")], "explain": [explain],
                                  "check": [_good("check")]})
    result = await _run()
    with_visual = [(s, b) for s in result.plan.sections for b in s.blocks if b.visual]
    assert {b.id for _, b in with_visual} == {"explain-b1", "check-b1"}

    resolved: dict[str, Any] = {}
    for section in result.plan.sections:
        choices = [
            CompositionChoice(
                teaching_block_id=b.id, kind="paragraph", semantic_role="explanation"
            )
            for b in section.blocks
        ]
        composition = validate_and_build_composition(
            section=section, choices=choices, tasks=[], reserve_key_idea=False
        )
        validate_composition_plan(plan=composition, section=section, tasks=[])
        figures = [item for item in composition.items if item.kind == "figure"]
        assert [f.teaching_block_id for f in figures] == [
            b.id for b in section.blocks if b.visual
        ]
        for item in figures:
            node = FigureNode.model_validate(
                {
                    "id": item.id,
                    "kind": "figure",
                    "teaching_block_id": item.teaching_block_id,
                    "display": {"caption": "A figure"},
                    "accessibility": {"alt_text": ""},
                }
            )
            resolved[item.teaching_block_id] = _plan_figure_spec(section, node)

    assert set(resolved) == {b.id for _, b in with_visual}
    for _, block in with_visual:
        assert resolved[block.id] == block.visual
    assert resolved["check-b1"].purpose == "See the dimensions of the bed."  # backbone copy


# ------------------------------------------------------------------ review settings


async def test_section_review_off_lesson_review_reports_all_codes(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staged_section_review", False)
    seen: list[dict] = []
    h = Harness(
        monkeypatch,
        lesson_reviews=[[_finding("task_evidence_gap", ["explain"], ["explain-b1"])], []],
    )
    original = h._review

    async def spy(**kwargs):
        seen.append(kwargs)
        return await original(**kwargs)

    monkeypatch.setattr(semantic_review, "_run_structured", spy)
    result = await _run()
    assert h.section_review_calls == 0
    assert h.lesson_review_calls == 2
    # Section-local finding is blocking, routed to the named section, fixed once.
    assert h.calls("explain") == 2 and h.calls("orient") == 1
    errors = h.section_calls["explain"][1]["repair"]["validation_errors"]
    assert errors[0].startswith("SEMANTIC_TASK_EVIDENCE_GAP sections=['explain']")
    assert "task_evidence_gap" in seen[0]["system_prompt"]
    assert "NOT reviewed separately" in seen[0]["system_prompt"]
    assert result.semantic_review.content_hash == _hash_of(result)


async def test_section_review_off_run_section_stage_has_no_reviewer(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staged_section_review", False)
    h = Harness(monkeypatch)
    spine = stp.materialize_teaching_spine(
        _draft_dict(), slot_ids=SLOTS, item_backbone_refs=_packet().item_backbone_refs
    )
    stp.repair_spine_figure_plan(spine, _packet())
    result = await stp.run_section_stage(
        spine, "orient", _packet(), _snapshot(), trace_id="t", generation_id="g"
    )
    assert not result.unresolved and h.section_review_calls == 0


async def test_lesson_review_failure_is_advisory_flag(monkeypatch) -> None:
    h = Harness(monkeypatch)

    async def broken(**kwargs):
        if kwargs["caller"] == "teaching_lesson_reviewer":
            raise TimeoutError("reviewer timed out after 240s")
        return await h._review(**kwargs)

    monkeypatch.setattr(semantic_review, "_run_structured", broken)
    result = await _run()
    assert result.validation.ok and result.semantic_review is None
    flag = next(f for f in result.flags if f["code"] == "LESSON_REVIEW_UNAVAILABLE")
    assert flag["source"] == "reviewer" and "could not run" in flag["message"]
    assert result.stage_timings["lesson_review"]["state"] == "unavailable"
    assert {"code": "TEACHING_PLAN_SEMANTIC_REVIEW_SKIPPED", "state": "unavailable"} in result.qc


async def test_lesson_review_off_skips_review_and_fix_round(monkeypatch) -> None:
    monkeypatch.setattr(settings, "staged_lesson_review", False)
    h = Harness(monkeypatch, lesson_reviews=[[_finding("progression_gap", ["explain"])]])
    result = await _run()
    assert h.lesson_review_calls == 0 and h.calls("explain") == 1
    assert result.semantic_review is None and result.validation.ok
    assert result.flags == []
    assert result.stage_timings["lesson_review"]["state"] == "skipped"
    assert result.stage_timings["fix_round"] == {}
    assert {"code": "TEACHING_PLAN_SEMANTIC_REVIEW_SKIPPED", "state": "skipped"} in result.qc


async def test_no_output_section_flows_through_finish_as_flag(monkeypatch) -> None:
    scripts = {s: [_good(s)] for s in SLOTS}
    scripts["orient"] = [ValueError("not json")]
    h = Harness(monkeypatch, scripts=scripts)
    result = await _run()
    assert h.calls("orient") == 3
    orient = result.plan.sections[0]
    assert orient.blocks == [] and orient.slot_id == "orient"
    assert ("TEACHING_SECTION_UNRESOLVED", ("orient",)) in {
        (f["code"], tuple(f["section_ids"])) for f in result.flags
    }
    assert result.stage_timings["sections"]["orient"]["unresolved"] is True
    assert result.semantic_review is None or result.semantic_review.content_hash == _hash_of(
        result
    )
