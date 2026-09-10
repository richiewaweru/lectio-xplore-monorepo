from __future__ import annotations

from pathlib import Path


LESSON_APPROACH_PROMPT_V1 = "lesson-approach-planner-v1.txt"
LESSON_APPROACH_PROMPT_V2 = "lesson-approach-planner-v2.txt"
ACTIVE_LESSON_APPROACH_PROMPT = LESSON_APPROACH_PROMPT_V2
ACTIVE_LESSON_APPROACH_PROMPT_VERSION = 2
VISUAL_REQUIRED_INTENTS = frozenset(
    {"show-structure", "trace-flow", "sequence", "name-parts"}
)
LESSON_APPROACH_PROMPT_V1_SHA256 = (
    "475b8b178f74c1397742b12002a324e18ae3e39a4fffd9e7a4c199713780a9cd"
)
LESSON_APPROACH_PROMPT_V2_SHA256 = (
    "1e48a253a1be4cdc4c3f77b4a2d57a2662fdf2869db7a724af4fe15dac5b7e3d"
)


_PROMPT_NAMES = {
    "path-planner-v1.txt",
    "merge-critic-v1.txt",
    "component-selector-v1.txt",
    "path-structural-planner-v1.txt",
    "path-structural-planner-page-v1.txt",
    LESSON_APPROACH_PROMPT_V1,
    LESSON_APPROACH_PROMPT_V2,
    "form-planner-v1.txt",
    "native-capability-selector-v1.txt",
    "page-writer-common-v1.txt",
    "prose-writer-v1.txt",
    "list-writer-v1.txt",
    "table-writer-v1.txt",
    "worked-example-writer-v1.txt",
    "figure-brief-writer-v1.txt",
}

# Prompts that have moved into the packaged `resources/prompts/` directory
# (Workstream C). These are loaded by `packaged_prompt_text` instead of the
# legacy flat `resources/*.txt` layout used by `_PROMPT_NAMES`.
_PACKAGED_PROMPT_NAMES = {
    "path-planner.md",
    "merge-critic.md",
    "document-composer-v1.txt",
    "document-writer-v1.txt",
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
    """v1 ONLY — do not use on the native path."""
    return prompt_text("component-selector-v1.txt")


def path_structural_planner_prompt() -> str:
    return prompt_text("path-structural-planner-v1.txt")


def path_structural_planner_page_prompt() -> str:
    return prompt_text("path-structural-planner-page-v1.txt")


def lesson_approach_planner_prompt() -> str:
    return prompt_text(ACTIVE_LESSON_APPROACH_PROMPT)


def lesson_approach_planner_v1_prompt() -> str:
    """Return the frozen historical lesson-approach prompt body."""
    return prompt_text(LESSON_APPROACH_PROMPT_V1)


def form_planner_prompt() -> str:
    return prompt_text("form-planner-v1.txt")


def capability_selector_prompt() -> str:
    return prompt_text("native-capability-selector-v1.txt")


def page_writer_common_prompt() -> str:
    return prompt_text("page-writer-common-v1.txt")


def document_composer_prompt() -> str:
    return packaged_prompt_text("document-composer-v1.txt")


def document_writer_prompt() -> str:
    return packaged_prompt_text("document-writer-v1.txt")
