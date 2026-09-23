"""Architecture guard tests: prevent reintroduction of retired V3 execution and assert current ownership."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"

FORBIDDEN_MODULES = [
    "v3_execution.executors.section_writer",
    "v3_execution.executors.question_writer",
    "v3_execution.runtime.stage2_lanes",
    "v3_execution.runtime.runner",
    "v3_execution.assembly.section_builder",
    "v3_execution.assembly.pack_builder",
    "v3_blueprint.planning.section_expander",
    "v3_blueprint.planning.assembler",
    "v3_blueprint.planning.structural_planner",
    "v3_blueprint.planning.retry",
    "v3_blueprint.planning.work_orders",
]

FORBIDDEN_IMPORT_PREFIXES = (
    "v3_execution.executors.section_writer",
    "v3_execution.executors.question_writer",
    "v3_execution.runtime.stage2_lanes",
    "v3_execution.runtime.runner",
    "v3_execution.assembly",
    "v3_blueprint.planning.section_expander",
    "v3_blueprint.planning.assembler",
    "v3_blueprint.planning.structural_planner",
    "v3_blueprint.planning.retry",
    "v3_blueprint.planning.work_orders",
)

CURRENT_NATIVE_SCAN_DIRS = [
    "application/unit_lesson",
    "learn/generation",
    "print/generation/whole_lesson",
    "curriculum",
]


def test_retired_modules_cannot_be_imported() -> None:
    """Deleted legacy execution modules must not be importable."""
    for mod_name in FORBIDDEN_MODULES:
        with pytest.raises(ModuleNotFoundError, match=r"No module named"):
            importlib.import_module(mod_name)


def test_current_native_source_has_no_forbidden_legacy_imports() -> None:
    """Current native code must not import retired planners, expanders, or writers."""
    violations: list[str] = []

    for scan_dir in CURRENT_NATIVE_SCAN_DIRS:
        target_path = BACKEND_SRC / scan_dir
        if not target_path.exists():
            continue
        for py_path in target_path.rglob("*.py"):
            if "__pycache__" in py_path.parts:
                continue
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                            if alias.name == forbidden or alias.name.startswith(forbidden + "."):
                                rel = py_path.relative_to(BACKEND_SRC)
                                violations.append(f"Forbidden legacy dependency: {rel} -> {alias.name}")
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                        if node.module == forbidden or node.module.startswith(forbidden + "."):
                            rel = py_path.relative_to(BACKEND_SRC)
                            violations.append(f"Forbidden legacy dependency: {rel} -> {node.module}")

    assert not violations, "\n".join(violations)


def test_expected_current_ownership_packages_exist() -> None:
    """Assert canonical current packages exist."""
    expected_modules = [
        "curriculum.planning",
        "curriculum.items",
        "media.generation",
        "infra.authoring",
        "application.unit_lesson.native_pipeline",
        "application.unit_lesson.native_http",
    ]
    for mod_name in expected_modules:
        mod = importlib.import_module(mod_name)
        assert mod is not None
