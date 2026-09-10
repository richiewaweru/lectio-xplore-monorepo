# Caller map — policy cleanup v4 (current HEAD)

Baseline HEAD: `c3563abbb141443bc0131917d09de81a8e4c118a`

Updated from remaining-fixes R00 map. Keyword-rank production paths were removed in R03; async selectors are canonical.

## Shared preparation

| Step | Symbol | File |
| --- | --- | --- |
| Load approved state | `load_shared_teaching_state` | `application/unit_lesson/dual_native.py` |
| Dual-path accept | `accept_shared_teaching_for_both` | same |
| Prep packet | `project_shared_preparation_packet` | `curriculum/teaching_plan/projections.py` |
| Learn prep extract | `learn_preparation_context_from_state` | `learn/generation/preparation_context.py` |

## Learn path

| Stage | Symbol | File |
| --- | --- | --- |
| Entry | `produce_learn_from_approved_teaching` | `learn/generation/native_execution.py` |
| Closed production | `build_closed_learn_production_async` | `learn/generation/native_production.py` |
| Selection | `build_learn_selection_snapshot_async` | `learn/generation/native_selection.py` |
| Work orders | `compile_learn_work_orders` | `learn/generation/work_orders.py` |
| Policy resolve (new) | `resolve_authoring_policy` | `infra/authoring/policy_resolver.py` |
| Authoring | `run_learn_authoring` | `learn/generation/authoring_adapter.py` |
| ShortResponse convert | `_convert_short_response` | same |
| Contract assembly | `interaction_contract_from_authoring_result` | same |
| Engine | `AuthoringEngine.execute` | `infra/authoring/engine.py` |
| Assembly | `assemble_ordered_learn_document` | `learn/generation/ordered_assemble.py` |
| Publish | `validate_publishable_lesson_document` / release routes | `learn/publishing/` |
| Runtime | `submit_attempt` / `evaluate_short_response` | `learn/runtime/` |
| Builder | builder routes + `validate_interaction_contract` | `learn/authoring/builder/` |

## Print path

| Stage | Symbol | File |
| --- | --- | --- |
| Entry | `execute_after_teaching_approval` | `print/generation/whole_lesson/executor.py` |
| Closed plan | `build_closed_print_production_plan_async` | `print/generation/native_production.py` |
| Selection | `build_print_selection_snapshot_async` | `print/generation/selection_snapshot.py` |
| Work orders | `compile_print_work_orders` | `print/generation/work_orders.py` |
| Writer dispatch | `dispatch_writer_async` | `print/rendering/page_objects/registry.py` |
| Authoring | `run_print_authoring` | `print/generation/authoring_adapter.py` |
| Facts into context | executor `WriterContext.lesson_context` + `allowed_facts` | executor / registry |

## Policy owners

| Policy | Declared | Resolved | Executed | Persisted |
| --- | --- | --- | --- | --- |
| Knowledge | Package writer `knowledge` | `policy_resolver` | writers / prompts | provenance snapshot |
| Assessment (Learn ShortResponse) | Package writer `assessment` | `policy_resolver` | `_convert_short_response` / generate config | contract `config.evaluation` + provenance |
