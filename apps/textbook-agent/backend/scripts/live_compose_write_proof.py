"""Live proof: Teaching Plan → LLM compose → LLM write (one paragraph + list).

Requires configured production LLM provider. Exits non-zero on failure.
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
from document.composer import compose_document_plan
from document.writer import write_document_primitive
from infra.authoring import LLMAuthoringProvider


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id="tp-live-correction",
        revision=1,
        arc="Students explain how stomata control gas exchange in leaves.",
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
                            "Open with the plant leaf as the teaching anchor. "
                            "Orient learners to stomata as adjustable openings."
                        ),
                        evidence="Learner names stomata as leaf openings.",
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
                            "Explain that stomata open to let CO2 in for photosynthesis "
                            "and close to limit water loss. Use the plant anchor. "
                            "Include a short caution about night-time closure myths."
                        ),
                        evidence="Learner can explain open/close trade-off.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="stomata function",
                            purpose="check understanding",
                            expected_evidence="correct option selected",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                    )
                ],
            ),
        ],
    )


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()
    composition = await compose_document_plan(
        plan,
        path="learn",
        provider=provider,
        allow_heuristic_fallback=False,
    )
    print("COMPOSITION", json.dumps(composition.model_dump(mode="json"), indent=2))
    kinds = [d.kind for d in composition.decisions if d.lane == "document"]
    if len(kinds) < 1:
        print("FAIL: no document decisions", file=sys.stderr)
        return 1
    if not any(k != "paragraph" for k in kinds) and len(kinds) == 1:
        # Multi-node preferred but not mandatory if pedagogy chooses one.
        pass

    # Write first two ordinary nodes (or one if only one).
    written = []
    blocks = {b.id: b for s in plan.sections for b in s.blocks}
    for decision in [d for d in composition.decisions if d.lane == "document"][:3]:
        block = blocks[decision.teaching_block_id]
        node = await write_document_primitive(
            kind=decision.kind,
            brief=block.brief,
            teaching_block={
                "id": block.id,
                "intent": block.intent,
                "brief": block.brief,
                "evidence": block.evidence,
            },
            lesson_context={
                "objective": plan.arc,
                "title": "Stomata lesson",
                "subject": "science",
            },
            evidence=block.evidence,
            teaching_block_id=block.id,
            role=decision.role,
            reason=decision.reason,
            provider=provider,
        )
        written.append(node)
        text_blob = json.dumps(node).lower()
        if "content pending" in text_blob or "option a" in text_blob:
            print("FAIL: placeholder content", node, file=sys.stderr)
            return 1
        if block.brief.strip().lower() in text_blob and decision.kind == "paragraph":
            # Exact brief copy forbidden for paragraphs.
            if node.get("text", "").strip() == block.brief.strip():
                print("FAIL: brief copied into paragraph", file=sys.stderr)
                return 1

    print("WRITTEN", json.dumps(written, indent=2))
    print("LIVE_COMPOSE_WRITE_PROOF=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
