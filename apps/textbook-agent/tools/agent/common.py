# ruff: noqa: E402
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.scripts.common import (
    ContextError,
    get_architecture_strategy,
    get_scope_steps,
    load_context,
    resolve_repo_path,
)

DEFAULT_CONTEXT_PATH = REPO_ROOT / 'docs' / 'project' / 'context-summary.yaml'
__all__ = [
    'ContextError',
    'DEFAULT_CONTEXT_PATH',
    'REPO_ROOT',
    'get_architecture_strategy',
    'get_scope_steps',
    'load_project_context',
    'resolve_repo_path',
]


def load_project_context(
    context_path: str | Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    return load_context(context_path or DEFAULT_CONTEXT_PATH, repo_root=repo_root)
