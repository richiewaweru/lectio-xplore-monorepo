"""Skeleton catalog remains for Unit path shape (HTTP preview retired in D3)."""
from __future__ import annotations

import logging

import pytest

from curriculum.planning.skeletons import (
    PLANNER_LESSON_MODES,
    SkeletonCatalogError,
    effective_lesson_mode,
    load_skeleton_catalog,
)


def test_versioned_catalog_loads_twelve_skeletons() -> None:
    catalog = load_skeleton_catalog()
    assert len(catalog.skeletons) == 12


def test_factual_consolidation_recipe_is_short_and_keeps_locked_check() -> None:
    skeleton = load_skeleton_catalog().skeleton_for("factual", "consolidation")
    assert skeleton["id"] == "factual.consolidation"
    slots = list(skeleton["slots"])
    assert len(slots) <= 6
    assert slots[-1] == "check"
    assert slots.count("check") == 1


def test_effective_lesson_mode() -> None:
    assert PLANNER_LESSON_MODES == ("first_exposure", "consolidation", "transfer")
    assert effective_lesson_mode(None) == "first_exposure"
    assert effective_lesson_mode("") == "first_exposure"
    assert effective_lesson_mode("nonsense") == "first_exposure"
    for mode in ("first_exposure", "consolidation", "transfer", "repair", "retrieval"):
        assert effective_lesson_mode(mode) == mode


def test_unknown_pair_for_known_type_falls_back_to_first_exposure(caplog) -> None:
    catalog = load_skeleton_catalog()
    with caplog.at_level(logging.WARNING, logger="curriculum.planning.skeletons"):
        skeleton = catalog.skeleton_for("factual", "repair")
    assert skeleton["id"] == "factual.first_exposure"
    assert "factual" in caplog.text and "repair" in caplog.text


def test_unknown_knowledge_type_still_raises() -> None:
    with pytest.raises(SkeletonCatalogError):
        load_skeleton_catalog().skeleton_for("mystical", "consolidation")  # type: ignore[arg-type]


@pytest.mark.parametrize("knowledge_type", ["procedural", "conceptual", "factual", "evaluative"])
@pytest.mark.parametrize("mode", PLANNER_LESSON_MODES)
def test_every_knowledge_type_resolves_for_every_planner_mode(knowledge_type, mode) -> None:
    skeleton = load_skeleton_catalog().skeleton_for(knowledge_type, mode)
    assert skeleton["slots"][-1] == "check"
