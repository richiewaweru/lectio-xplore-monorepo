from __future__ import annotations

from v3_blueprint.planning.section_expander import build_stage2_system_prompt


def test_stage2_prompt_requires_visual_style_and_visual_constraints() -> None:
    prompt = build_stage2_system_prompt()

    assert '"visual_style": "diagram_precision | illustration"' in prompt
    assert "Prefer 2 to 5 short, concrete items" in prompt
    assert "use diagram_precision" in prompt
    assert "content_intent max 300 chars" not in prompt
    assert "Do not add any keys not shown" not in prompt
