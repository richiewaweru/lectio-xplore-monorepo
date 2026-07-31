from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import ConceptCardModel, GenerationModel, LessonProvenanceModel
from generation.v3_studio.dtos import V3InputForm, V3SignalSummary
from resource_specs.loader import get_spec
from resource_specs.renderer import render_spec_for_prompt
from v3_blueprint.planning.models import StructuralPlan
from v3_blueprint.planning.objective_ownership import hash_path_objective
from v3_blueprint.planning.persistence import persist_chunked_state, persist_structural_plan


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
    lines = ["This lesson is owned by an approved unit path; preserve its exact objective and scope."]
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
    await persist_chunked_state(
        generation.id,
        {
            "stage": "awaiting_review",
            "display_title": plan.cards[0].title,
            "execution_started": False,
            "path_prepared": True,
        },
        session,
    )
    generation.status = "awaiting_review"
    card = await session.scalar(
        select(ConceptCardModel).where(
            ConceptCardModel.pack_id == generation.id,
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
