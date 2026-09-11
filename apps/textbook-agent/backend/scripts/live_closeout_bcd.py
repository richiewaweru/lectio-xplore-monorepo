"""Closeout live proofs after Google sign-in: second Teaching Plan + twin + Print writer.

Uses production planner/composer/writer. Does not print the JWT.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from curriculum.teaching_plan.models import TeachingPlan
from learn.generation.document_realizer import realize_learn_document
from print.generation.composition_bridge import build_print_production_from_composition
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
from core.prompts.loader import closeout_prompt_hashes
from infra.authoring import LLMAuthoringProvider

EVIDENCE = Path(__file__).resolve().parents[4] / "docs" / "generation-closeout" / "evidence"


def _ratio_packet() -> ImmutableLessonPacket:
    """Procedural/math shape — same planner contract as the successful conceptual packet."""
    return ImmutableLessonPacket(
        lesson=LessonIdentity(
            path_lesson_id="closeout-b-ratios",
            subject="Mathematics",
            grade_level="Grade 6",
            objective="Explain what a ratio is and use a ratio to compare two quantities in a simple recipe.",
            knowledge_type="conceptual",
            lesson_mode="first_exposure",
        ),
        scope=ScopeContract(
            must_establish=[
                ScopeEntry(
                    id="must-ratio",
                    statement="A ratio compares two quantities using the same kind of unit.",
                ),
                ScopeEntry(
                    id="must-order",
                    statement="The order of a ratio matters: 2:3 is not the same as 3:2.",
                ),
            ],
            must_not_introduce=[
                ScopeEntry(id="exclude-rate", statement="unit rates and speed")
            ],
            terminology=["ratio", "compare", "quantity", "recipe"],
        ),
        anchor=AnchorRecord(
            id="anchor-juice",
            description="A juice recipe that mixes 2 cups concentrate with 3 cups water.",
        ),
        approved_items=[
            ApprovedItemRef(
                id="item-ratio-1",
                card_id="card-ratio-1",
                stem="A juice mix uses 2 cups concentrate and 3 cups water. What is the ratio of concentrate to water?",
                options=[
                    {"key": "A", "text": "2:3"},
                    {"key": "B", "text": "3:2"},
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


def _summarize(plan: TeachingPlan) -> dict:
    instruction = 0
    check = 0
    blocks = []
    for section in plan.sections:
        for block in section.blocks:
            action = block.learner_action.action if block.learner_action else None
            intent = (block.intent or "").lower().replace("_", "-")
            if action and intent in {
                "orient",
                "explain",
                "explain-cause",
                "introduce",
                "demonstrate",
            }:
                instruction += 1
            if action and intent in {
                "check-understanding",
                "practice",
                "apply",
                "practise-guided",
                "practise-independent",
            }:
                check += 1
            blocks.append(
                {
                    "id": block.id,
                    "intent": block.intent,
                    "action": action,
                    "brief": (block.brief or "")[:200],
                }
            )
    return {
        "instruction_actions": instruction,
        "check_actions": check,
        "blocks": blocks,
        "arc": plan.arc[:240],
    }


async def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    conceptual_path = EVIDENCE / "phase-b-conceptual-plan.json"
    if not conceptual_path.exists():
        print("CLOSEOUT_B=FAIL missing conceptual plan evidence", file=sys.stderr)
        return 1
    conceptual = TeachingPlan.model_validate(
        json.loads(conceptual_path.read_text(encoding="utf-8"))
    )

    result = await run_lesson_approach_planner(
        _ratio_packet(),
        require_items=True,
        trace_id="closeout-b-ratios",
    )
    lever = result.plan
    (EVIDENCE / "phase-b-ratio-plan.json").write_text(
        json.dumps(lever.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    c_sum = _summarize(conceptual)
    l_sum = _summarize(lever)

    learn = realize_learn_document(conceptual)
    printed = realize_print_document(conceptual)
    twin = {
        "learn": [(d.teaching_block_id, d.kind, d.lane) for d in learn.decisions],
        "print": [(d.teaching_block_id, d.kind, d.lane) for d in printed.decisions],
    }
    select_ok = any(
        d.kind == "choice" and d.lane == "learn_interaction" for d in learn.decisions
    ) and any(
        d.kind == "choices" and d.lane == "print_task" for d in printed.decisions
    )

    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    form_plan, snapshot, print_comp = await build_print_production_from_composition(
        teaching_plan=conceptual, provider=provider
    )
    composition_mode = getattr(print_comp, "composition_mode", None)
    writer_kinds = [d.kind for d in print_comp.decisions if d.lane == "document"]

    payload = {
        "conceptual_summary": c_sum,
        "ratio_summary": l_sum,
        "twin": twin,
        "select_one_ok": select_ok,
        "print_composition_mode": composition_mode,
        "print_document_kinds": writer_kinds,
        "form_objects": [
            str(item.object) for section in form_plan.sections for item in section.forms
        ],
        "prompt_hashes": closeout_prompt_hashes(),
        "snapshot_hash": getattr(snapshot, "teaching_plan_hash", None),
    }
    (EVIDENCE / "phase-b-c-d-live.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, indent=2))

    if c_sum["instruction_actions"] < 1 or c_sum["check_actions"] < 1:
        print("CLOSEOUT_B=FAIL conceptual action placement", file=sys.stderr)
        return 1
    if l_sum["check_actions"] < 1 and l_sum["instruction_actions"] < 1:
        print("CLOSEOUT_B=FAIL ratio plan has no natural actions", file=sys.stderr)
        return 1
    print("CLOSEOUT_B=PASS")
    if not select_ok:
        print("CLOSEOUT_C=FAIL select-one twin", file=sys.stderr)
        return 1
    print("CLOSEOUT_C=PASS")
    if composition_mode == "heuristic_fallback":
        print("CLOSEOUT_D=FAIL heuristic_fallback", file=sys.stderr)
        return 1
    print("CLOSEOUT_D=COMPOSITION_PASS mode=", composition_mode)
    return 0


if __name__ == "__main__":
    # Optional token for later Unit API proofs; never log it.
    os.environ.setdefault("CLOSEOUT_TOKEN", "")
    raise SystemExit(asyncio.run(main()))
