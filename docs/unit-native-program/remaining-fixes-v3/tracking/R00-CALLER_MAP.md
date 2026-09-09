# R00 Caller map — exact function paths

Baseline HEAD: `db157f00731602c35ec1ec1e71fd5cc5d21e655b`

## Shared preparation handoff

| Step | Function path | Module file |
| --- | --- | --- |
| Load approved state | `application.unit_lesson.dual_native.load_shared_teaching_state` | `src/application/unit_lesson/dual_native.py` |
| Accept Print consumer | `curriculum.teaching_plan.consumers.accept_approved_teaching_revision(..., consumer="print")` | `src/curriculum/teaching_plan/consumers.py` |
| Accept Learn consumer | `curriculum.teaching_plan.consumers.accept_approved_teaching_revision(..., consumer="learn")` | `src/curriculum/teaching_plan/consumers.py` |
| Identity guard | `curriculum.teaching_plan.consumers.assert_identical_consumer_handoffs` | `src/curriculum/teaching_plan/consumers.py` |
| Coverage obligations | `curriculum.teaching_plan.coverage.instructional_coverage` | `src/curriculum/teaching_plan/coverage.py` |
| Dual-path orchestration | `application.unit_lesson.dual_native.accept_shared_teaching_for_both` | `src/application/unit_lesson/dual_native.py` |

## Print — prepare → selection → work orders → engine → assembly → persist

| Stage | Function path | Module file |
| --- | --- | --- |
| Entry | `print.generation.whole_lesson.executor.execute_after_teaching_approval` | `src/print/generation/whole_lesson/executor.py` |
| Candidate map | `print.generation.catalogue_projections.build_form_candidate_map` | `src/print/generation/catalogue_projections.py` |
| Closed plan | `print.generation.native_production.build_closed_print_production_plan` | `src/print/generation/native_production.py` |
| Selection snapshot | `print.generation.selection_snapshot.build_print_selection_snapshot` | `src/print/generation/selection_snapshot.py` |
| Deterministic pick | `print.generation.selection_snapshot.select_print_deterministically` | `src/print/generation/selection_snapshot.py` |
| Keyword rank (current) | `print.generation.selection_snapshot.rank_print_form_candidates` | `src/print/generation/selection_snapshot.py` |
| Work orders | `print.generation.work_orders.compile_print_work_orders` | `src/print/generation/work_orders.py` |
| Scoped request | `print.generation.work_orders.build_print_writer_request` | `src/print/generation/work_orders.py` |
| Block write loop | `print.generation.whole_lesson.executor.write_form_blocks` | `src/print/generation/whole_lesson/executor.py` |
| Single block | `print.generation.whole_lesson.executor._write_one_block` | `src/print/generation/whole_lesson/executor.py` |
| Writer dispatch | `print.rendering.page_objects.registry.dispatch_writer_async` | `src/print/rendering/page_objects/registry.py` |
| Provider authoring | `print.generation.authoring_adapter.run_print_authoring` | `src/print/generation/authoring_adapter.py` |
| Shared engine | `infra.authoring.engine.AuthoringEngine.execute` | `src/infra/authoring/engine.py` |
| DB assembly | `print.generation.whole_lesson.executor.assemble_from_db` | `src/print/generation/whole_lesson/executor.py` |
| Section assembly | `print.rendering.assembly.assemble_section` | `src/print/rendering/assembly/` |
| Document assembly | `print.rendering.assembly.assemble_document_v2` | `src/print/rendering/assembly/` |
| Persistence | `print.generation.whole_lesson.repository.PageDocumentRepository` | `src/print/generation/whole_lesson/repository.py` |
| Realization link | `application.unit_lesson.dual_native.link_print_realization` | `src/application/unit_lesson/dual_native.py` |

## Learn — prepare → selection → work orders → engine → assembly → persist

