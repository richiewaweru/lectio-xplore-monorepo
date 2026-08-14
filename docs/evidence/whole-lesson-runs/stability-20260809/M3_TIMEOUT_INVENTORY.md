# M3 timeout inventory (static audit)

Audit date: 2026-08-09  
Scope: current Xplore native path from constructor and unit/path planning through native structural planning, items, teaching approval, form planning, page-object writers, and visual dispatch.  
Method: source/config inspection only (`rg`, file reads, and line-level cross-checks). No provider calls, browser runs, or setting changes were made.

## Interpretation and limits

`core.llm.runner.run_llm` wraps each provider invocation in `asyncio.wait_for(...,
timeout=RetryPolicy.call_timeout_seconds)` (`apps/textbook-agent/backend/src/core/llm/runner.py:121-131`).
Its `max_attempts` is an inner transport retry budget; caller-level validation/repair loops
are separate. Timeout/network errors are retryable in the runner (`runner.py:203-222`), and
native execution classifies `asyncio.TimeoutError`, `httpx.TimeoutException`, transport
errors, and OS `TimeoutError` as `TIMEOUT`/`TRANSPORT` with `retryable=true`
(`planning/whole_lesson/failure_policy.py:29-85`).

The “observed” columns are deliberately pending. They require M10-attributed live
telemetry from a real generation; this audit does not infer latency from configured values.

## Effective timeout and retry inventory

