"""Live proof: Teaching Plan → Print composition bridge → FormPlan (ordinary + tasks).

Requires configured production LLM provider. Does not run full PDF assembly;
proves composition + Print task layering on the production bridge path.
"""

from __future__ import annotations

import asyncio
import json
import sys

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import LLMAuthoringProvider
from print.generation.composition_bridge import build_print_production_from_composition


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id="tp-live-print-correction",
        revision=1,
        arc="Students explain why plants need light to make food.",
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                specific_purpose="orient",
                blocks=[
                    TeachingPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="introduce",
                        brief=(
                            "Orient learners with the covered-leaf plant anchor. "
                            "State that light is required for food-making."
                        ),
                        evidence="Learner names light as required for plant food.",
                        evidence_refs=[],
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="explain",
                specific_purpose="explain",
                blocks=[
                    TeachingPlanBlock(
                        id="explain-b1",
                        position=0,
                        intent="explain",
                        brief=(
                            "Explain photosynthesis at Grade 4: leaves use light energy "
                            "to make sugar from water and carbon dioxide. Include a "
                            "simple figure cue for leaf + light."
                        ),
                        evidence="Learner explains light → food in own words.",
                        evidence_refs=[],
                    )
                ],
            ),
            TeachingPlanSection(
                slot_id="check",
                specific_purpose="check",
                blocks=[
                    TeachingPlanBlock(
                        id="check-b1",
                        position=0,
                        intent="check",
                        brief=(
                            "Check understanding with a select-one item about why a "
                            "covered leaf cannot make food."
                        ),
                        evidence="Correct option selected.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="covered leaf cannot make food",
                            purpose="check understanding",
                            expected_evidence="correct option selected",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                        source_question_ids=["q-covered-leaf-1"],
                    )
                ],
            ),
        ],
    )


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()
    form_plan, snapshot, composition = await build_print_production_from_composition(
        teaching_plan=plan,
        provider=provider,
    )
    decisions = list(composition.decisions)
    kinds = [d.kind for d in decisions]
    lanes = [d.lane for d in decisions]

    form_objects: list[str] = []
    for section in form_plan.sections:
        for item in section.forms:
            form_objects.append(str(item.object))

    print("LIVE_PRINT_COMPOSITION_PROOF kinds=", json.dumps(kinds))
    print("LIVE_PRINT_COMPOSITION_PROOF lanes=", json.dumps(lanes))
    print("LIVE_PRINT_COMPOSITION_PROOF form_objects=", json.dumps(form_objects))
    print(
        "LIVE_PRINT_COMPOSITION_PROOF snapshot_hash=",
        getattr(snapshot, "teaching_plan_hash", None) or "",
    )

    if not kinds:
        print("LIVE_PRINT_COMPOSITION_PROOF=FAIL empty composition", file=sys.stderr)
        return 1
    if "print_task" not in lanes and "choices" not in form_objects and "questions" not in form_objects:
        print(
            "LIVE_PRINT_COMPOSITION_PROOF=FAIL missing print task for select-one",
            file=sys.stderr,
        )
        return 1
    if not any(
        obj in {"prose", "figure", "table", "callout", "list", "choices", "questions"}
        for obj in form_objects
    ):
        print(
            "LIVE_PRINT_COMPOSITION_PROOF=FAIL unexpected form objects",
            file=sys.stderr,
        )
        return 1

    print("LIVE_PRINT_COMPOSITION_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
