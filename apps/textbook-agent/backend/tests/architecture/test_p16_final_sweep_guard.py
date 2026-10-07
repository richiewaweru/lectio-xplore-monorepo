"""P16 guard: modules retired by the final zero-caller sweep stay deleted.

Each module below had no production importer reachable from ``app`` (static
import graph incl. function-local imports), and no test or script kept it
alive except its own dedicated tests, which were removed with it. The shims
(``v3_blueprint.planning.*``, ``v3_execution.config*``, ``v3_execution.executors.*``,
``learn.release_routes`` ...) were re-exports whose callers now import the
canonical module directly.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

RETIRED_MODULES = (
    # 3A: preparation runs on the shared runtime. The NativeExecutionWorker only
    # served the preparation pre-worker retry; the Print awaiting_visuals dispatch
    # and topology-recovery modules have had no production caller since 4A.
    "print.generation.whole_lesson.worker",
    "print.generation.whole_lesson.visual_dispatch",
    "print.generation.whole_lesson.visual_topology_recovery",
    # 4B: realization progress/status routes (status now projected from Runs)
    "application.unit_lesson.progress_routes",
    # 3D: legacy chunked status projector + native retry-target decision
    "print.generation.whole_lesson.native_status",
    "print.generation.whole_lesson.native_retry",
    # 3C: the Teaching Plan planner moved to application.unit_lesson
    "print.generation.whole_lesson.teaching_agent",
    "print.generation.whole_lesson.service",
    # old ordinary document authoring (replaced by document.shared_lesson.composer)
    "document.composer",
    # dead generation/authoring leftovers
    "application.unit_lesson.stage_registry",
    "curriculum.compatibility",
    "curriculum.linkage",
    "curriculum.teaching_plan.coverage",
    "learn.generation.canonical",
    "learn.generation.document_writer",
    "learn.generation.figure_pipeline",
    "learn.generation.fencing",
    "learn.generation.realize_learn",
    "learn.generation.worker",
    "learn.models",
    "learn.pack_repository",
    "learn.resources.component_candidates",
    "learn.routes",
    "print.generation.document_form_map",
    "print.generation.page_projections",
    "print.http.v3_studio.agents",
    "print.http.v3_studio.prompts",
    "print.http.v3_studio.signal_map",
    "print.rendering.page_objects.scripted_provider",
    "print.rendering.page_objects.views",
    "print.rendering.pdf.telemetry",
    "resource_specs.component_candidates",
    "infra.telemetry.v3_trace.payloads",
    "v3_blueprint.shadow",
    "v3_blueprint.validators",
    # Item 2: the old Learn LLM-authoring engine (Learn is realized deterministically
    # from the verified SharedLessonDocument; validate_interaction_contract now lives in
    # learn.interactions.contract_validation)
    "learn.generation.interaction_writer",
    "learn.generation.authoring_adapter",
    "learn.generation.work_orders",
    "learn.generation.activity_authoring",
    "learn.generation.native_selection",
    "learn.generation.source_resolver",
    "learn.generation.preparation_context",
    "learn.generation.reliability_persist",
    "learn.interactions.action_map",
    "learn.resources.selection",
    "document.writer",
    "document.writer_prompts",
    "document.heuristics",
    "infra.authoring.capability_selector",
    "v3_execution.llm_helpers",
    # compatibility shims (callers import the canonical module)
    "core.errors",
    "core.logging",
    "core.middleware",
    "core.version",
    "learn.release_routes",
    "learn.runtime_routes",
    "v3_blueprint.planning",
    "v3_blueprint.skeletons",
    "v3_execution.config",
    "v3_execution.executors",
    "v3_execution.prompts.item_prompt",
    "v3_execution.runtime",
)


@pytest.mark.parametrize("module_name", RETIRED_MODULES)
def test_retired_module_cannot_be_imported(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)


def test_retired_document_composer_prompt_is_not_in_manifest() -> None:
    from core.prompts import loader

    assert "document-composer" not in {entry.id for entry in loader.load_manifest()}
    assert "document-composer" not in loader.CLOSEOUT_PROMPT_IDS


def test_retired_learn_and_document_writer_prompts_are_not_in_manifest() -> None:
    from core.prompts import loader

    retired = {"interaction-writer", "document-writer"}
    assert retired.isdisjoint({entry.id for entry in loader.load_manifest()})
    assert retired.isdisjoint(loader.CLOSEOUT_PROMPT_IDS)


PLANNER_ENTRY_POINTS = {
    "run_staged_teaching_planner",
    "review_teaching_plan_draft",
    "run_and_persist_teaching_plan",
}
_SRC = Path(__file__).resolve().parents[2] / "src"


def test_planner_lives_in_application_layer() -> None:
    from application.unit_lesson import staged_teaching_planner, teaching_plan_service

    assert callable(staged_teaching_planner.run_staged_teaching_planner)
    assert callable(teaching_plan_service.run_and_persist_teaching_plan)


def test_print_does_not_define_planner_entry_points() -> None:
    offenders: list[str] = []
    for path in sorted((_SRC / "print").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in PLANNER_ENTRY_POINTS
            ):
                offenders.append(f"{path.relative_to(_SRC)}: {node.name}")
    assert not offenders, offenders
