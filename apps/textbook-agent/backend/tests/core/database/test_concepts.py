from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from core.database.models import (
    ConceptCardModel,
    ConceptModel,
    LessonProvenanceModel,
    UserModel,
)


@pytest.mark.asyncio
async def test_concept_slug_is_canonical_and_unique(db_session) -> None:
    db_session.add(UserModel(id="teacher-1", email="teacher@example.com"))
    db_session.add_all(
        [
            ConceptModel(
                id="concept-1",
                canonical_slug="biology.photosynthesis.inputs",
                subject="Biology",
                title="Inputs to photosynthesis",
                created_by="teacher-1",
            ),
            ConceptModel(
                id="concept-2",
                canonical_slug="biology.photosynthesis.inputs",
                subject="Biology",
                title="Renamed duplicate",
                created_by="teacher-1",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_card_and_provenance_concept_references_are_nullable_for_legacy_rows(
    db_session,
) -> None:
    card = ConceptCardModel(
        id="pack-1:legacy.card",
        pack_id="pack-1",
        slug="legacy.card",
        title="Legacy card",
        objective="Identify the legacy fact.",
        prereqs=[],
        misconceptions=[],
        canonical_concept_id=None,
    )
    provenance = LessonProvenanceModel(pack_id="pack-1")
    db_session.add_all([card, provenance])

    await db_session.commit()

    assert card.canonical_concept_id is None
    assert provenance.concept_id is None
    assert provenance.objective_hash is None
    assert provenance.skeleton_id is None
    assert provenance.toggles_applied is None
    assert provenance.deviations_applied is None
