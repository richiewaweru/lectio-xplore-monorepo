# P5 — Unified correction ownership implementation

## Result

Implementation is ready for Sol's gate review. P5 is not marked complete until that review passes.

The Learn `LLMAuthoringProvider` now calls `run_structured_agent` with generic JSON output, `retries={"output": 0}`, and `RetryPolicy(max_attempts=1)`. This makes one adapter invocation equal one `run_llm` dispatch. The AuthoringEngine treats malformed structured output as repair input for the same item, marks the reservation dispatched, and runs normal schema/registered-validator correction under the same budget. Transport failures consume an ambiguous budget slot and may not enter semantic repair. Permanent auth/config/provider errors become terminal `PROVIDER_FAILURE`.

Document writer quality and normalized-node checks, composer schema/allowlist/coverage semantics, and Learn interaction-envelope validation now run as AuthoringEngine validators. The interaction contract is checked before the ready checkpoint is committed. Composer heuristic fallback is allowed only when explicitly enabled and the engine exhausts semantic correction; generic missing-provider and transport failures do not permit fallback. The Print production caller explicitly selects `heuristic_only` when no LLM composer was intended. That mode is included in checkpoint compatibility, consumes a declared fallback budget slot, commits an outcome of `heuristic_fallback`, and stamps the selection trace's reason as degraded. Print teaching/form retain their separate bounded correction owners; deterministic tests classify transport, timeout, programming, provider, budget, and semantic exhaustion separately.

## Validation

From `apps/textbook-agent/backend`:

```text
uv run pytest tests/authoring_correction/test_a02_shared_authoring_engine.py tests/generation/test_writer_repair.py tests/authoring_correction/test_a04_learn_authoring.py tests/learn/authoring/test_builder_document_v2.py tests/print_learn/test_composition_bridge.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/planning/test_phase02_failure_classification.py tests/authoring_correction/test_a00_arbitrary_answers.py tests/authoring_correction/test_a06_integrated_offline.py tests/print_learn/test_p08_integration_gates.py tests/application/test_p04_learn_worker.py -q
uv run python ../tools/agent/check_architecture.py --format text
```

Result: **72 passed, 5 existing warnings in 44.40 s.** The warnings are the existing Pydantic `schema` field shadowing warning and PydanticAI `AgentRunResult.usage` deprecation warnings from the P08 integration suite. Architecture check result: **No architecture violations found** (exit 0).

The added provider-boundary test replaces `run_llm` below `run_structured_agent`, then invokes the actual `LLMAuthoringProvider` and `AuthoringEngine`. For a malformed structured response followed by a valid correction it proves two actual dispatches equal two consumed/dispatched ledger slots. HTTP 429 and `TimeoutError` each prove one actual dispatch equals one consumed ambiguous slot and no semantic repair. A programming `AssertionError` proves one dispatch is accounted as dispatched, terminates as `PROVIDER_FAILURE`, and does not trigger correction.

The P08 Print integration exposed that the production caller intentionally has no LLM composer. The fix makes that choice explicit through `heuristic_only`; a focused bridge test verifies the output selection trace carries `heuristic fallback:` reasons, the budget declares/consumes a fallback slot, and the checkpoint records `heuristic_fallback`. The integrated P08 test also asserts the persisted Print selection trace exposes that degraded path. Generic `provider=None` calls continue to fail closed.

Scoped lint from `apps/textbook-agent/backend`:

```text
uv run ruff check src/infra/authoring/models.py src/infra/authoring/__init__.py src/infra/authoring/engine.py src/v3_execution/llm_helpers.py src/document/writer.py src/document/composer.py src/learn/generation/authoring_adapter.py src/learn/generation/interaction_writer.py src/print/generation/whole_lesson/failure_policy.py tests/authoring_correction/test_a02_shared_authoring_engine.py tests/authoring_correction/test_a00_arbitrary_answers.py tests/print_learn/test_composition_bridge.py tests/reliability/test_p03_durable_budget_checkpoints.py tests/planning/test_phase02_failure_classification.py
```

Result: **All checks passed.** `git -c core.whitespace=cr-at-eol diff --check` also passed. No P6 implementation has started.

## Changed areas

- `infra/authoring`: provider classification, one-dispatch adapter, engine accounting, and same-item structured-output repair.
- `v3_execution/llm_helpers.py`: optional explicit provider `RetryPolicy`; existing callers keep their prior default.
- `document/writer.py` and `document/composer.py`: quality and semantic validation inside engine; semantic-only explicit composer fallback.
- `learn/generation/authoring_adapter.py` and `interaction_writer.py`: interaction validation before checkpoint readiness.
- Print failure policy and focused tests: distinguish transport, terminal provider, budget, and semantic correction exhaustion.

## Remaining gate review

Sol should inspect the scoped diff and P5 gate claims before P5 is marked PASS. P6 remains blocked on that gate decision. Print planners intentionally remain separate correction owners, as approved in the P5 design checkpoint.
