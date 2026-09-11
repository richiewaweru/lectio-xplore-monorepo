"""Live proof: same Teaching Plan → Learn then Print independently (no conversion)."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from document.composer import compose_document_plan
from infra.authoring import LLMAuthoringProvider
from print.generation.composition_bridge import build_print_production_from_composition

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "document-overhaul"
    / "reports"
    / "evidence"
)


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id=f"tp-sibling-{uuid.uuid4().hex[:8]}",
        revision=1,
        arc="Students explain stomata open/close trade-offs.",
        sections=[
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="explain-b1",
                        position=0,
                        intent="explain",
                        brief="Explain stomata open for CO2 and close to limit water loss.",
                        evidence="Learner explains trade-off.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="stomata trade-off",
                            purpose="check",
                            expected_evidence="correct option",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                    )
                ],
            )
        ],
    )


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()

    learn = await compose_document_plan(plan, path="learn", provider=provider)
    form_plan, snapshot, print_comp = await build_print_production_from_composition(
        teaching_plan=plan, provider=provider
    )

    learn_kinds = [d.kind for d in learn.decisions]
    print_kinds = [d.kind for d in print_comp.decisions]
    print_lanes = [d.lane for d in print_comp.decisions]
    form_objects = [f.object for s in form_plan.sections for f in s.forms]

    # Independence: Print must not require Learn artifact; Learn must not contain print_task
    if any(d.lane == "print_task" for d in learn.decisions):
        print("LIVE_SIBLING=FAIL learn contains print_task", file=sys.stderr)
        return 1
    if any(d.lane == "learn_interaction" for d in print_comp.decisions):
        print("LIVE_SIBLING=FAIL print contains learn_interaction", file=sys.stderr)
        return 1
    if "print_task" not in print_lanes and "choices" not in form_objects:
        print("LIVE_SIBLING=FAIL print missing task treatment", file=sys.stderr)
        return 1

    evidence = {
        "teaching_plan_id": plan.teaching_plan_id,
        "learn_kinds": learn_kinds,
        "print_kinds": print_kinds,
        "print_lanes": print_lanes,
        "form_objects": form_objects,
        "print_teaching_plan_hash": getattr(snapshot, "teaching_plan_hash", None),
        "independence": "no conversion; both from Teaching Plan",
    }
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"sibling-{plan.teaching_plan_id}.json"
    path.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    print("LIVE_SIBLING teaching_plan_id=", plan.teaching_plan_id)
    print("LIVE_SIBLING learn_kinds=", json.dumps(learn_kinds))
    print("LIVE_SIBLING print_form_objects=", json.dumps(form_objects))
    print("LIVE_SIBLING evidence=", path)
    print("LIVE_SIBLING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
