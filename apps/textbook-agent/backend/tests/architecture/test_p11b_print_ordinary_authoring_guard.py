"""P11B architecture guard: Print cannot resurrect ordinary authoring, and
standalone Print generation stays retired.

The SharedLessonDocument Print adapter
(``print.generation.shared_document_adapter`` /
``print.generation.shared_document_execution``) realizes Print
deterministically from the verified, immutable shared source. Nothing in the
Print realization path may plan forms via an LLM, author ordinary content via
an LLM, or call the shared ordinary composer/writer directly. Standalone
Print (a Print generation with no Unit lesson to key a SharedLessonDocument
identity on) is retired outright — there is no ordinary-authoring fallback
left for it to route through.

This guard fails if:
  * a retired module (the closed-catalogue form/work-order pipeline, the
    whole-lesson planning/writing executor, or the old dual-native bridge)
    is importable again;
  * Print/application-unit-lesson code imports ``document.composer`` or
    ``document.writer`` (P11B made Print's own callers of these zero-caller;
    unlike the Learn P10E guard, Print now carries no exception for them);
  * Print/application-unit-lesson code references a deleted ordinary-
    authoring symbol name;
  * ``realize_print_from_preparation`` still accepts the retired
    ``allow_standalone`` parameter, or admits a standalone (no
    ``path_lesson_id``) Print generation instead of failing closed.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_SRC = Path(__file__).resolve().parents[2] / "src"

RETIRED_MODULES = [
    "print.generation.composition_bridge",
    "print.generation.document_realizer",
    "print.generation.shared_writer_bridge",
    "print.generation.authoring_adapter",
    "print.generation.work_orders",
    "print.generation.selection_snapshot",
    "print.generation.source_resolver",
    "print.generation.model_tiers",
    "print.generation.whole_lesson.form_agent",
    "print.generation.whole_lesson.form_plan",
    "print.generation.whole_lesson.executor",
    "print.generation.whole_lesson.resolved_block_plan",
    "print.generation.whole_lesson.failure_injection",
    "application.unit_lesson.dual_native",
]

# Unlike Learn's P10E guard, Print carries no exception here: P11B's deletion
# sweep confirmed zero remaining Print/application-unit-lesson callers of
# document.composer/document.writer (composition_bridge.py, their only
# caller, is retired).
FORBIDDEN_ORDINARY_MODULES = (
    "document.composer",
    "document.writer",
)

DELETED_SYMBOLS = (
    "execute_after_teaching_approval",
    "build_closed_print_production_plan",
    "build_closed_print_production_plan_async",
    "compile_print_work_orders",
    "compile_print_work_orders_for_form_plan",
    "run_print_authoring",
    "write_ordinary_via_shared_writer",
    "produce_print_document_plan_from_teaching",
    "build_print_production_from_composition",
    "dispatch_writer_async",
    "build_print_selection_snapshot",
    "build_print_selection_snapshot_async",
)

PRINT_SCAN_DIRS = [
    "print/generation",
    "print/rendering",
    "application/unit_lesson",
]


def test_retired_print_ordinary_modules_cannot_be_imported() -> None:
    """Deleted Print ordinary-authoring modules must not be importable."""
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


def test_print_generation_does_not_import_ordinary_composer_or_writer() -> None:
    """No Print/application-unit-lesson code may invoke the ordinary composer/writer.

    P11B made this a hard prohibition with no exception: Print's last caller
    of ``document.composer``/``document.writer`` (``composition_bridge.py``)
    is deleted.
    """
    violations: list[str] = []

    for scan_dir in PRINT_SCAN_DIRS:
        for py_path in _iter_py_files(scan_dir):
            rel = py_path.relative_to(BACKEND_SRC)
            tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for forbidden in FORBIDDEN_ORDINARY_MODULES:
                            if alias.name == forbidden or alias.name.startswith(
                                forbidden + "."
                            ):
                                violations.append(
                                    f"Forbidden ordinary-authoring import: {rel} -> {alias.name}"
                                )
                elif isinstance(node, ast.ImportFrom) and node.module:
                    full_module = node.module
                    for forbidden in FORBIDDEN_ORDINARY_MODULES:
                        if full_module == forbidden or full_module.startswith(
                            forbidden + "."
                        ):
                            violations.append(
                                f"Forbidden ordinary-authoring import: {rel} -> {full_module}"
                            )
                    if full_module == "document":
                        for alias in node.names:
                            qualified = f"document.{alias.name}"
                            for forbidden in FORBIDDEN_ORDINARY_MODULES:
                                if qualified == forbidden:
                                    violations.append(
                                        f"Forbidden ordinary-authoring import: {rel} -> {qualified}"
                                    )

    assert not violations, "\n".join(violations)


def test_print_generation_does_not_reference_deleted_ordinary_symbols() -> None:
    """Deleted ordinary-authoring symbol names must not reappear as live code."""
    violations: list[str] = []

    for scan_dir in PRINT_SCAN_DIRS:
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


def test_realize_print_from_preparation_no_longer_accepts_allow_standalone() -> None:
    """The retired ``allow_standalone`` escape hatch must not reappear."""
    from application.unit_lesson.realize_print_handoff import (
        realize_print_from_preparation,
    )

    signature = inspect.signature(realize_print_from_preparation)
    assert "allow_standalone" not in signature.parameters


@pytest.mark.asyncio
async def test_standalone_print_generation_fails_closed(monkeypatch) -> None:
    """A preparation with no resolvable Unit lesson must be rejected, not
    routed through any ordinary-authoring fallback.

    Full DB-backed coverage of this (including the route-level path via
    ``native_http.post_lesson_approach_approve`` and
    ``post_realize_print``) lives in
    ``tests/application/test_p03_realization_gates.py::test_p03_standalone_studio_print_approval_is_retired``.
    This is a narrow, DB-free proof that the guard fires before any admission
    or worker-side logic runs.
    """
    from application.unit_lesson.realize_print_handoff import (
        realize_print_from_preparation,
    )

    class _FakeSession:
        """Returns the fake preparation generation on the first ``scalar``
        call only (the admission-side load), and ``None`` for every
        subsequent lookup (provenance, path-lesson fallback) so the handoff
        genuinely cannot resolve a ``path_lesson_id`` and takes the
        standalone branch."""

        def __init__(self, generation):
            self._generation = generation
            self._scalar_calls = 0

        async def scalar(self, *_args, **_kwargs):
            self._scalar_calls += 1
            if self._scalar_calls == 1:
                return self._generation
            return None

        async def get(self, *_args, **_kwargs):
            return None

    class _FakeGeneration:
        id = "fake-standalone-preparation"
        user_id = "fake-user"
        chunked_state_json = {
            "native_whole_lesson": True,
            "stage": "awaiting_teaching_approval",
        }

    session = _FakeSession(_FakeGeneration())

    with pytest.raises(HTTPException) as error:
        await realize_print_from_preparation(
            session,
            preparation_generation_id="fake-standalone-preparation",
            user_id="fake-user",
        )
    assert error.value.status_code == 409
    assert error.value.detail["code"] == "PRINT_STANDALONE_RETIRED"
