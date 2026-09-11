"""Produce a LearnDocument from the closeout conceptual Teaching Plan (has select-one)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from curriculum.teaching_plan.models import TeachingPlan
from infra.authoring import LLMAuthoringProvider
from learn.generation.native_production import produce_learn_document_from_teaching_async

EVIDENCE = Path(__file__).resolve().parents[4] / "docs" / "generation-closeout" / "evidence"


async def main() -> int:
    plan = TeachingPlan.model_validate(
        json.loads((EVIDENCE / "phase-b-conceptual-plan.json").read_text(encoding="utf-8"))
    )
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    result = await produce_learn_document_from_teaching_async(
        teaching_plan=plan,
        title="Closeout G covered leaf",
        subject="Science",
        source_generation_id="closeout-g-conceptual",
        provider=provider,
        allow_heuristic_composition_fallback=False,
    )
    document = result["document"]
    composition = result["composition_plan"]
    interactions = [
        {
            "id": n.get("id"),
            "type": n.get("interaction_type"),
            "prompt": str(n.get("prompt") or "")[:120],
        }
        for n in document.get("nodes") or []
        if n.get("kind") == "interaction"
    ]
    out = {
        "composition_mode": getattr(composition, "composition_mode", None),
        "sections": document.get("sections"),
        "interactions": interactions,
        "document_id": document.get("id"),
        "node_count": len(document.get("nodes") or []),
        "teaching_plan_hash": result.get("teaching_plan_hash"),
    }
    (EVIDENCE / "phase-g-learn-doc.json").write_text(
        json.dumps({"summary": out, "document": document}, indent=2, default=str),
        encoding="utf-8",
    )
    print(json.dumps(out, indent=2))
    if len(interactions) < 2:
        print("CLOSEOUT_G=FAIL need >=2 interactions", file=sys.stderr)
        return 1
    types = {i["type"] for i in interactions}
    if len(types) < 1:
        print("CLOSEOUT_G=FAIL no interaction types", file=sys.stderr)
        return 1
    print("CLOSEOUT_G=DOC_PASS types=", sorted(types))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
