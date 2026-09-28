"""P10E architecture guard: Learn generation cannot resurrect ordinary authoring.

The SharedLessonDocument Learn adapter (``learn.generation.shared_document_adapter``)
copies ordinary content from the verified, immutable shared source and maps
every TaskAnchor to a Learn interaction deterministically. Nothing in the
Learn realization path may author ordinary content, select an interaction via
an LLM, or call the shared ordinary composer/writer directly.

This guard fails if:
  * a retired module (``learn.generation.native_execution``,
    ``learn.generation.document_realizer``) is importable again;
  * Learn generation code imports ``document.composer`` or ``document.writer``
    (the shared ordinary composer/writer that Print still legitimately uses),
    including aliased or module-qualified imports;
  * Learn generation code imports a deleted symbol name
    (``produce_learn_from_approved_teaching``,
    ``produce_learn_document_from_teaching``, ``realize_learn_document``).
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"

RETIRED_MODULES = [
    "learn.generation.native_execution",
    "learn.generation.document_realizer",
]

FORBIDDEN_ORDINARY_MODULES = (
    "document.composer",
    "document.writer",
)

DELETED_SYMBOLS = (
    "produce_learn_from_approved_teaching",
    "produce_learn_document_from_teaching",
    "produce_learn_document_from_teaching_async",
    "realize_learn_document",
)

LEARN_SCAN_DIRS = [
    "learn/generation",
    "application/unit_lesson",
]

# Pre-existing, narrowly-scoped exception outside this work package's bounded
# candidate list (see docs/shared-document-overhaul/phase10_learn_cutover_audit.md
# and the P10E Luna report). ``work_orders.py`` keeps a closed LessonDocument
# v1 ``compile_learn_work_orders`` path whose only remaining callers are
# tests (zero production callers); it reads ``document.writer._PRIMITIVE_SCHEMAS``
# for schema lookups only, never composes or writes ordinary content. Deleting
# it means touching the still-live ``LearnWorkOrder``/interaction-writer
# machinery, which is out of P10E's scope. Recorded for Sol as a follow-up
# decision rather than silently ignored.
FORBIDDEN_IMPORT_EXCEPTIONS = {
    "learn/generation/work_orders.py": {"document.writer"},
}


def _is_excepted(rel_path: Path, forbidden: str) -> bool:
    key = rel_path.as_posix()
    return forbidden in FORBIDDEN_IMPORT_EXCEPTIONS.get(key, set())


def test_retired_learn_ordinary_modules_cannot_be_imported() -> None:
    """Deleted Learn ordinary-authoring modules must not be importable."""
    for mod_name in RETIRED_MODULES:
        with pytest.raises(ModuleNotFoundError, match=r"No module named"):
            importlib.import_module(mod_name)


def _iter_py_files(scan_dir: str) -> list[Path]:
    target_path = BACKEND_SRC / scan_dir
    if not target_path.exists():
        return []
    return [
        p
        for p in target_path.rglob("*.py")
        if "__pycache__" not in p.parts
    ]


def test_learn_generation_does_not_import_ordinary_composer_or_writer() -> None:
    """Only SharedDocument generation may invoke the ordinary composer/writer.

    Print keeps legitimate callers of ``document.composer``/``document.writer``
    (Phase 11 cutover is separate); Learn must have none, including aliased
    imports (``import document.composer as x``) and module-qualified imports
    (``from document import composer``).
    """
    violations: list[str] = []

    for scan_dir in LEARN_SCAN_DIRS:
        for py_path in _iter_py_files(scan_dir):
            rel = py_path.relative_to(BACKEND_SRC)
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in FORBIDDEN_ORDINARY_MODULES:
                            if (
                                alias.name == forbidden
                                or alias.name.startswith(forbidden + ".")
                            ) and not _is_excepted(rel, forbidden):
                                violations.append(
                                    f"Forbidden ordinary-authoring import: {rel} -> {alias.name}"
                                )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    full_module = node.module
                    for forbidden in FORBIDDEN_ORDINARY_MODULES:
                        if (
                            full_module == forbidden
                            or full_module.startswith(forbidden + ".")
                        ) and not _is_excepted(rel, forbidden):
                            violations.append(
                                f"Forbidden ordinary-authoring import: {rel} -> {full_module}"
                            )
                    # `from document import composer` / `from document import writer`
                    if full_module == "document":
                        for alias in node.names:
                            qualified = f"document.{alias.name}"
                            for forbidden in FORBIDDEN_ORDINARY_MODULES:
                                if qualified == forbidden and not _is_excepted(
                                    rel, forbidden
                                ):
                                    violations.append(
                                        f"Forbidden ordinary-authoring import: {rel} -> {qualified}"
                                    )

    assert not violations, "\n".join(violations)


def test_learn_generation_does_not_reference_deleted_ordinary_symbols() -> None:
    """Deleted ordinary-authoring symbol names must not reappear as live code.

    Uses the AST (import/name/attribute nodes only) rather than a raw
    substring search so that historical docstrings explaining *why* a symbol
    was retired (for example ``shared_document_execution``'s module
    docstring) do not trip the guard.
    """
    violations: list[str] = []

    for scan_dir in LEARN_SCAN_DIRS:
        for py_path in _iter_py_files(scan_dir):
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                name: str | None = None
                if isinstance(node, ast.Name):
                    name = node.id
                elif isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, ast.alias):
                    name = node.name.rsplit(".", 1)[-1]
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name in DELETED_SYMBOLS:
                            rel = py_path.relative_to(BACKEND_SRC)
                            violations.append(
                                f"Deleted symbol imported: {rel} -> {alias.name}"
                            )
                    continue
                if name in DELETED_SYMBOLS:
                    rel = py_path.relative_to(BACKEND_SRC)
                    violations.append(f"Deleted symbol referenced: {rel} -> {name}")

    assert not violations, "\n".join(violations)
