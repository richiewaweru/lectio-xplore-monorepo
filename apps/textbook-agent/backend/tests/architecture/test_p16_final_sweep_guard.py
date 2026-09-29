"""P16 guard: modules retired by the final zero-caller sweep stay deleted.

Each module below had no production importer reachable from ``app`` (static
import graph incl. function-local imports), and no test or script kept it
alive except its own dedicated tests, which were removed with it. The shims
(``v3_blueprint.planning.*``, ``v3_execution.config*``, ``v3_execution.executors.*``,
``learn.release_routes`` ...) were re-exports whose callers now import the
canonical module directly.
"""

from __future__ import annotations

import importlib

import pytest

RETIRED_MODULES = (
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