| Stage | Function path | Module file |
| --- | --- | --- |
| Entry | `learn.generation.native_execution.produce_learn_from_approved_teaching` | `src/learn/generation/native_execution.py` |
| Closed production | `learn.generation.native_production.build_closed_learn_production_async` | `src/learn/generation/native_production.py` |
| Sync wrapper | `learn.generation.native_production.build_closed_learn_production` | `src/learn/generation/native_production.py` |
| Candidate map | `learn.resources.selection.build_learn_candidate_map` | `src/learn/resources/selection.py` |
| Selection snapshot | `learn.generation.native_selection.build_learn_selection_snapshot` | `src/learn/generation/native_selection.py` |
| Deterministic pick | `learn.generation.native_selection.select_learn_deterministically` | `src/learn/generation/native_selection.py` |
| Keyword rank (current) | `learn.generation.native_selection.rank_learn_content_candidates` | `src/learn/generation/native_selection.py` |
| Keyword rank (current) | `learn.generation.native_selection.rank_learn_interaction_candidates` | `src/learn/generation/native_selection.py` |
| Work orders | `learn.generation.work_orders.compile_learn_work_orders` | `src/learn/generation/work_orders.py` |
| Scoped request | `learn.generation.work_orders.build_learn_writer_request` | `src/learn/generation/work_orders.py` |
| Batch authoring | `learn.generation.authoring_adapter.author_learn_work_orders` | `src/learn/generation/authoring_adapter.py` |
| Per-order authoring | `learn.generation.authoring_adapter.run_learn_work_order_authoring` | `src/learn/generation/authoring_adapter.py` |
| Engine call | `learn.generation.authoring_adapter.run_learn_authoring` | `src/learn/generation/authoring_adapter.py` |
| Input map | `learn.generation.authoring_adapter._input_map` | `src/learn/generation/authoring_adapter.py` |
| Contract assembly | `learn.generation.authoring_adapter.interaction_contract_from_authoring_result` | `src/learn/generation/authoring_adapter.py` |
| Prompt substitution (defect) | `learn.generation.authoring_adapter._prompt_from_order` | `src/learn/generation/authoring_adapter.py` |
| Shared engine | `infra.authoring.engine.AuthoringEngine.execute` | `src/infra/authoring/engine.py` |
| Ordered assembly | `learn.generation.ordered_assemble.assemble_ordered_learn_document` | `src/learn/generation/ordered_assemble.py` |
| Builder host remap | `learn.generation.native_production.host_interaction_blocks_for_builder` | `src/learn/generation/native_production.py` |
| Publish validation | `learn.publishing.publish_validation.validate_publishable_lesson_document` | `src/learn/publishing/publish_validation.py` |
| Persistence | `core.database.models.GenerationModel` / `EditableLessonModel` | `src/core/database/models.py` |
| Realization link | `application.unit_lesson.realizations.admit_realization` | `src/application/unit_lesson/realizations.py` |

## Alternate Learn interaction entry (compatibility)

| Stage | Function path | Module file |
| --- | --- | --- |
| Legacy/test request | `learn.generation.interaction_writer.write_interaction_from_request` | `src/learn/generation/interaction_writer.py` |
| Work-order path | `learn.generation.interaction_writer.write_interaction_from_work_order` | `src/learn/generation/interaction_writer.py` |

## Commands exercised in R00

| Purpose | Command | Cwd |
| --- | --- | --- |
| R00 regressions (all) | `uv run pytest -q tests/remaining_fixes/` | `apps/textbook-agent/backend` |
| Incomplete activity | `uv run pytest -q tests/remaining_fixes/test_r00_incomplete_activity.py` | `apps/textbook-agent/backend` |
| Approved source leak | `uv run pytest -q tests/remaining_fixes/test_r00_approved_source_leak.py` | `apps/textbook-agent/backend` |
| Empty teaching context | `uv run pytest -q tests/remaining_fixes/test_r00_empty_teaching_context.py` | `apps/textbook-agent/backend` |
| Keyword selection | `uv run pytest -q tests/remaining_fixes/test_r00_keyword_selection.py` | `apps/textbook-agent/backend` |
