"""Print-owned planner/writer prompt loaders (evacuated from curriculum.prompts)."""

from __future__ import annotations

from pathlib import Path

from curriculum.prompts import (
    form_planner_prompt,
    lesson_approach_planner_prompt,
    lesson_approach_planner_v1_prompt,
    page_writer_common_prompt,
    prompt_text as _curriculum_prompt_text,
)

_PACKAGE_WRITER_RESOURCES = {
    "prose-writer-v1.txt": "prose-writer-v1.txt",
    "list-writer-v1.txt": "list-writer-v1.txt",
    "table-writer-v1.txt": "table-writer-v1.txt",
    "worked-example-writer-v1.txt": "worked-example-writer-v1.txt",
    "figure-brief-writer-v1.txt": "figure-brief-writer-v1.txt",
}


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _package_instruction_path(resource_name: str) -> Path:
    return (
        _backend_root()
        / "contracts"
        / "lectio-page"
        / "authoring"
        / "instructions"
        / resource_name
    )


def prompt_text(name: str) -> str:
    resource_name = _PACKAGE_WRITER_RESOURCES.get(name)
    if resource_name:
        path = _package_instruction_path(resource_name)
        if path.exists():
            return path.read_text(encoding="utf-8")
    return _curriculum_prompt_text(name)

__all__ = [
    "form_planner_prompt",
    "lesson_approach_planner_prompt",
    "lesson_approach_planner_v1_prompt",
    "page_writer_common_prompt",
    "prompt_text",
]
