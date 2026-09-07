"""Skeleton catalog remains for Unit path shape (HTTP preview retired in D3)."""
from __future__ import annotations

from v3_blueprint.skeletons import load_skeleton_catalog


def test_versioned_catalog_loads_eleven_skeletons() -> None:
    catalog = load_skeleton_catalog()
    assert len(catalog.skeletons) == 11
