"""Live closeout B/C: two fresh Teaching Plans + twin Learn/Print realization.

Uses the production lesson-approach planner (LLM). Exits non-zero on failure.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from learn.generation.document_realizer import realize_learn_document
from print.generation.document_realizer import realize_print_document
from print.generation.whole_lesson.packet import (
    AnchorRecord,
    ApprovedItemRef,
    ImmutableLessonPacket,
    LessonIdentity,
    LessonLimits,
    ScopeContract,
    ScopeEntry,
    SlotRecord,
)
from print.generation.whole_lesson.teaching_agent import run_lesson_approach_planner

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[4] / "docs" / "generation-closeout" / "evidence"
)

INSTRUCTION_INTENTS = {
    "orient",
    "explain",
    "explain-cause",
    "introduce",
    "demonstrate",
    "example",
}
CHECK_INTENTS = {
    "check-understanding",
    "practice",
    "apply",
    "independent-practice",
}


def _conceptual_packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="closeout-b-conceptual",
            subject="Science",
            grade_level="Grade 5",
            objective="Explain why a covered leaf cannot make food even when the plant is watered.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[
                ScopeEntry(id="must-light", statement="Light is required to make food."),
                ScopeEntry(id="must-cover", statement="Covering a leaf blocks light from that leaf."),
            ],
            must_not_introduce=[
                ScopeEntry(id="exclude-chem", statement="chlorophyll molecular structure")
            ],
            terminology=["light", "leaf", "food", "cover"],
        ),
        anchor=AnchorRecord(
            id="anchor-covered-leaf",
            description="One plant with one leaf covered and one leaf in the light.",
        ),
        approved_items=[
            ApprovedItemRef(
                id="item-cover-1",
                card_id="card-cover-1",
                stem="Why did the covered leaf fail to make food?",
                options=[
                    {"key": "A", "text": "It had no light"},
                    {"key": "B", "text": "It had no water"},
                ],
                correct_key="A",
            )
        ],
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause", "explain"]),
            SlotRecord(slot_id="check", typical_intents=["check-understanding"]),
        ],
        limits=LessonLimits(max_sections=4, max_blocks_per_section=4, max_total_blocks=12),
    )


def _procedural_packet() -> ImmutableLessonPacket:
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="closeout-b-procedural",
            subject="Mathematics",
            grade_level="Grade 4",
            objective="Show how to find the area of a rectangle by multiplying length and width.",
            knowledge_type="procedural",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[
                ScopeEntry(
                    id="must-multiply",
                    statement="To find the area of a rectangle, multiply length by width.",
                ),
                ScopeEntry(
                    id="must-example",
                    statement="A 5 cm by 2 cm rectangle has an area of 10 square centimetres.",
                ),
            ],
            must_not_introduce=[
                ScopeEntry(id="exclude-pi", statement="area of a circle")
            ],
            terminology=["length", "width", "area", "rectangle"],
        ),
        anchor=AnchorRecord(
            id="anchor-tile-card",
            description="A 5 cm by 2 cm rectangle drawn on a card that will be covered with 1 cm tiles.",
        ),
        approved_items=[
            ApprovedItemRef(
                id="item-area-1",
                card_id="card-area-1",
                stem="A rectangle is 5 cm by 2 cm. What is its area?",
                options=[
                    {"key": "A", "text": "10 square centimetres"},
                    {"key": "B", "text": "7 centimetres"},
                ],
                correct_key="A",
            )
        ],
        slots=[
            SlotRecord(slot_id="orient", typical_intents=["orient"]),
            SlotRecord(slot_id="explain", typical_intents=["explain-cause", "explain"]),
            SlotRecord(slot_id="check", typical_intents=["check-understanding"]),
        ],
        limits=LessonLimits(max_sections=4, max_blocks_per_section=4, max_total_blocks=12),
    )


def _summarize(plan) -> dict:
    blocks = []
    native_leaks = []
    instruction_actions = 0
    check_actions = 0
    for section in plan.sections:
        for block in section.blocks:
            action = None
            if block.learner_action is not None:
                action = block.learner_action.action
                intent = (block.intent or "").strip().lower().replace("_", "-")
                if intent in INSTRUCTION_INTENTS:
                    instruction_actions += 1
                if intent in CHECK_INTENTS:
                    check_actions += 1
            payload = {
                "id": block.id,
                "intent": block.intent,
                "brief": block.brief[:240],
                "learner_action": action,
            }
            blocks.append(payload)
            blob = f"{block.intent} {block.brief} {action or ''}".lower()
            for token in (
                "worked-example",
                "answer-key",
                "ruled_lines",
                "multi-select",
                "fill-blank",
                "match-pairs",
            ):
                if token in blob:
                    native_leaks.append(f"{block.id}:{token}")
            if action in {
                "choice",
                "choices",
                "classify",
                "numeric",
                "questions",
                "worked-example",
            }:
                native_leaks.append(f"{block.id}:action={action}")
    return {
        "arc": plan.arc,
        "teaching_plan_id": plan.teaching_plan_id,
        "blocks": blocks,
        "instruction_actions": instruction_actions,
        "check_actions": check_actions,
        "native_leaks": native_leaks,
    }


async def _plan_one(
    name: str,
    packet: ImmutableLessonPacket,
    *,
    require_items: bool = True,
) -> dict:
    result = await run_lesson_approach_planner(
        packet,
        require_items=require_items,
        trace_id=f"closeout-b-{name}",
    )
    summary = _summarize(result.plan)
    return {
        "name": name,
        "ok": result.validation.ok,
        "summary": summary,
        "plan": result.plan.model_dump(mode="json"),
    }


def _twin_from_plan(plan) -> dict:
    learn = realize_learn_document(plan)
    printed = realize_print_document(plan)
    learn_kinds = [(d.teaching_block_id, d.kind, d.lane) for d in learn.decisions]
    print_kinds = [(d.teaching_block_id, d.kind, d.lane) for d in printed.decisions]
    return {
        "learn_decisions": learn_kinds,
        "print_decisions": print_kinds,
        "learn_composition_mode": learn.composition_mode,
        "print_composition_mode": printed.composition_mode,
        "select_one": _pair_for_action(plan, learn, printed, "select-one", "choice", "choices"),
        "classify_items": _pair_for_action(
            plan, learn, printed, "classify-items", "classify", "questions"
        ),
        "no_action_blocks": _no_action_pairs(plan, learn, printed),
    }


def _pair_for_action(plan, learn, printed, action: str, learn_kind: str, print_kind: str) -> dict:
    matches = []
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action and block.learner_action.action == action:
                learn_dec = next(
                    (d for d in learn.decisions if d.teaching_block_id == block.id and d.lane == "learn_interaction"),
                    None,
                )
                print_dec = next(
                    (d for d in printed.decisions if d.teaching_block_id == block.id and d.lane == "print_task"),
                    None,
                )
                matches.append(
                    {
                        "block_id": block.id,
                        "learn_kind": None if learn_dec is None else learn_dec.kind,
                        "print_kind": None if print_dec is None else print_dec.kind,
                        "ok": (
                            learn_dec is not None
                            and print_dec is not None
                            and learn_dec.kind == learn_kind
                            and print_dec.kind == print_kind
                        ),
                    }
                )
    return {"action": action, "matches": matches}


def _no_action_pairs(plan, learn, printed) -> list[dict]:
    rows = []
    for section in plan.sections:
        for block in section.blocks:
            if block.learner_action is not None:
                continue
            learn_task = [
                d.kind for d in learn.decisions if d.teaching_block_id == block.id and d.lane == "learn_interaction"
            ]
            print_task = [
                d.kind for d in printed.decisions if d.teaching_block_id == block.id and d.lane == "print_task"
            ]
            rows.append(
                {
                    "block_id": block.id,
                    "learn_tasks": learn_task,
                    "print_tasks": print_task,
                    "diverged": bool(learn_task) != bool(print_task),
                }
            )
    return rows


async def main() -> int:
    from curriculum.teaching_plan.models import TeachingPlan

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    conceptual_path = EVIDENCE_DIR / "phase-b-conceptual-plan.json"
    if conceptual_path.exists():
        plan_json = json.loads(conceptual_path.read_text(encoding="utf-8"))
        plan = TeachingPlan.model_validate(plan_json)
        conceptual = {
            "name": "conceptual",
            "ok": True,
            "summary": _summarize(plan),
            "plan": plan_json,
        }
    else:
        conceptual = await _plan_one("conceptual", _conceptual_packet())
        conceptual_path.write_text(json.dumps(conceptual["plan"], indent=2), encoding="utf-8")

    procedural = await _plan_one("procedural", _procedural_packet())
    (EVIDENCE_DIR / "phase-b-procedural-plan.json").write_text(
        json.dumps(procedural["plan"], indent=2),
        encoding="utf-8",
    )

    twin = _twin_from_plan(TeachingPlan.model_validate(conceptual["plan"]))
    payload = {
        "conceptual": {k: v for k, v in conceptual.items() if k != "plan"},
        "procedural": {k: v for k, v in procedural.items() if k != "plan"},
        "twin": twin,
        "prompt_hashes": __import__(
            "core.prompts.loader", fromlist=["closeout_prompt_hashes"]
        ).closeout_prompt_hashes(),
    }
    (EVIDENCE_DIR / "phase-b-c-live.json").write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )

    instruction = (
        conceptual["summary"]["instruction_actions"]
        + procedural["summary"]["instruction_actions"]
    )
    check = conceptual["summary"]["check_actions"] + procedural["summary"]["check_actions"]
    leaks = conceptual["summary"]["native_leaks"] + procedural["summary"]["native_leaks"]
    print(json.dumps(payload, indent=2))
    if leaks:
        print("CLOSEOUT_B=FAIL native ids in Teaching Plan", file=sys.stderr)
        return 1
    if instruction < 1 or check < 1:
        print(
            f"CLOSEOUT_B=FAIL instruction_actions={instruction} check_actions={check}",
            file=sys.stderr,
        )
        return 1
    print("CLOSEOUT_B=PASS")
    unexplained = [row for row in twin["no_action_blocks"] if row["diverged"]]
    if unexplained:
        print("CLOSEOUT_C=FAIL no-action divergence", unexplained, file=sys.stderr)
        return 1
    print("CLOSEOUT_C=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
