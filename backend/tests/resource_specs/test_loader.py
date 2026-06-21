from __future__ import annotations

from pathlib import Path

from resource_specs.loader import load_all_specs

SPECS_DIR = Path(__file__).parents[2] / "resources" / "specs"


def test_all_resource_specs_load() -> None:
    specs = load_all_specs(SPECS_DIR)
    assert set(specs) == {
        "lesson",
        "mini_booklet",
        "worksheet",
        "exit_ticket",
        "quick_explainer",
        "practice_set",
        "quiz",
    }


def test_specs_have_required_sections_and_depths() -> None:
    specs = load_all_specs(SPECS_DIR)
    for spec in specs.values():
        assert spec.sections.required
        assert {"quick", "standard", "deep"}.issubset(spec.depth)
        for depth_key in ("quick", "standard", "deep"):
            depth_variant = spec.depth[depth_key]
            assert isinstance(depth_variant.min_sections, int)
            assert isinstance(depth_variant.max_sections, int)
            assert depth_variant.min_sections <= depth_variant.max_sections


def test_resource_type_enum_matches_available_specs() -> None:
    """
    ResourceType enum in v3_blueprint/models.py must contain exactly the spec IDs
    that exist on disk.

    If this test fails:
    - A new spec YAML was added but ResourceType was not updated, OR
    - A ResourceType value was added that has no backing spec YAML.
    Either is a bug. Fix by keeping the enum and the spec files in sync.
    """
    from v3_blueprint.models import ResourceType

    spec_ids = set(load_all_specs(SPECS_DIR).keys())
    enum_values = set(ResourceType.__args__)

    in_enum_not_in_specs = enum_values - spec_ids
    in_specs_not_in_enum = spec_ids - enum_values

    assert not in_enum_not_in_specs, (
        f"ResourceType enum contains values with no backing spec YAML: "
        f"{sorted(in_enum_not_in_specs)}. "
        f"Either add a spec YAML for each, or remove them from ResourceType."
    )
    assert not in_specs_not_in_enum, (
        f"Spec YAMLs exist with no matching ResourceType value: "
        f"{sorted(in_specs_not_in_enum)}. "
        f"Add them to ResourceType in v3_blueprint/models.py."
    )
