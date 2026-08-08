## Phase 02 report — item generation observability

### Files changed
- `src/v3_execution/executors/item_diagnostics.py` (new)
- `src/v3_execution/executors/item_executor.py` — attempt journal, correlation IDs, outer retry budget
- `src/generation/v3_studio/router.py` — `_generate_shared_pack_items` persists attempts[]
- `tests/v3_execution/test_phase02_item_observability.py` — I01–I05

### Behavior
- Every item provider call is correlated (`item:{generation}:{card}:{nonce}`)
- Attempts record latency_ms + class: OK | TRANSPORT | TIMEOUT | RATE_LIMIT | CONTRACT | SEMANTIC
- Hidden `run_llm` retries removed for items (`RetryPolicy(max_attempts=1)`); outer loop owns budget=`ITEM_MAX_ATTEMPTS=3` (unchanged)

### Tests
I01–I05 + existing item_executor tests: passed
