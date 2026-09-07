"""Unit-path generation admission / dispatch after prepare.

Owned by application.unit_lesson (D1). Historical application.unit_lesson
is a temporary re-export shim.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel, LessonProvenanceModel
from learn.generation.pipeline_dispatch import build_control_patch, select_default_pipeline
from learn.generation.contracts import GenerationInputForm as V3InputForm
from learn.generation.contracts import GenerationSignalSummary as V3SignalSummary
from resource_specs.loader import get_spec
from resource_specs.renderer import render_spec_for_prompt
from v3_blueprint.planning.models import StructuralPlan, VariantSpec
from v3_blueprint.planning.objective_ownership import hash_path_objective
from v3_blueprint.planning.persistence import (
    load_chunked_state,
    persist_chunked_state,
    persist_structural_plan,
)


def _path_resource_spec() -> dict[str, Any]:
    spec = get_spec("lesson")
    return {
        "resource_type": "lesson",
        "depth": "standard",
        "spec": spec.model_dump(mode="json"),
        "rendered": render_spec_for_prompt(
            spec,
            depth="standard",
            active_roles=[],
            active_supports=[],
        ),
    }


def _scope_note(scope_contract: dict[str, Any]) -> str:
    terminology = [str(item) for item in scope_contract.get("terminology", [])]
    exclusions = [str(item) for item in scope_contract.get("must_not_introduce", [])]
    notation = scope_contract.get("notation")
    lines = [
        "This lesson is owned by an approved unit path; preserve its exact objective and scope."
    ]
    if terminology:
        lines.append(f"Use unit terminology exactly: {', '.join(terminology)}.")
    if notation:
        lines.append(f"Use unit notation exactly: {notation}.")
    if exclusions:
        lines.append(f"Do not introduce: {', '.join(exclusions)}.")
    return "\n".join(lines)


async def initialise_path_generation(
    session: AsyncSession,
    *,
    generation: GenerationModel,
    plan: StructuralPlan,
    concept_id: str,
    topic: str,
    grade_level: str,
    subject: str,
    lesson_mode: str,
    prior_established: list[str],
    scope_contract: dict[str, Any],
    variants: list[VariantSpec] | None = None,
    variant_plans: dict[str, StructuralPlan] | None = None,
    native_whole_lesson: bool = False,
    path_plan_raw: str | None = None,
) -> None:
    signals = V3SignalSummary(
        topic=topic,
        prior_knowledge=prior_established,
        learner_needs=[],
        teacher_goal=plan.cards[0].objective,
        inferred_lesson_mode=lesson_mode,
        lesson_mode_confidence="high",
    )
    form = V3InputForm(
        grade_level=grade_level,
        subject=subject,
        duration_minutes=45,
        resource_type="lesson",
        topic=topic,
        subtopics=[plan.cards[0].title],
        prior_knowledge="; ".join(prior_established),
        outcome=plan.cards[0].objective,
        prior_knowledge_level="some_background" if prior_established else "new_topic",
        free_text=_scope_note(scope_contract),
    )
    await persist_structural_plan(
        generation.id,
        plan,
        session,
        signals=signals,
        form=form,
        resource_spec=_path_resource_spec(),
    )
    state: dict[str, Any] = {
        "stage": "awaiting_review",
        "display_title": plan.cards[0].title,
        "execution_started": False,
        "path_prepared": True,
        # Units owns admission. Select once and persist before any later state merge.
        **build_control_patch(select_default_pipeline()),
    }
    if native_whole_lesson:
        # Print Unit path: native approve gate reads these from chunked state.
        # Do not write state["context"] here — persist_structural_plan already
        # stored form/signals/resource_spec under context; a shallow
        # persist_chunked_state update would clobber them and break Learn launch.
        state["native_whole_lesson"] = True
        state["page_document_v2"] = True
    if path_plan_raw:
        state["path_plan_raw"] = path_plan_raw
    if variants:
        state.update(
            {
                "pack_id": generation.pack_id,
                "variants": [variant.model_dump(mode="json") for variant in variants],
                "variant_structural_plans": {
                    label: variant_plan.model_dump(mode="json")
                    for label, variant_plan in (variant_plans or {}).items()
                },
            }
        )
    await persist_chunked_state(
        generation.id,
        state,
        session,
    )
    if native_whole_lesson:
        # Merge the Print flag into the preserved Learn/Print context blob.
        current = await load_chunked_state(generation.id, session)
        ctx = dict(current.get("context") or {})
        if ctx.get("native_whole_lesson") is not True:
            ctx["native_whole_lesson"] = True
            await persist_chunked_state(
                generation.id,
                {"context": ctx},
                session,
            )
    generation.status = "awaiting_review"
    card = await session.scalar(
        select(ConceptCardModel).where(
            ConceptCardModel.pack_id == (generation.pack_id or generation.id),
            ConceptCardModel.slug == concept_id,
        )
    )
    if card is None:
        raise ValueError("Path preparation did not persist its concept card")
    card.canonical_concept_id = concept_id


async def enforce_path_owned_card_objective(
    session: AsyncSession,
    *,
    pack_id: str,
    objective: str,
) -> None:
    provenance = await session.get(LessonProvenanceModel, pack_id)
    if provenance is None or provenance.path_lesson_id is None:
        return
    if provenance.objective_hash != hash_path_objective(objective):
        raise ValueError("A path-prepared lesson cannot rewrite its approved objective")


__all__ = ["enforce_path_owned_card_objective", "initialise_path_generation"]
