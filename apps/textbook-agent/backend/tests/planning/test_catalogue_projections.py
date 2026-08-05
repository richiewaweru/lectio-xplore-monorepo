"""Tests for catalogue projections and the object-free teaching barrier."""

from __future__ import annotations

from contracts.lectio_page import PAGE_OBJECT_IDS
from planning.catalogue_projections import (
    assert_teaching_guidance_has_no_object_ids,
    project_form_guidance,
    project_teaching_guidance,
    project_writer_contract,
)
from resource_specs.loader import get_spec, load_all_specs


def test_teaching_guidance_contains_no_page_object_ids() -> None:
    load_all_specs()
    spec = get_spec("lesson")
    assert spec.vocabulary is not None
    permitted = set(spec.vocabulary.intents.permitted)
    excluded = spec.vocabulary.intents.excluded
    projection = project_teaching_guidance(
        permitted_intent_ids=permitted,
        excluded_intents=excluded if isinstance(excluded, dict) else list(excluded),
    )
    assert_teaching_guidance_has_no_object_ids(projection)
    serialized = projection.serialize()
    assert "valid_objects" not in serialized
    assert "content_schema" not in serialized
    assert "worked-example" not in serialized
    assert "answer-key" not in serialized


def test_form_guidance_has_objects_but_no_writer_prompts() -> None:
    projection = project_form_guidance()
    assert projection.objects
    blob = str(projection.to_dict())
    assert "system_prompt" not in blob
    assert "You write the content" not in blob


def test_writer_contract_is_single_object() -> None:
    contract = project_writer_contract("prose")
    assert contract.object_id == "prose"
    assert "prose" in PAGE_OBJECT_IDS
