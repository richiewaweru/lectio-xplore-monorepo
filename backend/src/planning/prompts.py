from __future__ import annotations

from pathlib import Path


_PROMPT_NAMES = {
    "path-planner-v1.txt",
    "merge-critic-v1.txt",
    "component-selector-v1.txt",
    "path-structural-planner-v1.txt",
}


def prompt_text(resource_name: str) -> str:
    if resource_name not in _PROMPT_NAMES:
        raise ValueError(f"Unknown Phase 5 prompt resource: {resource_name}")
    path = Path(__file__).resolve().parents[2] / "resources" / resource_name
    return path.read_text(encoding="utf-8")


def path_planner_prompt() -> str:
    return prompt_text("path-planner-v1.txt")


def merge_critic_prompt() -> str:
    return prompt_text("merge-critic-v1.txt")


def component_selector_prompt() -> str:
    return prompt_text("component-selector-v1.txt")


def path_structural_planner_prompt() -> str:
    return prompt_text("path-structural-planner-v1.txt")

