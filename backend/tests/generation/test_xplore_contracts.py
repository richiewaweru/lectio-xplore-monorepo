from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from core.database.models import (
    ConceptCardModel,
    GenerationModel,
    LearningPackModel,
    PackItemModel,
    UserModel,
)
from core.database.session import async_session_factory
from generation.v3_studio.router import (
    _chunked_stage2_tasks,
    _ensure_chunked_generation_row,
    _run_pack_variant_pipeline,
    _with_shared_pack_assessment,
)
from v3_blueprint.planning.models import (
    AnchorSpec,
    ComponentSlot,
    ConceptCard,
    LessonIntent,
    Misconception,
    SectionPlan,
    StructuralPlan,
    VariantSpec,
    VoiceSpec,
)
from v3_blueprint.planning.persistence import (
    load_chunked_state,
    persist_chunked_state,
    persist_structural_plan,
)


def _plan(*, objective: str = "Identify the inputs to photosynthesis.") -> StructuralPlan:
    return StructuralPlan(
        lesson_mode="first_exposure",
        lesson_intent=LessonIntent(
            goal="Explain photosynthesis.",
            structure_rationale="Move from inputs to explanation.",
        ),
        anchor=AnchorSpec(
            example="A leaf in sunlight",
            reuse_scope="Use the same leaf throughout.",
        ),
        prior_knowledge=[],
        cards=[
            ConceptCard(
                id="biology.photosynthesis.inputs",
                title="Inputs",
                objective=objective,
                misconceptions=[
                    Misconception(
                        id="M1",
                        description="Plants get their food directly from soil.",
                    )
                ],
            )
        ],
        sections=[
            SectionPlan(
                id="inputs",
                title="Inputs",
                role="explain",
                card_id="biology.photosynthesis.inputs",
                visual_required=False,
                components=[
                    ComponentSlot(
                        slug="explanation-block",
                        purpose="Explain the inputs.",
                    )
                ],
            )
        ],
        question_plan=[],
        answer_key_style="brief_explanations",
    )


def _form_context() -> dict:
    return {
        "signals": {
            "topic": "Photosynthesis",
            "subtopic": None,
            "prior_knowledge": [],
            "learner_needs": [],
            "teacher_goal": "Explain photosynthesis",
            "inferred_lesson_mode": "first_exposure",
            "lesson_mode_confidence": "high",
        },
        "form": {
            "grade_level": "Form 2",
            "subject": "Biology",
            "duration_minutes": 45,
            "resource_type": "lesson",
            "topic": "Photosynthesis",
            "subtopics": [],
            "prior_knowledge": "",
            "outcome": "Explain photosynthesis.",
            "struggle": "",
            "learner_level": "on_grade",
            "reading_level": "on_grade",
            "language_support": "none",
            "prior_knowledge_level": "new_topic",
            "free_text": "",
        },
        "resource_spec": {"resource_type": "lesson"},
    }


@pytest.mark.asyncio
async def test_variant_failure_is_isolated_from_siblings() -> None:
    state = {
        "pack_id": "pack-isolation",
        "structural_plan": _plan().model_dump(mode="json"),
        "variants": [
            {
                "label": "Support",
                "group_description": "More scaffolding.",
                "voice": {
                    "register_name": "simple",
                    "tone": "encouraging",
                    "notation": None,
                },
            }
        ],
        "context": _form_context(),
    }
    persisted = AsyncMock()
    run_variant = AsyncMock(
        side_effect=[RuntimeError("support failed"), None],
    )
    with (
        patch(
            "generation.v3_studio.router.load_chunked_state",
            new=AsyncMock(return_value=state),
        ),
        patch(
            "generation.v3_studio.router._generate_shared_pack_items",
            new=AsyncMock(return_value={"pack_id": "pack-isolation"}),
        ),
        patch(
            "generation.v3_studio.router._run_chunked_stage2_pipeline",
            new=run_variant,
        ),
        patch(
            "generation.v3_studio.router.persist_chunked_state",
            new=persisted,
        ),
    ):
        await _run_pack_variant_pipeline(
            coordinator_id="coordinator",
            user_id="teacher",
            generation_ids={"Support": "variant-a", "Core": "variant-b"},
        )

    assert run_variant.await_count == 2
    final_patch = persisted.await_args_list[-1].args[1]
    assert final_patch["stage"] == "variants_running"
    assert final_patch["variant_failures"] == {"variant-a": "support failed"}


