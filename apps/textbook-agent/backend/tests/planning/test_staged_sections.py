"""Section calls: payload, checks, figure copy, per-section retry, flags, review."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from application.unit_lesson import staged_teaching_planner as stp
from core.config import settings
from curriculum.teaching_plan.models import (
    TeachingPlanDraftBlock,
    materialize_teaching_plan,
)
from curriculum.teaching_plan.staged import (
    TeachingSectionDraft,
    assemble_teaching_plan_draft,
)
from print.generation.whole_lesson.teaching_errors import TeachingPlanOutputInvalidError
from tests.planning.legality_fixtures import make_snapshot
from tests.planning.test_staged_spine import _draft_dict, _packet, _spine

BRIEF = (
    "Walk through the garden bed example using the word area so learners connect "
    "counted squares to the length times width idea in this step."
)
EVIDENCE = "The garden bed anchor shows the idea concretely for learners right here."


@pytest.fixture(autouse=True)
def _blocking_gate(monkeypatch):
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")


def _block(intent: str, **kw: Any) -> dict:
    data = {"intent": intent, "brief": BRIEF, "evidence": EVIDENCE}
    data.update(kw)
    return data


def _check_block(item: str, **kw: Any) -> dict:
    return _block(
        "check-understanding",
        source_question_ids=[item],
        task_mode="assessment",
        learner_action={
            "action": "enter-text",
            "target": "area of the bed",
            "purpose": "check understanding",
            "expected_evidence": "correct area with units",
            "difficulty": "independent",
        },
        **kw,
    )


FIG_VISUAL = {
    "mode": "diagram",
    "purpose": "See the dimensions of the bed.",
    "must_show": ["a rectangle"],
    "labels_required": [],
    "figure_ref": "fig-a",
}


def _good(slot_id: str, *, visual: dict | None = None) -> TeachingSectionDraft:
    if slot_id == "check":
        blocks = [_check_block("q1", visual=visual or FIG_VISUAL), _check_block("q2")]
    else:
        blocks = [
            _block("orient" if slot_id == "orient" else "explain-cause") for _ in range(2)
        ]
    return TeachingSectionDraft.model_validate({"blocks": blocks})


def _context():
    packet = _packet()
    spine, packet = _spine(packet=packet)
    stp.repair_spine_figure_plan(spine, packet)  # check gets fig-a
    snapshot = make_snapshot(
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
    return spine, packet, stp.build_planner_projections(packet, snapshot)


class Fake:
    """Scripted _call_section_model keyed by the payload's section slot_id."""

    def __init__(self, monkeypatch, scripts: dict[str, list[Any]]):
        self.scripts = scripts
        self.payloads: dict[str, list[dict]] = {}
        monkeypatch.setattr(stp, "_call_section_model", self)

    async def __call__(self, *, system_prompt, user_payload, trace_id, generation_id,
                       attempt_start=1):
        slot = user_payload["section"]["slot_id"]
        self.payloads.setdefault(slot, []).append(user_payload)
        queue = self.scripts[slot]
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item, item.model_dump_json()

    def calls(self, slot: str) -> int:
        return len(self.payloads.get(slot, []))


def _all_good() -> dict[str, list[Any]]:
    return {s: [_good(s)] for s in ("orient", "explain", "check")}


def _run_all(monkeypatch, scripts, **kw):
    fake = Fake(monkeypatch, scripts)
    spine, packet, proj = _context()
    results = asyncio.run(
        stp.plan_teaching_sections(
            spine, packet, projections=proj, trace_id="t", generation_id="g", **kw
        )
    )
    return fake, results, spine, packet


def _assemble(spine, results):
    draft = assemble_teaching_plan_draft(spine, {k: r.blocks for k, r in results.items()})
    return materialize_teaching_plan(draft, slot_ids=[s.slot_id for s in spine.sections])


def _codes(errors: list[str]) -> set[str]:
    return {e.split(":", 1)[0].split(" ")[0] for e in errors}


# ------------------------------------------------------------------ payload


