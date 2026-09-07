from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import (
    GenerationModel,
    LearningPackModel,
    LessonProvenanceModel,
    PathLessonModel,
    PathVersionModel,
    UnitModel,
)


@dataclass(frozen=True)
class LessonPreparationLinkage:
    """The persisted records that make a prepared path lesson usable."""

    generation: GenerationModel | None
    provenance: LessonProvenanceModel | None
    learning_pack: LearningPackModel | None
    source_pack_id: str | None
    reason: str | None = None

    @property
    def complete(self) -> bool:
        return self.reason is None and self.generation is not None and self.provenance is not None

    @property
    def stale(self) -> bool:
        return self.reason == "Preparation is stale"


async def resolve_lesson_preparation(
    session: AsyncSession,
    *,
    unit: UnitModel,
    version: PathVersionModel,
    lesson: PathLessonModel,
) -> LessonPreparationLinkage:
    """Resolve and validate the complete path-lesson preparation chain.

    A canonical preparation stores pack-owned artifacts under the coordinator
    generation itself. Differentiated preparations additionally point at a
    LearningPackModel through ``GenerationModel.pack_id``.
    """

    if not lesson.pack_id:
        return LessonPreparationLinkage(
            generation=None,
            provenance=None,
            learning_pack=None,
            source_pack_id=None,
            reason="Lesson is not prepared",
        )

    generation = await session.get(GenerationModel, lesson.pack_id)
    if generation is None:
        return LessonPreparationLinkage(
            generation=None,
            provenance=None,
            learning_pack=None,
            source_pack_id=None,
            reason="Preparation generation is missing",
        )
    if generation.user_id != unit.owner_id or generation.subject != unit.subject:
        return LessonPreparationLinkage(
            generation=generation,
            provenance=None,
            learning_pack=None,
            source_pack_id=None,
            reason="Preparation generation does not belong to this unit",
        )

    provenance = await session.get(LessonProvenanceModel, generation.id)
    if provenance is None:
        return LessonPreparationLinkage(
            generation=generation,
            provenance=None,
            learning_pack=None,
            source_pack_id=None,
            reason="Preparation provenance is missing",
        )
    if provenance.invalidated_at is not None:
        return LessonPreparationLinkage(
            generation=generation,
            provenance=provenance,
            learning_pack=None,
            source_pack_id=None,
            reason="Preparation is stale",
        )
    if (
        provenance.path_version_id != version.id
        or provenance.path_lesson_id != lesson.id
        or provenance.concept_id != lesson.concept_id
        or provenance.objective_hash != lesson.objective_hash
        or provenance.path_lesson_revision != lesson.revision
    ):
        return LessonPreparationLinkage(
            generation=generation,
            provenance=provenance,
            learning_pack=None,
            source_pack_id=None,
            reason="Preparation is stale",
        )

    learning_pack: LearningPackModel | None = None
    source_pack_id = generation.pack_id or generation.id
    if generation.pack_id:
        learning_pack = await session.get(LearningPackModel, generation.pack_id)
        if learning_pack is None:
            return LessonPreparationLinkage(
                generation=generation,
                provenance=provenance,
                learning_pack=None,
                source_pack_id=None,
                reason="Preparation learning pack is missing",
            )
        if learning_pack.user_id != unit.owner_id or learning_pack.subject != unit.subject:
            return LessonPreparationLinkage(
                generation=generation,
                provenance=provenance,
                learning_pack=learning_pack,
                source_pack_id=None,
                reason="Preparation learning pack does not belong to this unit",
            )

    return LessonPreparationLinkage(
        generation=generation,
        provenance=provenance,
        learning_pack=learning_pack,
        source_pack_id=source_pack_id,
    )