@pytest.mark.asyncio
async def test_all_variants_derive_one_shared_pack_item_set() -> None:
    suffix = uuid.uuid4().hex
    user_id = f"xplore-shared-user-{suffix}"
    pack_id = f"xplore-shared-pack-{suffix}"
    card_id = f"{pack_id}:biology.photosynthesis.inputs"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="Shared Quiz",
            )
        )
        session.add(
            LearningPackModel(
                id=pack_id,
                user_id=user_id,
                learning_job_type="xplore_variants",
                subject="Biology",
                topic="Photosynthesis",
                pack_plan_json='{"resources":[]}',
                resource_count=2,
            )
        )
        await session.commit()
    variants = [
        VariantSpec(
            label="Support",
            group_description="More scaffolding.",
            voice=VoiceSpec(register_name="simple", tone="encouraging"),
        ),
        VariantSpec(
            label="Extension",
            group_description="More concise challenge.",
            voice=VoiceSpec(register_name="formal", tone="direct"),
        ),
    ]
    generation_ids = []
    for index, variant in enumerate(variants):
        generation_id = f"xplore-shared-gen-{index}-{suffix}"
        generation_ids.append(generation_id)
        await _ensure_chunked_generation_row(
            generation_id=generation_id,
            user_id=user_id,
            subject="Biology",
            context=variant.label,
            pack_id=pack_id,
            pack_resource_id=f"variant-{index + 1}",
            pack_resource_label=variant.label,
            variant=variant,
        )
    async with async_session_factory() as session:
        session.add(
            ConceptCardModel(
                id=card_id,
                pack_id=pack_id,
                slug="biology.photosynthesis.inputs",
                title="Inputs",
                objective="Identify the inputs.",
                prereqs=[],
                misconceptions=[
                    {
                        "id": "M1",
                        "description": "Plants get food from soil.",
                        "source": "drafted",
                    }
                ],
            )
        )
        session.add(
            PackItemModel(
                id=f"{pack_id}:q1",
                pack_id=pack_id,
                card_id=card_id,
                stem="Which inputs are required?",
                options=[
                    {
                        "key": "a",
                        "text": "Carbon dioxide and water",
                        "correct": True,
                        "diagnoses": None,
                    },
                    {
                        "key": "b",
                        "text": "Soil and sunlight",
                        "correct": False,
                        "diagnoses": "M1",
                    },
                ],
                correct_key="a",
                diagnoses={"a": None, "b": "M1"},
            )
        )
        await session.commit()
        models = [
            await session.get(GenerationModel, generation_id)
            for generation_id in generation_ids
        ]

    documents = [
        await _with_shared_pack_assessment(
            model,
            {"sections": [{"section_id": "lesson"}]},
        )
        for model in models
        if model is not None
    ]
    assert len(documents) == 2
    assert documents[0]["shared_quiz_pack_id"] == pack_id
    assert documents[1]["shared_quiz_pack_id"] == pack_id
    assert documents[0]["sections"][1:] == documents[1]["sections"][1:]
    assert documents[0]["answer_key"] == documents[1]["answer_key"]
    async with async_session_factory() as session:
        item_pack_ids = set(
            (
                await session.execute(
                    select(PackItemModel.pack_id).where(
                        PackItemModel.card_id == card_id
                    )
                )
            ).scalars()
        )
    assert item_pack_ids == {pack_id}


@pytest.mark.asyncio
async def test_teacher_edited_misconceptions_survive_plan_regeneration() -> None:
    suffix = uuid.uuid4().hex
    user_id = f"xplore-preserve-user-{suffix}"
    generation_id = f"xplore-preserve-gen-{suffix}"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="Preserve Teacher",
            )
        )
        await session.commit()
    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=user_id,
        subject="Biology",
        context="Photosynthesis",
    )
    await persist_structural_plan(generation_id, _plan())
    async with async_session_factory() as session:
        card = (
            await session.execute(
                select(ConceptCardModel).where(
                    ConceptCardModel.pack_id == generation_id
                )
            )
        ).scalar_one()
        card.misconceptions = [
            {
                "id": "M99",
                "description": "Teacher-observed belief.",
                "source": "teacher",
            }
        ]
        card.teacher_edited = True
        await session.commit()

    await persist_structural_plan(
        generation_id,
        _plan(objective="A regenerated objective that must not overwrite edits."),
    )
    state = await load_chunked_state(generation_id)
    persisted_card = state["structural_plan"]["cards"][0]
    assert persisted_card["misconceptions"] == [
        {
            "id": "M99",
            "description": "Teacher-observed belief.",
            "source": "teacher",
        }
    ]
    async with async_session_factory() as session:
        stored = (
            await session.execute(
                select(ConceptCardModel).where(
                    ConceptCardModel.pack_id == generation_id
                )
            )
        ).scalar_one()
        assert stored.misconceptions[0]["id"] == "M99"


@pytest.mark.asyncio
async def test_awaiting_review_halt_survives_process_restart() -> None:
    suffix = uuid.uuid4().hex
    user_id = f"xplore-restart-user-{suffix}"
    generation_id = f"xplore-restart-gen-{suffix}"
    async with async_session_factory() as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                name="Restart Teacher",
            )
        )
        await session.commit()
    await _ensure_chunked_generation_row(
        generation_id=generation_id,
        user_id=user_id,
        subject="Biology",
        context="Photosynthesis",
    )
    await persist_structural_plan(generation_id, _plan())
    await persist_chunked_state(
        generation_id,
        {
            "stage": "awaiting_review",
            "approval_required": True,
            "approved": False,
        },
    )

    # Simulate a clean worker process after restart: no in-memory execution task.
    _chunked_stage2_tasks.clear()
    restored = await load_chunked_state(generation_id)

    assert restored["stage"] == "awaiting_review"
    assert restored["approval_required"] is True
    assert restored["approved"] is False
    assert generation_id not in _chunked_stage2_tasks