| Current-path node / caller | Provider call and timeout source | Effective local value | Inner attempts | Outer repair/retry loop | Timeout typed recoverable? | Observed success / failure latency |
| --- | --- | ---: | --- | --- | --- | --- |
| Constructor (`v3_constructor`, `planning.agents.run_constructor`) | `_run_structured` uses `settings.v3_timeout_stage1_seconds` (`planning/agents.py:35-95,281-310`) | **240 s default**. `V3_TIMEOUT_STAGE1_SECONDS` is not present in `.env`; the present `V3_TIMEOUT_ARCHITECT_SECONDS=300` is a different name and does not feed this setting. | 1 (`RetryPolicy` at `agents.py:84-87`) | No automatic outer repair. A user correction/clarification is a new request, not a provider retry. | Runner classifies timeout/transport retryable, but this pre-generation call has no native checkpoint; API-level failure must be handled by the caller. | Pending live telemetry |
| Path planner (`v2_path_planner`, `planning.agents.run_path_planner`) | Same `_run_structured` stage-1 timeout (`agents.py:35-95`) | **240 s default**; no effective `.env` override found for `v3_timeout_stage1_seconds`. | 1 per call | Two fresh attempts (`for attempt in (1, 2)`, `agents.py:108-169`), second carries validation errors/previous output. | Timeout is typed retryable in runner; outer loop retries once. This is pre-generation path planning, so no `failed_recoverable` generation state is persisted here. | Pending live telemetry |
| Path chat editor (`v2_path_chat_editor`, `planning.agents.run_plan_chat_edit`) | Same `_run_structured` stage-1 timeout (`agents.py:35-95,313-388`) | **240 s default**; no effective `.env` override found. | 1 per call | Two fresh attempts (`agents.py:336-388`), second is targeted repair. | Typed runner retryable; caller-level repair retries once, but this is an upstream edit request rather than native worker checkpoint recovery. | Pending live telemetry |
| Native path structural planner (`v2_path_structural_planner`, `planning.agents.run_path_structural_planner`) | Same `_run_structured` stage-1 timeout; native path selects page prompt when `native_whole_lesson` is true (`planning/agents.py:185-273`, `planning/bridge.py:590-625`) | **240 s default**; no effective `.env` override found for `v3_timeout_stage1_seconds`. | 1 per call | Two fresh attempts (`agents.py:218-273`) with fixed-slot/context validation repair. | Typed runner retryable; this runs before the generation row is created in path preparation, so failures surface as preparation errors rather than native checkpoint recovery. | Pending live telemetry |
| Native item generation (`v3_item_executor`, `v3_execution.executors.item_executor.execute_items_with_diagnostics`) | `run_llm(... RetryPolicy(max_attempts=1))` (`item_executor.py:124-151`); omitted `call_timeout_seconds` means `RetryPolicy` default (`runner.py:39`) | **120 s per provider attempt**, hard-coded runner default; no item-specific env override found. | 1 per outer attempt | Up to 3 outer attempts (`ITEM_MAX_ATTEMPTS=3`, `item_executor.py:29,107-109`); each attempt is journaled and classified by `item_diagnostics`. | Yes: timeout is classified as transport/retryable and worker persists a recoverable checkpoint (`whole_lesson/executor.py:322-344`). | Pending live telemetry |
| Teaching plan (`v2_lesson_approach_planner`, `whole_lesson.teaching_agent`) | `_call_teaching_model` passes `settings.page_lesson_plan_timeout_seconds` (`teaching_agent.py:67-96`) | **420 s**, `.env` `PAGE_LESSON_PLAN_TIMEOUT_SECONDS=420` (`backend/.env:291-296`). | 1 per call | Two fresh planner calls (`teaching_agent.py:146-220`); second is validation/contract repair. Native retry resumes the teaching checkpoint rather than rerunning items. | Yes: timeout remains typed transport failure; executor classifies it and targets `failed_recoverable`/`retry_teaching` (`whole_lesson/executor.py:322-344,959-969`). | Pending live telemetry |
| Form plan (`v2_form_planner`, `whole_lesson.form_agent`) | `_call_form_model` passes `settings.page_form_plan_timeout_seconds` (`form_agent.py:58-95`) | **120 s**, `.env` `PAGE_FORM_PLAN_TIMEOUT_SECONDS=120` (`backend/.env:291-296`). | 1 per call | Two fresh planner calls (`form_agent.py:160-214`); second is validation repair when applicable. Final exception is preserved/re-raised (`form_agent.py:217-225`). | Yes: timeout/transport is kept separate from contract repair (`is_transport_error`); worker records recoverable form failure and `retry_native` checkpoint. | Pending live telemetry |
| Page-object writers — standard (`v3_block_writer_standard`) | `_llm_write` passes `settings.page_standard_writer_timeout_seconds` (`generation/page_objects/registry.py:259-277`) | **180 s per provider attempt**, `.env` `PAGE_STANDARD_WRITER_TIMEOUT_SECONDS=180`. | `1 + settings.xplore_page_writer_retries`; env key is absent, so default **2 attempts** (`core/config.py:147`, `registry.py:270-276`). | `_write_validated_llm` makes a second logical call with a repair prompt after content validation failure (`registry.py:306-341`). Thus a malformed first result can consume up to two logical calls, each with the inner retry budget. | Yes: timeout is surfaced to native executor failure classification; content validation repair is distinct from transport retry. | Pending live telemetry |
| Page-object writers — fast (`v3_block_writer_fast`) | Same `_llm_write` path, fast tier (`registry.py:259-277`) | **90 s per provider attempt**, `.env` `PAGE_FAST_WRITER_TIMEOUT_SECONDS=90`. | Default **2 attempts** per logical call (`XPLORE_PAGE_WRITER_RETRIES` absent; `core/config.py:147`). | Same optional validation repair logical call as standard writers. `questions`/`choices` use approved deterministic records and do not invoke this provider call (`planning/model_tiers.py:67-79`). | Yes for provider timeout; native executor classifies retryable timeout separately from writer content repair. | Pending live telemetry |
| Visual provider (`visual_executor` -> active image provider) | Native dispatch invokes `execute_visual` (`whole_lesson/visual_dispatch.py:8-13,112-172`). Runtime bounds each visual order with `_timed_visual` and `_visual_deadline` (`v3_execution/runtime/runner.py:346-360`). | **45 s per frame/order** from `.env` `V3_TIMEOUT_VISUAL_FRAME_SECONDS=45` (`backend/.env:230-239`); diagram series multiplies by frame count. Active provider is xAI (`PIPELINE_IMAGE_PROVIDER=xai`, model `grok-imagine-image`, `.env:93-97,177-180`). xAI client has its own HTTP timeout of **120 s** for generation and **60 s** for edit (`media/providers/xai_image_client.py:76,145`). | Visual executor retries each order up to **2 executor attempts** (`V3_RETRY_VISUAL_MAX=1`, `visual_executor.py:461-462,585`; provider attempt counter is journaled). | Native dispatch processes each pending request once per dispatch; failed visual rows persist retryable visual state and `/visuals/retry` re-dispatches (`whole_lesson/visual_dispatch.py:187-248`). | Yes at native boundary: dispatch marks visual failure retryable; runtime deadline can cancel the provider call, and native retry action is `retry_visuals`. Provider-specific client exceptions are caught into `VisualStageError`, so exact underlying timeout class must be verified in live telemetry. | Pending live telemetry |

