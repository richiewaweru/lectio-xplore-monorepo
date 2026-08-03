"""Phase 0 expander A/B: same structural plan, flag off then on.

Uses a fixed StructuralPlan (practice/apply + check) so both arms share an identical
lesson shape. Stage 1 live calls were flaky on skeleton role validation; the expander
question is Stage 2 → writer, so a fixed plan is the fairer comparison.

Saves outputs under experiments/expander/{with_expander,skip_expander}/.
Run from repo root:
  uv run --directory backend python ../experiments/expander/run_ab.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
OUT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND / "src"))

load_dotenv(REPO_ROOT / ".env", override=True)
os.environ.setdefault("V3_STAGE2_PARALLEL", "true")
local_contracts = BACKEND / "contracts"
if local_contracts.exists():
    os.environ["LECTIO_CONTRACTS_DIR"] = str(local_contracts)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _lesson_inputs():
    from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
    from generation.v3_studio.router import _build_chunked_resource_spec

    form = V3InputForm(
        grade_level="Grade 7",
        subject="Science",
        duration_minutes=45,
        resource_type="lesson",
        topic="Photosynthesis",
        subtopics=["chlorophyll", "glucose", "gas exchange"],
        prior_knowledge="Plants need sunlight and water.",
        outcome="Students can explain how plants convert light energy into chemical energy.",
        struggle="Students think plants eat soil and that photosynthesis is the opposite of breathing.",
        learner_level="on_grade",
        reading_level="on_grade",
        language_support="none",
        prior_knowledge_level="some_background",
        free_text="Include practice and a check section. Prefer diagram only if essential.",
    )
    signals = V3SignalSummary(
        topic="Photosynthesis",
        subtopic="Energy conversion in plants",
        prior_knowledge=["plants need sunlight", "plants need water"],
        learner_needs=[],
        teacher_goal="Explain photosynthesis as energy conversion and target the soil-food misconception.",
        inferred_lesson_mode="first_exposure",
        lesson_mode_confidence="high",
    )
    resource_spec = _build_chunked_resource_spec(
        resource_type="lesson",
        duration_minutes=45,
    )
    return signals, form, resource_spec


def _photosynthesis_plan():
    """Fixed plan with apply (practice) + check; no visual_required sections."""
    from v3_blueprint.planning.models import (
        AnchorSpec,
        ComponentSlot,
        ConceptCard,
        LessonIntent,
        Misconception,
        QPlanItem,
        SectionPlan,
        StructuralPlan,
        VariantSpec,
        VoiceSpec,
    )

    plan = StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="Explain photosynthesis as converting light energy into chemical energy stored in glucose.",
            structure_rationale="Orient → explain → model → apply → check, targeting the soil-food misconception.",
        ),
        anchor=AnchorSpec(
            example="A sunny windowsill plant making glucose from light, water, and CO2.",
            reuse_scope="all sections",
        ),
        prior_knowledge=["plants need sunlight", "plants need water"],
        cards=[
            ConceptCard(
                id="photosynthesis.energy_conversion",
                title="Photosynthesis as energy conversion",
                objective="Explain that plants convert light energy into chemical energy stored in glucose.",
                prereqs=["plants need sunlight", "plants need water"],
                misconceptions=[
                    Misconception(
                        id="M1",
                        description="Plants get their food by absorbing nutrients from soil.",
                        source="drafted",
                    ),
                    Misconception(
                        id="M2",
                        description="Photosynthesis is just the opposite of breathing / animals breathe out what plants breathe in.",
                        source="drafted",
                    ),
                ],
                opens_by="Start from the windowsill plant and ask where its energy comes from.",
            )
        ],
        sections=[
            SectionPlan(
                id="orient",
                title="Where does a plant's energy come from?",
                role="orient",
                card_id="photosynthesis.energy_conversion",
                visual_required=False,
                transition_note=None,
                components=[
                    ComponentSlot(
                        slug="hook-hero",
                        purpose="Open with the windowsill plant and surface the soil-food idea without resolving it yet.",
                    )
                ],
            ),
            SectionPlan(
                id="explain",
                title="Light to chemical energy",
                role="explain",
                card_id="photosynthesis.energy_conversion",
                visual_required=False,
                transition_note="After the hook, name the conversion: light energy becomes chemical energy in glucose.",
                components=[
                    ComponentSlot(
                        slug="callout-block",
                        purpose="State that photosynthesis converts light energy into chemical energy stored in glucose; exclude soil-as-food.",
                    ),
                    ComponentSlot(
                        slug="definition-card",
                        purpose="Define photosynthesis with inputs (light, water, CO2) and output (glucose + oxygen).",
                    ),
                ],
            ),
            SectionPlan(
                id="model",
                title="Trace the windowsill example",
                role="model",
                card_id="photosynthesis.energy_conversion",
                visual_required=False,
                transition_note="Apply the definition to the same windowsill plant step by step.",
                components=[
                    ComponentSlot(
                        slug="worked-example-card",
                        purpose="Walk the windowsill plant through light → chlorophyll → glucose, contrasting soil nutrients vs food energy.",
                    )
                ],
            ),
            SectionPlan(
                id="apply",
                title="Practice the conversion story",
                role="apply",
                card_id="photosynthesis.energy_conversion",
                visual_required=False,
                transition_note="Learners try the conversion story on a new plant context after the model.",
                components=[
                    ComponentSlot(
                        slug="practice-stack",
                        purpose="Prompt learners to explain energy conversion for a shaded vs sunny plant without inventing new science.",
                    )
                ],
            ),
            SectionPlan(
                id="check",
                title="Check understanding",
                role="check",
                card_id="photosynthesis.energy_conversion",
                visual_required=False,
                transition_note="Close with a check that targets M1 soil-food and M2 breathing-opposite ideas.",
                components=[
                    ComponentSlot(
                        slug="quiz-check",
                        purpose="Ask one check that forces a choice between soil-food and light-to-glucose conversion.",
                    )
                ],
            ),
        ],
        question_plan=[
            QPlanItem(question_id="q-warm-1", section_id="orient", temperature="warm", diagram_required=False),
            QPlanItem(question_id="q-med-1", section_id="apply", temperature="medium", diagram_required=False),
            QPlanItem(question_id="q-cold-1", section_id="check", temperature="cold", diagram_required=False),
        ],
        answer_key_style="brief_explanations",
    )
    return plan.with_variant(
        VariantSpec(
            label="Everyone",
            voice=VoiceSpec(register_name="balanced", tone="encouraging", notation=None),
            group_description="Whole-class version for the expander A/B.",
        )
    )


async def _noop_emit(_name: str, _payload: dict) -> None:
    return None


async def _run_arm(
    *,
    label: str,
    skip: bool,
    plan,
    signals,
    form,
    resource_spec: dict,
) -> dict:
    from v3_blueprint.planning.assembler import assemble_blueprint
    from v3_blueprint.planning.retry import run_stage2
    from v3_execution.compile_orders import compile_execution_bundle
    from v3_execution.executors.section_writer import execute_section

    os.environ["V3_SKIP_EXPANDER"] = "true" if skip else "false"
    arm_dir = OUT_DIR / label
    arm_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    briefs = await run_stage2(
        plan,
        signals,
        form,
        resource_spec,
        generation_id=None,
        emit_event=_noop_emit,
    )
    t_stage2 = time.perf_counter() - t0

    blueprint = assemble_blueprint(
        plan,
        briefs,
        title="Photosynthesis",
        subject="Science",
        resource_type="lesson",
        ship_with_holes=True,
    )
    bundle = compile_execution_bundle(
        blueprint,
        generation_id=f"expander-ab-{label}",
        blueprint_id=f"bp-{label}",
        template_id="guided-concept-path",
    )

    prose: dict[str, object] = {}
    section_timings: dict[str, float] = {}
    t_writers_start = time.perf_counter()
    for order in bundle.section_orders:
        st = time.perf_counter()
        blocks = await execute_section(
            order,
            _noop_emit,
            trace_id=str(uuid.uuid4()),
            generation_id=f"expander-ab-{label}",
        )
        section_timings[order.section.id] = time.perf_counter() - st
        prose[order.section.id] = {
            "title": order.section.title,
            "role": order.section.role,
            "transition_note": order.section.transition_note,
            "learning_intent": order.section.learning_intent,
            "components": [
                {
                    "component_id": c.component_id,
                    "content_intent": c.content_intent,
                }
                for c in order.section.components
            ],
            "blocks": [b.model_dump(mode="json") for b in blocks],
        }
    t_writers = time.perf_counter() - t_writers_start
    t_total = time.perf_counter() - t0

    brief_payload = []
    for brief in briefs:
        data = brief.model_dump(mode="json")
        data["_failed"] = bool(getattr(brief, "_failed", False))
        data["_errors"] = list(getattr(brief, "_errors", []) or [])
        brief_payload.append(data)

    timings = {
        "label": label,
        "skip_expander": skip,
        "stage2_seconds": round(t_stage2, 2),
        "writers_seconds": round(t_writers, 2),
        "section_writer_seconds": {k: round(v, 2) for k, v in section_timings.items()},
        "total_seconds": round(t_total, 2),
        "section_count": len(bundle.section_orders),
        "failed_briefs": [b["section_id"] for b in brief_payload if b.get("_failed")],
    }
    _write_json(arm_dir / "briefs.json", brief_payload)
    _write_json(arm_dir / "prose.json", prose)
    _write_json(arm_dir / "blueprint.json", blueprint.model_dump(mode="json"))
    _write_json(arm_dir / "timings.json", timings)
    return timings


async def main() -> int:
    from v3_blueprint.planning.models import StructuralPlan

    shared_path = OUT_DIR / "shared_plan.json"
    if not shared_path.exists():
        raise FileNotFoundError(
            f"Missing {shared_path}; round 1 shared plan is required for comparable arms."
        )
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    plan = StructuralPlan.model_validate(shared["plan"])
    # Restore variant voice if dumped without private attrs (defaults to Core).
    signals, form, resource_spec = _lesson_inputs()
    roles = [s.role for s in plan.sections]
    print(
        f"[AB v2] Loaded shared_plan.json roles={roles} "
        f"section_ids={[s.id for s in plan.sections]}",
        flush=True,
    )

    print("[AB v2] Arm A: expander ON -> with_expander_v2/", flush=True)
    timings_a = await _run_arm(
        label="with_expander_v2",
        skip=False,
        plan=plan,
        signals=signals,
        form=form,
        resource_spec=resource_spec,
    )
    print(f"[AB v2] Arm A timings={timings_a}", flush=True)

    print("[AB v2] Arm B: expander OFF -> skip_expander_v2/", flush=True)
    timings_b = await _run_arm(
        label="skip_expander_v2",
        skip=True,
        plan=plan,
        signals=signals,
        form=form,
        resource_spec=resource_spec,
    )
    print(f"[AB v2] Arm B timings={timings_b}", flush=True)

    summary = {
        "round": 2,
        "topic": "Photosynthesis",
        "plan_source": "shared_plan.json",
        "roles": roles,
        "has_practice_role": "apply" in roles,
        "has_check_like_role": "check" in roles,
        "with_expander_v2": timings_a,
        "skip_expander_v2": timings_b,
        "stage2_delta_seconds": round(
            timings_a["stage2_seconds"] - timings_b["stage2_seconds"], 2
        ),
        "total_delta_seconds": round(
            timings_a["total_seconds"] - timings_b["total_seconds"], 2
        ),
    }
    _write_json(OUT_DIR / "summary_v2.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