def test_section_payload_contents() -> None:
    spine, packet, proj = _context()
    payload = stp.section_payload(spine, "check", packet, proj)
    assert set(payload) == {
        "spine", "section", "slot", "slot_intent_policy", "lesson", "scope", "anchor",
        "terminology", "assigned_items", "assigned_misconceptions", "backbone_targets",
        "backbone_figures", "figure_plan", "reserved_assessment_scenarios",
        "assessment_source_policy", "planned_block_count",
    }
    assert payload["section"]["slot_id"] == "check"
    assert [i["approved_item_id"] for i in payload["assigned_items"]] == ["q1", "q2"]
    assert set(payload["assigned_items"][0]) == {
        "approved_item_id", "kind", "stem", "allowed_actions", "evidence_ref"}
    assert [f["id"] for f in payload["backbone_figures"]] == ["fig-a"]
    assert payload["reserved_assessment_scenarios"] == ["Area of the bed?", "Area of the big bed?"]
    assert set(payload["assessment_source_policy"]) == {
        "rules", "eligible_intents", "allowed_evidence_refs", "forbidden_terminology"}
    assert payload["planned_block_count"] == 2
    assert payload["slot_intent_policy"]["typical_intents"] == ["check-understanding"]
    orient = stp.section_payload(spine, "orient", packet, proj)
    assert [m["id"] for m in orient["assigned_misconceptions"]] == ["m1"]
    assert orient["assigned_items"] == [] and orient["backbone_figures"] == []


# ------------------------------------------------------------------ figure copy


def test_figure_copy_overwrites_drift_and_guard_passes() -> None:
    spine, packet, _ = _context()
    drift = dict(FIG_VISUAL, purpose="Something else", must_show=["a circle"],
                 labels_required=["radius"], mode="image")
    section = stp.materialize_one_section(
        spine, "check", list(_good("check", visual=drift).blocks))
    assert stp.figure_copy_errors(section, packet)
    changes = stp.copy_backbone_figures(section, packet)
    assert changes and set(changes[0]["fields"]) == {
        "mode", "purpose", "must_show", "labels_required"}
    visual = section.blocks[0].visual
    assert (visual.mode, visual.purpose, visual.must_show, visual.labels_required) == (
        "diagram", "See the dimensions of the bed.", ["a rectangle"], [])
    assert stp.figure_copy_errors(section, packet) == []
    assert stp.copy_backbone_figures(section, packet) == []


def test_figure_copy_empty_must_show_diagram_uses_purpose() -> None:
    packet = _packet()
    fig = dict(packet.backbone["figures"][0], must_show=[])
    packet = packet.model_copy(update={"backbone": {**packet.backbone, "figures": [fig]}})
    spine, _ = _spine(packet=packet)
    section = stp.materialize_one_section(
        spine, "check", list(_good("check", visual=dict(FIG_VISUAL, must_show=["x"])).blocks))
    stp.copy_backbone_figures(section, packet)
    assert section.blocks[0].visual.must_show == ["See the dimensions of the bed."]


def test_checks_pass_for_good_section_and_repair_drift() -> None:
    spine, packet, proj = _context()
    drift = dict(FIG_VISUAL, purpose="Other", must_show=["a circle"])
    section = stp.materialize_one_section(
        spine, "check", list(_good("check", visual=drift).blocks))
    errors, flags, repairs = stp.section_check_errors(spine, "check", section, packet, proj)
    assert errors == [] and flags == []
    assert any(r["repair"] == "backbone_figure_copy" for r in repairs)


