"""Planner comparison script: fake packet loader, fake models, no DB writes."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from application.unit_lesson import staged_teaching_planner as stp
from application.unit_lesson import teaching_planner as tp
from curriculum.teaching_plan import semantic_review
from curriculum.teaching_plan.content_hash import teaching_plan_content_hash
from curriculum.teaching_plan.models import TeachingPlanDraftBlock, materialize_teaching_plan
from curriculum.teaching_plan.semantic_review import (
    TeachingPlanSemanticReviewDraft,
    TeachingPlanSemanticReviewResult,
)
from curriculum.teaching_plan.staged import (
    assemble_teaching_plan_draft,
    materialize_teaching_spine,
)
from infra.config import settings
from tests.planning.legality_fixtures import make_snapshot
from tests.planning.test_staged_assembly import SLOTS, _snapshot
from tests.planning.test_staged_sections import _good
from tests.planning.test_staged_spine import _draft_dict, _packet


def _load_script():
    path = Path(__file__).resolve().parents[1] / "scripts" / "compare_teaching_planners.py"
    spec = importlib.util.spec_from_file_location("compare_teaching_planners", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CMP = _load_script()


@pytest.fixture(autouse=True)
def _blocking_gate(monkeypatch):
    monkeypatch.setattr(settings, "teaching_plan_quality_gate", "blocking")


def _single_draft():
    spine = materialize_teaching_spine(
        _draft_dict(), slot_ids=SLOTS, item_backbone_refs=_packet().item_backbone_refs
    )
    blocks = {s: [TeachingPlanDraftBlock.model_validate(b.model_dump()) for b in _good(s).blocks] for s in SLOTS}
    return assemble_teaching_plan_draft(spine, blocks)


def _install_fakes(monkeypatch):
    async def spine(*, system_prompt, user_payload, trace_id, generation_id, attempt_start=1):
        draft = _draft_dict()
        return draft, draft.model_dump_json()

    async def section(*, system_prompt, user_payload, trace_id, generation_id, attempt_start=1):
        item = _good(user_payload["section"]["slot_id"])
        return item, item.model_dump_json()

    async def review(**kwargs):
        return TeachingPlanSemanticReviewDraft(reviewed=True, findings=[])

    monkeypatch.setattr(stp, "_call_spine_model", spine)
    monkeypatch.setattr(stp, "_call_section_model", section)
    monkeypatch.setattr(semantic_review, "_run_structured", review)

    seen: dict = {}

    async def single_call(**kwargs):
        seen.update(kwargs)
        draft = _single_draft()
        return draft, draft.model_dump_json()

    async def single_review(*, draft, plan, **kwargs):
        return TeachingPlanSemanticReviewResult(
            content_hash=teaching_plan_content_hash(plan), findings=[]
        )

    monkeypatch.setattr(tp, "_call_teaching_model", single_call)
    monkeypatch.setattr(tp, "review_teaching_plan_draft", single_review)
    return seen


async def _fake_loader(generation_id):
    return _packet(), _snapshot()


@pytest.mark.asyncio
async def test_run_compare_writes_files_and_report(monkeypatch, tmp_path) -> None:
    seen = _install_fakes(monkeypatch)
    entries = await CMP.run_compare(["gen-fake-1"], tmp_path, loader=_fake_loader)

    gen_dir = tmp_path / "gen-fake-1"
    for name in ("single.json", "staged.json", "report.md"):
        assert (gen_dir / name).is_file()
    assert (tmp_path / "summary.md").is_file()
    assert seen["generation_id"] is None
    assert seen["trace_id"].startswith("planner-compare:gen-fake-1:single")

    staged = json.loads((gen_dir / "staged.json").read_text())
    assert staged["ok"] is True
    assert set(staged) >= {"plan", "validation", "qc", "flags", "stage_timings", "attempts", "llm_calls"}
    assert [s["slot_id"] for s in staged["plan"]["sections"]] == SLOTS
    assert entries[0]["staged"][0]["ok"]
    assert json.loads((gen_dir / "single.json").read_text())["ok"] is True

    report = (gen_dir / "report.md").read_text()
    for heading in (
        "## Wall-clock",
        "## Single",
        "## Staged",
        "### LLM calls",
        "### Flags by code",
        "### Validation issues",
        "### Blocks with `visual`",
        "## Section-by-section diff",
        "### Slot `check`",
    ):
        assert heading in report
    assert "gen-fake-1" in (tmp_path / "summary.md").read_text()


@pytest.mark.asyncio
async def test_failure_is_recorded_not_raised(monkeypatch, tmp_path) -> None:
    _install_fakes(monkeypatch)

    async def boom(**kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr(stp, "_call_spine_model", boom)
    await CMP.run_compare(["g2"], tmp_path, modes=("staged",), loader=_fake_loader)
    staged = json.loads((tmp_path / "g2" / "staged.json").read_text())
    assert staged["ok"] is False and staged["error"]["type"]
    assert not (tmp_path / "g2" / "single.json").exists()
    assert "FAILED" in (tmp_path / "g2" / "report.md").read_text()


@pytest.mark.asyncio
async def test_repeat_writes_extra_runs(monkeypatch, tmp_path) -> None:
    _install_fakes(monkeypatch)
    await CMP.run_compare(["g3"], tmp_path, modes=("single",), repeat=2, loader=_fake_loader)
    assert (tmp_path / "g3" / "single.json").is_file()
    assert (tmp_path / "g3" / "single-r2.json").is_file()


class _ReadOnlySession:
    def __init__(self):
        self.rolled_back = False

    async def get(self, model, key):
        return object()

    def add(self, *a, **k):
        raise AssertionError("DB write attempted: add")

    async def commit(self):
        raise AssertionError("DB write attempted: commit")

    async def flush(self):
        raise AssertionError("DB write attempted: flush")

    async def rollback(self):
        self.rolled_back = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_load_inputs_never_writes_and_rolls_back(monkeypatch) -> None:
    from application.unit_lesson import teaching_plan_service as svc
    from core.database import session as db_session

    session = _ReadOnlySession()
    monkeypatch.setattr(db_session, "async_session_factory", lambda: session)

    async def fake_build(sess, generation, *, require_items=True):
        assert sess is session
        return _packet()

    monkeypatch.setattr(svc, "build_packet_for_generation", fake_build)
    packet, legality = await CMP.load_inputs("g4")
    assert packet.lesson.path_lesson_id == "l1"
    assert legality is not None
    assert session.rolled_back


@pytest.mark.asyncio
async def test_recorder_wraps_and_restores_run_llm(monkeypatch) -> None:
    class Usage:
        input_tokens = 10
        output_tokens = 5

    class Result:
        output = "x"

        def usage(self):
            return Usage()

    calls = []

    async def fake_run_llm(**kwargs):
        calls.append(kwargs)
        if kwargs["caller"] == "bad":
            raise ValueError("nope")
        return Result()

    monkeypatch.setattr(tp, "run_llm", fake_run_llm)
    with CMP.LlmRecorder() as rec:
        assert tp.run_llm is not fake_run_llm
        await tp.run_llm(caller="good", node="n", trace_id="t", attempt_start=2)
        with pytest.raises(ValueError):
            await tp.run_llm(caller="bad", trace_id="t")
    assert tp.run_llm is fake_run_llm
    assert rec.records[0]["total_tokens"] == 15 and rec.records[0]["attempt"] == 2
    assert rec.records[1]["error"].startswith("ValueError")


def _plan(sections):
    return {"plan": {"sections": sections}, "generation_id": "x", "ok": True}


def _blk(bid, intent, qids=(), visual=None):
    block = {"id": bid, "intent": intent, "source_question_ids": list(qids)}
    if visual:
        block["visual"] = visual
    return block


def test_section_diff_and_report_pure() -> None:
    single = _plan(
        [
            {"slot_id": "orient", "display_title": "Start", "blocks": [_blk("orient-b1", "orient")]},
            {
                "slot_id": "check",
                "display_title": "Check",
                "blocks": [_blk("check-b1", "check-understanding", ["q1"])],
            },
        ]
    )
    staged = _plan(
        [
            {"slot_id": "orient", "display_title": "Start", "blocks": [_blk("orient-b1", "orient")]},
            {
                "slot_id": "check",
                "display_title": "Check it",
                "blocks": [
                    _blk("check-b1", "check-understanding", ["q1"], {"figure_ref": "fig-a"}),
                    _blk("check-b2", "check-understanding", ["q2"]),
                ],
            },
        ]
    )
    rows = CMP.section_diff(single, staged)
    assert [r["slot_id"] for r in rows] == ["orient", "check"]
    assert rows[0]["diff"] == []
    check = rows[1]
    assert check["single"]["block_count"] == 1 and check["staged"]["block_count"] == 2
    assert check["staged"]["source_question_ids"] == ["q1", "q2"]
    assert check["staged"]["visual_block_ids"] == ["check-b1"]
    assert check["single"]["visual_block_ids"] == []
    assert any(line.startswith("+") and "check-b2" in line for line in check["diff"])
    assert CMP.visual_blocks(staged) == [
        {"slot_id": "check", "block_id": "check-b1", "figure_ref": "fig-a"}
    ]

    report = CMP.build_report(single, None)
    assert "Not run." in report and "## Section-by-section diff" in report
    assert CMP.section_diff(None, None) == []


def test_default_out_is_gitignored_location() -> None:
    assert CMP.DEFAULT_OUT.parts[-2:] == ("outputs", "planner-compare")
    assert CMP.DEFAULT_OUT.parent.parent == Path(CMP.__file__).resolve().parents[1]
