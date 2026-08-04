from __future__ import annotations

from pathlib import Path

from resource_specs.loader import load_all_specs
from resource_specs.renderer import render_spec_for_prompt

SPECS = load_all_specs(Path(__file__).parents[2] / "resources" / "specs")


def test_render_includes_intent_and_forbidden_components() -> None:
    output = render_spec_for_prompt(
        SPECS["worksheet"],
        "standard",
        ["intro", "practice", "summary"],
        [],
    )
    assert "Resource intent:" in output
    assert "hook-hero" in output
    assert "explanation-block" in output
    assert "HARD CONSTRAINT - these components are NEVER permitted for this resource type:" in output
    assert output.index("HARD CONSTRAINT - these components are NEVER permitted for this resource type:") < output.index(
        "Depth: standard"
    )


def test_render_includes_active_supports() -> None:
    output = render_spec_for_prompt(
        SPECS["worksheet"],
        "standard",
        ["intro", "practice", "summary"],
        ["worked_examples"],
    )
    assert "Support: worked_examples" in output
    assert "worked-example-card" in output