def test_figure_plan_missing_and_sources_mismatch_and_block_count() -> None:
    spine, packet, proj = _context()
    blocks = [_check_block("q2")]  # no q1, no figure, one block instead of two
    section = stp.materialize_one_section(
        spine, "check", [TeachingPlanDraftBlock.model_validate(b) for b in blocks])
    errors, _, _ = stp.section_check_errors(spine, "check", section, packet, proj)
    codes = _codes(errors)
    assert {"FIGURE_PLAN_MISSING", "SECTION_SOURCES_MISMATCH", "SECTION_BLOCK_COUNT"} <= codes

    # Duplicate binding of one item and an unassigned one.
    blocks = [_check_block("q1", visual=FIG_VISUAL), _check_block("q1", visual=FIG_VISUAL)]
    section = stp.materialize_one_section(
        spine, "check", [TeachingPlanDraftBlock.model_validate(b) for b in blocks])
    errors, _, _ = stp.section_check_errors(spine, "check", section, packet, proj)
    mismatch = [e for e in errors if e.startswith("SECTION_SOURCES_MISMATCH")]
    assert mismatch and "q2" in mismatch[0] and "more than once" in mismatch[0]


def test_advisory_gate_turns_quality_issues_into_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "advisory")
    spine, packet, proj = _context()
    short = _block("explain-cause", brief="Area of the garden bed in few words only.")
    section = stp.materialize_one_section(
        spine, "explain", [TeachingPlanDraftBlock.model_validate(b) for b in (short, _block("explain-cause"))])
    errors, flags, _ = stp.section_check_errors(spine, "explain", section, packet, proj)
    assert errors == []
    assert "BRIEF_TOO_SHORT" in {f["code"] for f in flags}
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")
    section = stp.materialize_one_section(
        spine, "explain", [TeachingPlanDraftBlock.model_validate(b) for b in (short, _block("explain-cause"))])
    errors, _, _ = stp.section_check_errors(spine, "explain", section, packet, proj)
    assert "BRIEF_TOO_SHORT" in _codes(errors)


# ------------------------------------------------------------------ orchestration


def test_all_good_one_call_per_section(monkeypatch) -> None:
    fake, results, spine, _ = _run_all(monkeypatch, _all_good())
    assert {s: fake.calls(s) for s in results} == {"orient": 1, "explain": 1, "check": 1}
    assert all(not r.unresolved and r.flags == [] for r in results.values())
    assert all(r.latency_s > 0 and r.attempts[0].latency_s > 0 for r in results.values())
    plan = _assemble(spine, results)
    assert [b.id for b in plan.sections[2].blocks] == ["check-b1", "check-b2"]


def test_only_bad_section_retried(monkeypatch) -> None:
    scripts = _all_good()
    bad = TeachingSectionDraft.model_validate({"blocks": [_block("explain-cause")]})
    scripts["explain"] = [bad, _good("explain")]
    fake, results, _, _ = _run_all(monkeypatch, scripts)
    assert fake.calls("explain") == 2
    assert fake.calls("orient") == 1 and fake.calls("check") == 1
    repair = fake.payloads["explain"][1]["repair"]
    assert any(e.startswith("SECTION_BLOCK_COUNT") for e in repair["validation_errors"])
    assert repair["previous_output"]["blocks"] and "instruction" in repair
    assert "repair" not in fake.payloads["explain"][0]
    assert not results["explain"].unresolved
    assert len(results["explain"].attempts) == 2
    assert results["explain"].attempts[0].errors


def test_exhausted_section_ships_flagged_and_assembles(monkeypatch) -> None:
    scripts = _all_good()
    bad = TeachingSectionDraft.model_validate({"blocks": [_block("explain-cause")]})
    scripts["explain"] = [bad]
    fake, results, spine, _ = _run_all(monkeypatch, scripts)
    assert fake.calls("explain") == 3
    r = results["explain"]
    assert r.unresolved and len(r.blocks) == 1
    unresolved = [f for f in r.flags if f["code"] == "TEACHING_SECTION_UNRESOLVED"]
    assert len(unresolved) == 1
    assert unresolved[0]["section_ids"] == ["explain"] and unresolved[0]["block_ids"] == []
    assert "SECTION_BLOCK_COUNT" in unresolved[0]["message"]
    assert not results["orient"].unresolved and not results["check"].unresolved
    plan = _assemble(spine, results)
    assert [b.id for b in plan.sections[1].blocks] == ["explain-b1"]


