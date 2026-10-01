"""Option D 3A guards: preparation status comes from the Run, and the bespoke
in-process stage-2 machinery stays deleted.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
_STATUS_INPUTS = {
    "generation_status",
    "workflow_stage",
    "generation_error",
    "generation_error_code",
    "generation_error_type",
}


def _function(path: Path, name: str) -> ast.AST:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found in {path}")


def test_preparation_projection_never_reads_generation_status_or_chunked_stage() -> None:
    path = SRC / "curriculum" / "workspace_projection.py"
    for name in ("_preparation_projection", "project_lesson_workspace"):
        fn = _function(path, name)
        args = {a.arg for a in fn.args.args + fn.args.kwonlyargs}  # type: ignore[attr-defined]
        assert not (args & _STATUS_INPUTS), f"{name} accepts a worker-status input"
        names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
        assert not (names & _STATUS_INPUTS)
        constants = {
            n.value for n in ast.walk(fn) if isinstance(n, ast.Constant) and isinstance(n.value, str)
        }
        # ``chunked["stage"]`` / ``generation.status`` style reads are forbidden;
        # ``teaching_review.status`` (the revision store) is not worker status.
        assert "stage" not in constants, f"{name} reads a worker stage"


def test_unit_path_status_buckets_do_not_read_generation_status() -> None:
    fn = _function(SRC / "curriculum" / "routes.py", "get_path_status")
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Attribute)
            and node.attr in {"status", "error", "error_code", "error_type"}
            and isinstance(node.value, ast.Name)
            and node.value.id in {"generation", "record"}
        ):
            raise AssertionError(f"get_path_status reads {node.value.id}.{node.attr}")


@pytest.mark.parametrize(
    "module, names",
    [
        (
            "application.unit_lesson.native_pipeline",
            ("_run_chunked_stage2_pipeline", "_chunked_stage2_tasks", "_items_job",
             "reap_orphaned_preparation_pipelines", "start_pipeline_orphan_reaper",
             "_generate_shared_pack_items"),
        ),
        (
            "print.generation.whole_lesson.repository",
            ("claim_next_native_job", "persist_native_failure_for_generation"),
        ),
        (
            "print.http.v3_studio.router",
            ("_run_chunked_stage2_pipeline", "_chunked_stage2_tasks", "_run_pack_variant_pipeline",
             "post_xplore_variant_retry", "post_chunked_plan_start"),
        ),
    ],
)
def test_bespoke_stage2_machinery_stays_deleted(module: str, names: tuple[str, ...]) -> None:
    imported = importlib.import_module(module)
    for name in names:
        assert not hasattr(imported, name), f"{module}.{name} must stay deleted"


def test_prep_pipeline_settings_and_orphan_code_are_gone() -> None:
    from infra.config import settings
    from print.generation.whole_lesson import failure_policy
    from print.generation.whole_lesson.repository import PageDocumentRepository

    assert not [k for k in type(settings).model_fields if k.startswith("prep_pipeline")]
    assert not hasattr(failure_policy, "PipelineOrphanedError")
    assert not hasattr(PageDocumentRepository, "claim_pre_worker_retry")
    assert not hasattr(PageDocumentRepository, "persist_native_failure")
    assert not hasattr(PageDocumentRepository, "persist_visual_dispatch_failure")


def test_preparation_worker_is_started_with_the_runtime_workers() -> None:
    text = (SRC / "app.py").read_text(encoding="utf-8")
    assert "PreparationWorker" in text
    assert "start_native_worker" not in text
    assert "fail_stale_running" not in text
    assert "prep_pipeline" not in text


def test_chunked_approve_and_retry_native_compatibility_routes_are_deleted() -> None:
    """3B: the plan page uses /preparations/{id}/plan and the runtime retry routes."""
    from app import app

    paths = {getattr(route, "path", "") for route in app.routes}
    assert not any(p.endswith("/chunked/{generation_id}/approve") for p in paths)
    assert not any(p.endswith("/generations/{generation_id}/retry-native") for p in paths)
