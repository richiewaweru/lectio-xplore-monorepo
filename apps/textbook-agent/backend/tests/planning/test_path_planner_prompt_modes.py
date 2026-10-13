"""The live path planner prompt owns lesson_mode; the structural prompt defers to it."""

from __future__ import annotations

from curriculum.prompts import packaged_prompt_text, prompt_text


def test_path_planner_defines_three_modes_with_definitions() -> None:
    text = packaged_prompt_text("path-planner.md")

    assert "### Step 8 — Set lesson_mode" in text
    for mode in ("first_exposure", "consolidation", "transfer"):
        assert mode in text
    assert "the lesson teaches something new" in text
    assert "uses ideas taught in earlier lessons" in text
    assert "applies everything so far to an unfamiliar" in text


def test_path_planner_schema_includes_lesson_mode_fields() -> None:
    text = packaged_prompt_text("path-planner.md")

    assert '"lesson_mode":' in text
    assert '"lesson_mode_reason":' in text


def test_path_planner_never_emits_repair_or_retrieval() -> None:
    text = packaged_prompt_text("path-planner.md")

    assert "Never emit repair or retrieval" in text
    assert '"lesson_mode": "first_exposure" | "consolidation" | "transfer"' in text
    assert '"repair"' not in text
    assert '"retrieval"' not in text


def test_structural_planner_defers_lesson_mode_to_path_planner() -> None:
    text = prompt_text("path-structural-planner-v1.txt")

    assert "determined by position" not in text
    assert "lesson_mode          set by the path planner" in text
