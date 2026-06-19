from __future__ import annotations

from pathlib import Path

from learning.pack_spec_loader import load_all_pack_specs

SPECS_DIR = Path(__file__).parents[2] / "resources" / "pack_specs"


def test_all_pack_specs_load() -> None:
    specs = load_all_pack_specs(SPECS_DIR)
    assert set(specs) == {"reteach", "assess", "differentiate"}


def test_reteach_order_is_spec_driven() -> None:
    spec = load_all_pack_specs(SPECS_DIR)["reteach"]
    assert [entry.resource_type for entry in spec.resources] == [
        "quick_explainer",
        "worksheet",
        "exit_ticket",
    ]


def test_assess_has_no_instruction_resources() -> None:
    spec = load_all_pack_specs(SPECS_DIR)["assess"]
    types = [entry.resource_type for entry in spec.resources]
    assert "mini_booklet" not in types
    assert "worksheet" not in types
