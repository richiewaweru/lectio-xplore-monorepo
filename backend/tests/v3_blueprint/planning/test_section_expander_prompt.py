from __future__ import annotations

from v3_blueprint.planning.section_expander import build_stage2_system_prompt


def test_stage2_prompt_requires_visual_style_and_visual_constraints() -> None:
    prompt = build_stage2_system_prompt()

    assert '"visual_style": "diagram_precision | illustration"' in prompt
    assert "must_show and must_not_show each contain 2 to 5" in prompt
    assert "use diagram_precision" in prompt
