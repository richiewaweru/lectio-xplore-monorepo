from __future__ import annotations

from pathlib import Path


_PROMPT_NAMES = {
    "path-planner-v1.txt",
    "merge-critic-v1.txt",
    "component-selector-v1.txt",
    "path-structural-planner-v1.txt",
    "path-structural-planner-page-v1.txt",
    "section-block-planner-v1.txt",
}

# Prompts that have moved into the packaged `resources/prompts/` directory
# (Workstream C). These are loaded by `packaged_prompt_text` instead of the
# legacy flat `resources/*.txt` layout used by `_PROMPT_NAMES`.
_PACKAGED_PROMPT_NAMES = {
    "path-planner.md",
    "merge-critic.md",
}


def prompt_text(resource_name: str) -> str:
    if resource_name not in _PROMPT_NAMES:
        raise ValueError(f"Unknown Phase 5 prompt resource: {resource_name}")
    path = Path(__file__).resolve().parents[2] / "resources" / resource_name
    return path.read_text(encoding="utf-8")


def packaged_prompt_text(resource_name: str) -> str:
    if resource_name not in _PACKAGED_PROMPT_NAMES:
        raise ValueError(f"Unknown packaged prompt resource: {resource_name}")
    path = Path(__file__).resolve().parents[2] / "resources" / "prompts" / resource_name
    return path.read_text(encoding="utf-8")


def path_planner_prompt() -> str:
    from core.prompts import effective_prompt_text

    return effective_prompt_text("path-planner")


def merge_critic_prompt() -> str:
    from core.prompts import effective_prompt_text

    return effective_prompt_text("merge-critic")


def constructor_prompt() -> str:
    from core.prompts import effective_prompt_text

    return effective_prompt_text("constructor")


def plan_editor_prompt() -> str:
    from core.prompts import effective_prompt_text

    return effective_prompt_text("plan-editor")


def component_selector_prompt() -> str:
    return prompt_text("component-selector-v1.txt")


def path_structural_planner_prompt() -> str:
    return prompt_text("path-structural-planner-v1.txt")


def path_structural_planner_page_prompt() -> str:
    return prompt_text("path-structural-planner-page-v1.txt")


def section_block_planner_prompt() -> str:
    return prompt_text("section-block-planner-v1.txt")