## Supporting configured values

The current local `.env` values relevant to this inventory are:

| Setting | Value | Source / effect |
| --- | ---: | --- |
| `PAGE_LESSON_PLAN_TIMEOUT_SECONDS` | 420 s | Teaching planner; `core.config.Settings.page_lesson_plan_timeout_seconds` |
| `PAGE_FORM_PLAN_TIMEOUT_SECONDS` | 120 s | Form planner |
| `PAGE_STANDARD_WRITER_TIMEOUT_SECONDS` | 180 s | Standard page writers |
| `PAGE_FAST_WRITER_TIMEOUT_SECONDS` | 90 s | Fast page writers |
| `XPLORE_PAGE_WRITER_RETRIES` | not set | Settings default 1; gives two inner attempts per logical writer call |
| `V3_TIMEOUT_VISUAL_FRAME_SECONDS` | 45 s | Runtime visual order/frame deadline |
| `V3_RETRY_VISUAL_MAX` | 1 | Two visual executor attempts |
| `V3_TIMEOUT_STAGE1_SECONDS` | not set | `settings.v3_timeout_stage1_seconds` therefore remains default 240 s |
| `V3_TIMEOUT_STAGE2_SECTION_SECONDS` | 100 s | Retained V3 section-expander path; not the native page-object writer timeout |
| `V3_TIMEOUT_GENERATION_TOTAL_SECONDS` | 600 s | Retained V3 runtime total cap; not a per-call native page timeout |

## Static findings and pending evidence

1. The native teaching planner is configured at 420 s, materially above the plan’s
   approximately-180-second silent-call target. This is recorded, not changed: live
   success/failure latency is required before recommending a setting.
2. Native item generation currently relies on the generic runner default of 120 s because
   its call site does not pass an item-specific timeout. This is a configuration fact to
   validate with telemetry, not a recommendation.
3. Writer timeouts are per provider attempt; writer validation repair and native checkpoint
   retry are separate layers. The live audit must report provider-call wall time separately
   from stage wall time.
4. Visual execution has three boundaries (provider client timeout, 45-second runtime frame
   deadline, and two executor attempts). A live visual run must record which boundary fired.
5. No observed-success or observed-failure latency is available from this static pass. M10
   telemetry must populate node, provider/model, attempt, start/end, elapsed time, outcome,
   and error class before M3 settings are revisited.

## Static commands run

```text
rg -n "run_llm\(|timeout|RetryPolicy|V3_TIMEOUT|PAGE_.*TIMEOUT|V3_MAX_RETRIES" apps/textbook-agent/backend/src
Get-Content apps/textbook-agent/backend/.env
Get-Content apps/textbook-agent/backend/src/core/config.py
```

No provider, browser, worker, database, or source-setting mutation was performed for this
audit.
