"""Recipe slots must stay inside the lesson resource spec vocabulary."""
from __future__ import annotations

from copy import deepcopy

import pytest

from curriculum.planning.skeletons import (
    SkeletonCatalog,
    SkeletonCatalogError,
    load_skeleton_catalog,
    validate_skeletons_against_spec,
)
from print.contracts.lectio_page import get_intent_catalogue
from resource_specs.loader import get_spec, load_all_specs


@pytest.fixture()
def lesson_spec():
    load_all_specs()
    return get_spec("lesson")


@pytest.fixture()
def intents() -> dict:
    return get_intent_catalogue()["intents"]


def _catalog_with_slot_intents(slot_id: str, typical: list[str]) -> SkeletonCatalog:
    data = deepcopy(load_skeleton_catalog().data)
    data["slots"][slot_id]["typical_intents"] = {"core": typical, "optional": []}
    return SkeletonCatalog(data)


def test_real_files_pass(lesson_spec, intents) -> None:
    validate_skeletons_against_spec(load_skeleton_catalog(), lesson_spec, intents)


def test_excluded_intent_is_reported_with_slot_and_intent(lesson_spec, intents) -> None:
    excluded = lesson_spec.vocabulary.intents.excluded
    assert "transfer" in excluded
    catalog = _catalog_with_slot_intents("explain", ["explain", "transfer"])
    with pytest.raises(SkeletonCatalogError) as exc:
        validate_skeletons_against_spec(catalog, lesson_spec, intents)
    message = str(exc.value)
    assert "slot 'explain'" in message
    assert "intent 'transfer'" in message


def test_intent_missing_from_catalogue_is_reported(lesson_spec, intents) -> None:
    catalog = _catalog_with_slot_intents("explain", ["explain", "no-such-intent"])
    with pytest.raises(SkeletonCatalogError, match="no-such-intent.*not in intent catalogue"):
        validate_skeletons_against_spec(catalog, lesson_spec, intents)


def test_toggle_inserted_slots_are_checked(lesson_spec, intents) -> None:
    reachable = load_skeleton_catalog().all_reachable_slots()
    for slot_id in ("confront", "model", "contrast", "apply"):
        assert slot_id in reachable


def test_knowledge_type_guidance() -> None:
    catalog = load_skeleton_catalog()
    conceptual = catalog.knowledge_type_guidance("conceptual")
    assert conceptual is not None and conceptual.demands
    assert conceptual.teacher_label
    assert catalog.knowledge_type_guidance("any") is None


def test_catalog_rejects_knowledge_type_without_demands() -> None:
    data = deepcopy(load_skeleton_catalog().data)
    del data["knowledge_types"]["conceptual"]["demands"]
    with pytest.raises(SkeletonCatalogError, match="conceptual.demands"):
        SkeletonCatalog(data)
