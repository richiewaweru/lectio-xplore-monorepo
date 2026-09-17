"""D2 Wave C: move curriculum validation/agents/prompts; split print prompts."""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print("wrote", path.relative_to(SRC))


def main() -> None:
    # --- validation ---
    val = (SRC / "planning" / "validation.py").read_text(encoding="utf-8")
    val = val.replace("from planning.models import", "from curriculum.models import")
    write(SRC / "curriculum" / "validation.py", val)
    write(
        SRC / "planning" / "validation.py",
        '''"""Compatibility shim — use curriculum.validation.

Temporary (D2).
"""

from __future__ import annotations

from curriculum.validation import *  # noqa: F401,F403
''',
    )

    # --- prompts: curriculum keeps path/constructor; print gets lesson-approach/form/page ---
    prompts = (SRC / "planning" / "prompts.py").read_text(encoding="utf-8")

    # curriculum prompts: full file with print-specific wrappers that stay for shim re-export
    # First write full content to curriculum, then print-specific module with needed funcs.
    cur_prompts = prompts
    # ensure no planning. imports
    write(SRC / "curriculum" / "prompts.py", cur_prompts)

    # Extract print-specific functions into print/generation/prompts.py by importing shared helpers
    # from curriculum.prompts for prompt_text if needed.
    print_prompts = '''"""Print-owned planner/writer prompt loaders (evacuated from planning.prompts)."""

from __future__ import annotations

from curriculum.prompts import (
    form_planner_prompt,
    lesson_approach_planner_prompt,
    lesson_approach_planner_v1_prompt,
    page_writer_common_prompt,
    prompt_text,
)

__all__ = [
    "form_planner_prompt",
    "lesson_approach_planner_prompt",
    "lesson_approach_planner_v1_prompt",
    "page_writer_common_prompt",
    "prompt_text",
]
'''
    write(SRC / "print" / "generation" / "prompts.py", print_prompts)

    write(
        SRC / "planning" / "prompts.py",
        '''"""Compatibility shim — use curriculum.prompts / print.generation.prompts.

Temporary (D2).
"""

from __future__ import annotations

from curriculum.prompts import *  # noqa: F401,F403
''',
    )

    # Update print consumers to print.generation.prompts
    for rel, pairs in [
        (
            "print/generation/whole_lesson/prompt_render.py",
            [
                (
                    "from planning.prompts import form_planner_prompt, lesson_approach_planner_prompt",
                    "from print.generation.prompts import form_planner_prompt, lesson_approach_planner_prompt",
                )
            ],
        ),
        (
            "print/rendering/page_objects/prompts.py",
            [("from planning.prompts import prompt_text", "from print.generation.prompts import prompt_text")],
        ),
        (
            "print/rendering/page_objects/registry.py",
            [
                (
                    "from planning.prompts import page_writer_common_prompt, prompt_text",
                    "from print.generation.prompts import page_writer_common_prompt, prompt_text",
                )
            ],
        ),
    ]:
        path = SRC / rel
        text = path.read_text(encoding="utf-8")
        new = text
        for old, repl in pairs:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print("updated", rel)

    # --- agents ---
    agents = (SRC / "planning" / "agents.py").read_text(encoding="utf-8")
    agents = (
        agents.replace("from core.config import settings", "from infra.config import settings")
        .replace("from core.llm.runner import", "from infra.llm.runner import")
        .replace("from planning.llm_contract_errors import", "from planning.llm_contract_errors import")
        .replace("from planning.models import", "from curriculum.models import")
        .replace("from planning.prompts import", "from curriculum.prompts import")
        .replace("from planning.planner_diagnostics import", "from planning.planner_diagnostics import")
        .replace("from planning.validation import", "from curriculum.validation import")
    )
    write(SRC / "curriculum" / "agents.py", agents)
    write(
        SRC / "planning" / "agents.py",
        '''"""Compatibility shim — use curriculum.agents.

Temporary (D2).
"""

from __future__ import annotations

from curriculum.agents import *  # noqa: F401,F403
''',
    )

    # Update call sites to curriculum.agents / curriculum.validation
    updates = {
        "curriculum/routes.py": [
            ("from planning.agents import", "from curriculum.agents import"),
            ("from planning.validation import", "from curriculum.validation import"),
        ],
        "curriculum/service.py": [
            ("from planning.validation import", "from curriculum.validation import"),
        ],
        "application/unit_lesson/prepare.py": [
            (
                "from planning.agents import run_component_selector, run_path_structural_planner",
                "from curriculum.agents import run_component_selector, run_path_structural_planner",
            ),
        ],
        "v3_blueprint/planning/component_selector.py": [
            ("from planning.agents import run_component_selector", "from curriculum.agents import run_component_selector"),
        ],
    }
    for rel, pairs in updates.items():
        path = SRC / rel
        text = path.read_text(encoding="utf-8")
        new = text
        for old, repl in pairs:
            new = new.replace(old, repl)
        if new != text:
            path.write_text(new, encoding="utf-8")
            print("updated", rel)

    # learn generation signal_map / v3_execution stage2 if they import generation.contracts
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if "from generation.contracts import" in text or "from generation.pipeline_dispatch import" in text:
            new = text.replace(
                "from generation.contracts import",
                "from learn.generation.contracts import",
            ).replace(
                "from generation.pipeline_dispatch import",
                "from learn.generation.pipeline_dispatch import",
            )
            # Don't rewrite the shim files themselves
            rel = str(path.relative_to(SRC)).replace("\\", "/")
            if rel in {"generation/contracts.py", "generation/pipeline_dispatch.py"}:
                continue
            if new != text:
                path.write_text(new, encoding="utf-8")
                print("rewrote contracts/pipeline import in", rel)


if __name__ == "__main__":
    main()
