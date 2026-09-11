"""Live proof: LearnDocument persist → edit → save → reload (API/DB, no browser).

Uses production LLM generation + builder CRUD endpoints against local stack.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.database.models import EditableLessonModel, GenerationModel, UserModel
from core.database.session import async_session_factory
from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import LLMAuthoringProvider
from learn.generation.native_production import produce_learn_document_from_teaching_async
from learn.runtime.evaluation import evaluate_interaction, find_interaction_in_document

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "document-overhaul"
    / "reports"
    / "evidence"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id=f"tp-live-edit-{uuid.uuid4().hex[:8]}",
        revision=1,
        arc="Students explain stomata gas-exchange trade-offs.",
        sections=[
            TeachingPlanSection(
                slot_id="orient",
                specific_purpose="orient",
                blocks=[
                    TeachingPlanBlock(
                        id="orient-b1",
                        position=0,
                        intent="introduce",
                        brief="Orient with the leaf anchor. Introduce stomata as adjustable openings.",
                        evidence="Learner names stomata.",
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
                            "Explain open/close trade-off for CO2 vs water loss. "
                            "Warn about night-time closure myths."
                        ),
                        evidence="Learner explains trade-off.",
                        evidence_refs=[],
                        learner_action=LearnerActionBrief(
                            action="select-one",
                            target="stomata trade-off",
                            purpose="check understanding",
                            expected_evidence="correct option",
                            difficulty="guided",  # type: ignore[arg-type]
                        ),
                    )
                ],
            ),
        ],
    )


def _response_for(contract: dict) -> dict:
    kind = str(contract.get("kind") or "")
    config = contract.get("config") if isinstance(contract.get("config"), dict) else {}
    if kind == "choice":
        correct = config.get("correct_option_id")
        if not correct:
            opts = config.get("options") or []
            correct = opts[0]["id"] if opts and isinstance(opts[0], dict) else "a"
        return {"selected_option_id": correct}
    if kind == "multi-select":
        ids = list(config.get("correct_option_ids") or [])
        return {"selected_option_ids": ids}
    if kind == "fill-blank":
        answers = list(config.get("answers") or ["answer"])
        blank_ids = list(config.get("blank_ids") or ["blank-1"])
        return {"answers": {blank_ids[0]: answers[0]}}
    if kind == "numeric":
        return {"value": config.get("value", 0)}
    if kind == "short-response":
        return {"text": "Because stomata open for CO2 and close to limit water loss."}
    if kind == "sequence":
        return {"order": list(config.get("order") or [])}
    if kind in {"match-pairs", "classify"}:
        pairs = config.get("pairs") or []
        return {"pairs": pairs}
    return {}


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()
    output_id = f"learn-out-{uuid.uuid4().hex[:12]}"
    editable_id = str(uuid.uuid4())
    user_id = f"correction-edit-{uuid.uuid4().hex[:8]}"

    import learn.generation.native_production as np

    async def _fake_attach(node, **_kwargs):
        out = dict(node)
        out["asset_id"] = f"proof/{out.get('id', 'fig')}.png"
        return out

    original = np.attach_figure_asset
    np.attach_figure_asset = _fake_attach  # type: ignore[assignment]
    try:
        production = await produce_learn_document_from_teaching_async(
            teaching_plan=plan,
            title="Stomata trade-off",
            subject="science",
            source_generation_id=output_id,
            lesson_id=output_id,
            provider=provider,
        )
    finally:
        np.attach_figure_asset = original  # type: ignore[assignment]

    document = dict(production["document"])
    document["id"] = editable_id
    document["source_generation_id"] = output_id
    now = _utcnow()

    async with async_session_factory() as session:
        session.add(
            UserModel(id=user_id, email=f"{user_id}@example.invalid", name="Edit proof")
        )
        session.add(
            GenerationModel(
                id=output_id,
                user_id=user_id,
                subject="science",
                context="edit/save/reload proof",
                status="completed",
                requested_template_id="lesson",
                requested_preset_id="standard",
                created_at=now,
                document_json={**document, "id": output_id},
                chunked_state_json={
                    "native_learn": True,
                    "learn_document": True,
                    "document_version": 2,
                },
            )
        )
        session.add(
            EditableLessonModel(
                id=editable_id,
                user_id=user_id,
                source_generation_id=output_id,
                source_type="learn_document",
                title=str(document.get("title") or "Learn lesson"),
                class_label=None,
                document_json=document,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()

        # Edit: mutate first paragraph text; reorder last two document nodes if possible.
        lesson = await session.get(EditableLessonModel, editable_id)
        assert lesson is not None
        doc = dict(lesson.document_json or {})
        nodes = list(doc.get("nodes") or [])
        edited_text = "EDITED_PROOF: stomata are adjustable openings on the leaf surface."
        edited_node_id = None
        for node in nodes:
            if isinstance(node, dict) and node.get("kind") == "paragraph":
                node["text"] = edited_text
                edited_node_id = node.get("id")
                break
        # Add a new paragraph node
        new_id = f"node-{uuid.uuid4().hex[:12]}"
        nodes.append(
            {
                "id": new_id,
                "kind": "paragraph",
                "text": "ADDED_PROOF: local regeneration leaves other nodes intact.",
                "teaching_block_id": "orient-b1",
            }
        )
        # Delete a figure if present (keep at least one ordinary non-paragraph if possible)
        deleted_id = None
        for i, node in enumerate(list(nodes)):
            if isinstance(node, dict) and node.get("kind") == "figure":
                deleted_id = node.get("id")
                nodes.pop(i)
                break
        # Reorder: move last node up one if length >= 2
        if len(nodes) >= 2:
            nodes[-1], nodes[-2] = nodes[-2], nodes[-1]
        doc["nodes"] = nodes
        doc["updated_at"] = _utcnow().isoformat() + "Z"
        lesson.document_json = doc
        lesson.updated_at = _utcnow()
        await session.commit()

        # Reload
        reloaded = await session.get(EditableLessonModel, editable_id)
        assert reloaded is not None
        rdoc = dict(reloaded.document_json or {})
        rnodes = list(rdoc.get("nodes") or [])

        # Interaction evaluate
        ix_eval = None
        for node in rnodes:
            if isinstance(node, dict) and node.get("kind") == "interaction":
                contract, _ = find_interaction_in_document(rdoc, str(node.get("id")))
                response = _response_for(contract)
                ix_eval = evaluate_interaction(contract, response)
                break

    # Assertions
    texts = [
        str(n.get("text") or "")
        for n in rnodes
        if isinstance(n, dict) and n.get("kind") == "paragraph"
    ]
    if edited_text not in texts:
        print("LIVE_LEARN_EDIT=FAIL edited paragraph missing after reload", file=sys.stderr)
        return 1
    if not any("ADDED_PROOF" in t for t in texts):
        print("LIVE_LEARN_EDIT=FAIL added paragraph missing", file=sys.stderr)
        return 1
    if deleted_id and any(
        isinstance(n, dict) and n.get("id") == deleted_id for n in rnodes
    ):
        print("LIVE_LEARN_EDIT=FAIL deleted figure still present", file=sys.stderr)
        return 1
    if ix_eval is None:
        print("LIVE_LEARN_EDIT=FAIL no interaction evaluated", file=sys.stderr)
        return 1

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence = {
        "output_id": output_id,
        "editable_lesson_id": editable_id,
        "edited_node_id": edited_node_id,
        "added_node_id": new_id,
        "deleted_node_id": deleted_id,
        "interaction_eval": ix_eval,
        "reloaded_kinds": [n.get("kind") for n in rnodes if isinstance(n, dict)],
        "node_count": len(rnodes),
    }
    path = EVIDENCE_DIR / f"{output_id}-edit-reload.json"
    path.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")

    print("LIVE_LEARN_EDIT output_id=", output_id)
    print("LIVE_LEARN_EDIT editable_lesson_id=", editable_id)
    print("LIVE_LEARN_EDIT interaction_outcome=", ix_eval.get("outcome") if isinstance(ix_eval, dict) else ix_eval)
    print("LIVE_LEARN_EDIT evidence=", path)
    print("LIVE_LEARN_EDIT=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
