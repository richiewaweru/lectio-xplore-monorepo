"""Live proof: LLM compose/write LearnDocument v2 + capture generation evidence.

Writes evidence JSON under docs/document-overhaul/reports/evidence/.
Persists to DB when available; otherwise records document-only evidence.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from curriculum.teaching_plan.models import (
    LearnerActionBrief,
    TeachingPlan,
    TeachingPlanBlock,
    TeachingPlanSection,
)
from infra.authoring import LLMAuthoringProvider
from learn.generation.native_production import produce_learn_document_from_teaching_async

EVIDENCE_DIR = (
    Path(__file__).resolve().parents[4]
    / "docs"
    / "document-overhaul"
    / "reports"
    / "evidence"
)


def _plan() -> TeachingPlan:
    return TeachingPlan(
        teaching_plan_id=f"tp-live-persist-{uuid.uuid4().hex[:8]}",
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
                        brief=(
                            "Orient with the leaf anchor. Introduce stomata as "
                            "adjustable openings without copying this brief."
                        ),
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
                            "Include a short warning callout about night myths."
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


async def main() -> int:
    provider = LLMAuthoringProvider(node_name="v3_block_writer_fast")
    plan = _plan()
    output_id = f"learn-out-{uuid.uuid4().hex[:12]}"
    editable_id = str(uuid.uuid4())

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
            allow_heuristic_composition_fallback=True,
        )
    finally:
        np.attach_figure_asset = original  # type: ignore[assignment]

    document = dict(production["document"])
    document["id"] = output_id
    document["source_generation_id"] = output_id
    nodes = document.get("nodes") or []
    kinds = [n.get("kind") for n in nodes if isinstance(n, dict)]
    has_paragraph = "paragraph" in kinds
    has_other = any(k in kinds for k in ("heading", "list", "figure", "table", "callout"))
    has_interaction = "interaction" in kinds
    placeholders = json.dumps(document).lower()
    bad = any(
        token in placeholders
        for token in ("content pending", "option a", "row 1", "item / detail")
    )

    db_status = "skipped"
    try:
        from core.database.models import EditableLessonModel, GenerationModel, UserModel
        from core.database.session import async_session_factory

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        user_id = f"correction-proof-{uuid.uuid4().hex[:8]}"
        async with async_session_factory() as session:
            session.add(
                UserModel(
                    id=user_id,
                    email=f"{user_id}@example.invalid",
                    name="Correction proof",
                )
            )
            session.add(
                GenerationModel(
                    id=output_id,
                    user_id=user_id,
                    subject="science",
                    context="correction persist proof",
                    status="completed",
                    requested_template_id="lesson",
                    requested_preset_id="standard",
                    created_at=now,
                    document_json=document,
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
                    document_json={**document, "id": editable_id},
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()
            reloaded = await session.get(EditableLessonModel, editable_id)
            assert reloaded is not None
            db_status = "persisted"
    except Exception as exc:  # noqa: BLE001
        db_status = f"unavailable:{type(exc).__name__}"

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    evidence_path = EVIDENCE_DIR / f"{output_id}.json"
    evidence_path.write_text(
        json.dumps(
            {
                "output_id": output_id,
                "editable_lesson_id": editable_id,
                "teaching_plan_id": plan.teaching_plan_id,
                "kinds": kinds,
                "db_status": db_status,
                "document": document,
                "composition_plan": (
                    production["composition_plan"].model_dump(mode="json")
                    if hasattr(production["composition_plan"], "model_dump")
                    else production["composition_plan"]
                ),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print("LIVE_LEARN_PERSIST output_id=", output_id)
    print("LIVE_LEARN_PERSIST editable_lesson_id=", editable_id)
    print("LIVE_LEARN_PERSIST kinds=", json.dumps(kinds))
    print("LIVE_LEARN_PERSIST db_status=", db_status)
    print("LIVE_LEARN_PERSIST evidence=", evidence_path)

    if not has_paragraph or not has_other:
        print("LIVE_LEARN_PERSIST=FAIL need paragraph + another primitive", file=sys.stderr)
        return 1
    if not has_interaction:
        print("LIVE_LEARN_PERSIST=FAIL missing interaction for select-one", file=sys.stderr)
        return 1
    if bad:
        print("LIVE_LEARN_PERSIST=FAIL placeholder content", file=sys.stderr)
        return 1

    print("LIVE_LEARN_PERSIST=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