def test_nothing_parses_raises_invalid(monkeypatch) -> None:
    scripts = _all_good()
    scripts["orient"] = [ValueError("not json")]
    Fake(monkeypatch, scripts)
    spine, packet, proj = _context()
    with pytest.raises(TeachingPlanOutputInvalidError):
        asyncio.run(
            stp.plan_teaching_sections(
                spine, packet, projections=proj, trace_id="t", generation_id="g"
            )
        )


def test_transport_errors_retry_without_repair_then_reraise(monkeypatch) -> None:
    scripts = _all_good()
    scripts["orient"] = [TimeoutError("boom"), _good("orient")]
    fake, results, _, _ = _run_all(monkeypatch, scripts)
    assert fake.calls("orient") == 2 and "repair" not in fake.payloads["orient"][1]
    assert not results["orient"].unresolved

    scripts["orient"] = [TimeoutError("boom")]
    Fake(monkeypatch, scripts)
    spine, packet, proj = _context()
    with pytest.raises(TimeoutError):
        asyncio.run(
            stp.plan_teaching_section(
                spine, "orient", packet, projections=proj,
                system_prompt="s", trace_id="t", generation_id=None,
            )
        )


def test_repair_findings_in_first_payload(monkeypatch) -> None:
    fake = Fake(monkeypatch, _all_good())
    spine, packet, proj = _context()
    result = asyncio.run(
        stp.plan_teaching_section(
            spine, "orient", packet, projections=proj, system_prompt="s",
            trace_id="t", generation_id=None, repair_findings=["progression_gap: fix it"],
        )
    )
    first = fake.payloads["orient"][0]
    assert first["repair"]["validation_errors"] == ["progression_gap: fix it"]
    assert not result.unresolved


def _finding(code: str):
    return SimpleNamespace(
        code=code, section_ids=["explain"], block_ids=["explain-b1"],
        message="msg", repair_instruction="do this",
        model_dump=lambda mode="json": {"code": code},
    )


def test_reviewer_finding_routes_retry(monkeypatch) -> None:
    seen: list[Any] = []

    async def reviewer(*, spine, slot_id, section, draft_blocks, packet):
        seen.append((slot_id, section.blocks[0].id, len(draft_blocks)))
        return [_finding("task_evidence_gap")] if len(seen) == 1 else []

    fake, results, _, _ = _run_all(
        monkeypatch,
        {"orient": [_good("orient")], "explain": [_good("explain")], "check": [_good("check")]},
        section_reviewer=reviewer,
    )
    total = sum(fake.calls(s) for s in results)
    assert total == 4  # exactly one section needed a second call
    retried = next(s for s in results if fake.calls(s) == 2)
    errs = fake.payloads[retried][1]["repair"]["validation_errors"]
    assert errs == ["SEMANTIC_TASK_EVIDENCE_GAP sections=['explain'] blocks=['explain-b1']: do this"]
    assert (retried, f"{retried}-b1", 2) in seen
    assert results[retried].attempts[0].review_findings


def test_advisory_only_reviewer_code_flags_without_retry(monkeypatch) -> None:
    async def reviewer(*, spine, slot_id, section, draft_blocks, packet):
        return [_finding("visual_missing_for_figure_objective")] if slot_id == "explain" else []

    fake, results, _, _ = _run_all(monkeypatch, _all_good(), section_reviewer=reviewer)
    assert fake.calls("explain") == 1
    flags = results["explain"].flags
    assert [f["code"] for f in flags] == ["visual_missing_for_figure_objective"]
    assert flags[0]["source"] == "reviewer" and not results["explain"].unresolved


def test_advisory_gate_flags_all_reviewer_findings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "advisory")

    async def reviewer(*, spine, slot_id, section, draft_blocks, packet):
        return [_finding("task_evidence_gap")] if slot_id == "explain" else []

    fake, results, _, _ = _run_all(monkeypatch, _all_good(), section_reviewer=reviewer)
    assert fake.calls("explain") == 1
    assert any(f["code"] == "task_evidence_gap" for f in results["explain"].flags)
