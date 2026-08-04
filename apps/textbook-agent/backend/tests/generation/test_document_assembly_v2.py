"""Assemble/persist/reload LectioDocumentV2 without SectionContent."""

from __future__ import annotations

import json

from generation.page_objects.document_assembly import (
    assemble_document_v2,
    persist_document_json,
    reload_document,
    write_planned_section,
)
from planning.page_blocks import plan_conceptual_first_exposure_blocks
import pytest


@pytest.mark.asyncio
async def test_fixture_lesson_persists_and_reloads_equal() -> None:
    plans = await plan_conceptual_first_exposure_blocks(allow_paid=False)
    item_records = ({"id": "q-fixture-1", "prompt": "Why no food in dark?", "answer": "No light"},)
    sections = []
    for slot_id, plan in plans.items():
        section, _ = write_planned_section(
            section_id=slot_id,
            title=slot_id.replace("-", " ").title(),
            plan=plan,
            item_records=item_records,
        )
        sections.append(section)

    document = assemble_document_v2(
        title="Why Plants Need Light to Make Food",
        sections=sections,
        document_id="lesson-photosynthesis-light",
    )
    assert document["document_version"] == 2
    assert "SectionContent" not in json.dumps(document)

    envelope = persist_document_json(None, document)
    reloaded = reload_document(envelope)
    assert reloaded["id"] == document["id"]
    assert reloaded["sections"] == document["sections"]


def test_v2_path_does_not_import_section_content() -> None:
    import generation.page_objects.document_assembly as mod

    source = open(mod.__file__, encoding="utf-8").read()
    assert "SectionContent" not in source or "must not" in source
    assert "from contracts.section_content" not in source
