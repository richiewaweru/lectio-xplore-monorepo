# Required behavior

## R1 — Author the complete activity
Target: backend/src/learn/generation/authoring_adapter.py; interaction_writer.py; package Learn writer views, authoring instructions and schemas; consumers of interaction contracts.
Current defect: interaction_contract_from_authoring_result takes prompt from order.brief and inserts generic feedback while writer emits config only.

Generate mode must author a complete activity payload: student-facing prompt, capability-specific config, and relevant feedback required by the existing contract. Use an authoring envelope around the existing config schema; do not redefine the runtime config format. Resolve schema references correctly for structured provider output. A validated postprocessing step combines the authored material with trusted work-order identity, assessment mode, concept references, attempt/completion policy and accessibility requirements. The model must not choose those trusted policies.

Convert-approved mode must preserve the approved stem/prompt, accepted answers, identifiers and feedback where present. Missing required fields mean INCOMPATIBLE_APPROVED_ITEM. If feedback is missing, use only an explicitly defined package conversion policy: optional omission or separately scoped feedback generation that preserves the approved question/answer. Do not silently fall back to the teaching brief as the question. Do not infer teacher-review solely because an answer is absent unless the authoritative work order permits it.

The planning brief remains context. A natural student instruction already approved as a prompt can be preserved, but a planner brief is not automatically an approved prompt. This is a data-contract distinction; a string-inequality test alone is not enough.

## R2 — Exact approved-source ownership
Target: run_learn_authoring, _input_map, author_learn_work_orders, build_learn_writer_request and compile_learn_work_orders.
Create one source resolver used by all entrypoints. Resolve only the work order's explicit approved-item references. Empty references mean no approved items, never approved_items[0]. Missing references, duplicate ambiguous IDs or incompatible item types fail before provider invocation. Source IDs and selected objects must agree.

Do not pass the full approved pool in inputs, prompt JSON, repair requests or provenance. Multiple explicitly referenced items are supported only when the capability's conversion contract supports them; otherwise return a typed incompatibility. Preserve all declared IDs and relationships. New generation may use explicitly scoped supporting source material without being forced into conversion; mode is chosen from work-order intent and definition capability, not merely the existence of any lesson question.

Audit conversion helpers for lossy behavior: e.g. changing Sequence IDs with slugification while preserving incompatible original item IDs, or stringifying accepted-answer alternatives. Preserve the canonical source semantics; reject unrepresentable input.

## R3 — Connect upstream teaching context
Target: native_execution.py, native_production.py, authoring_adapter.py, work_orders.py, shared preparation caller, infra/authoring/engine.py.
Carry objective, relevant approved facts, learner level, terminology, constraints and required dependency results from the existing shared preparation into native production and each work order. Do not invent a second preparation pipeline. Native execution currently exposes too little input: extend its interface and all normal callers, not only the test helper.

Remove unconditional allowed_facts=[] and terminology=[] at the production call. Keep the approved teaching revision immutable; do not reload unrelated current data in place of its pinned preparation. Dependency resolution must provide required predecessor material or produce an owning-stage failure.

Input validation is capability- and mode-specific. A required objective cannot be blank; facts required for new factual generation cannot be an empty list of empty strings. Empty terminology can legitimately be allowed. Do not globally reject all empty lists. Conversion can rely on a complete approved activity without duplicating its facts. Define these rules in the owning authoring contract and enforce them in the engine. Never fill missing information with fake facts just to pass.

## R4 — Actual semantic shortlist selection
Target: Learn native_selection.py; Print selection_snapshot.py/native_production.py and actual form selector routes; provider abstraction and selector prompts.
For an ambiguous legal shortlist, invoke the configured model selector. Supply only eligible candidate IDs and package choose/reject guidance plus relevant teaching need and constraints. Validate response and use bounded repair with the same shortlist. Sole eligible candidates may be automatic. Required actions cannot be omitted; optional interactions follow native policy.

Delete production reliance on rank_learn_content_candidates, rank_learn_interaction_candidates and rank_print_form_candidates keyword scoring, including hardcoded component bonuses. They may remain explicitly isolated test utilities if genuinely needed. Naming token ranking 'semantic' is not compliance. Tests must capture provider calls and prove production follows a valid model decision even when it is not first or highest in lexical overlap.

Audit both actual Print paths: preserve an already-correct model form planner and route other production adapters consistently. Do not add a redundant second model choice after a valid sealed selection. Introduce async interfaces where needed and await them in production; no event-loop-blocking sync bridge for model calls.

## R5 — Evidence must match the gate
Target: authoring-correction-v2 tracking and tests/authoring_correction, original affected P04/P06/P07/P08 reports.
Reopen affected A02, A04, A05 and A06 gates before edits. Preserve old logs as historical. A deepcopy is not persistence; a changed hash is not release publishing; a dispatched Print block is not a completed Print production path; a Python evaluator call is not component rendering.

Use real local test database/service/API entrypoints and explicitly mocked external provider boundaries. Implement or point to existing exact tests that exercise complete requirements. Do not manufacture final documents, inject authored result maps, or directly edit database state as proof of a product journey. Ordinary fixture seeding of identity/preparation is allowed and must be labelled. New generation must still pass through normal writers.

Rendering gates require actual package component tests for generated payloads, including keyboard/submit behavior where required. Builder roundtrip gates require actual edit/validation flow. These are offline tests and need no real provider calls. Explicitly distinguish local component mounting from live browser acceptance.

Fix any implementation defect exposed by these tests. Do not modify gate wording, lower assertions, skip required cases or classify unfinished work as live-only to obtain PASS.
