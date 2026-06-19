from __future__ import annotations

from generation.v3_studio.prompts import _planner_index_block, build_architect_system_prompt


def test_manifest_block_is_guided_concept_filtered() -> None:
    block = _planner_index_block()
    assert "TEMPLATE: guided-concept-path" in block
    assert "AVAILABLE COMPONENTS (use only these slugs):" in block
    assert "REQUIRED in every section:" in block
    assert "what-next-bridge" in block
    assert "hook-hero [hook]:" in block
    assert "explanation-block [explanation]:" in block
    assert "concept_intro [explanation]" not in block
    assert "worked_example [worked_example]" not in block


def test_architect_prompt_includes_contract_limits() -> None:
    prompt = build_architect_system_prompt()
    assert "COMPONENT BUDGETS (max across entire lesson):" in prompt
    assert "diagram-block: max 3" in prompt
    assert "PER-SECTION LIMITS:" in prompt
    assert "practice-stack: max 1 per section" in prompt


def test_architect_prompt_includes_reasoning_scaffold() -> None:
    prompt = build_architect_system_prompt()
    assert "REASONING STEPS" in prompt
    assert "STEP 1 - LEARNER CONTEXT" in prompt
    assert "teacher form signals" in prompt
