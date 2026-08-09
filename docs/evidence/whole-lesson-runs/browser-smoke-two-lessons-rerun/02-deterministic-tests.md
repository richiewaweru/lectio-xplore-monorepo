# 02 — Deterministic tests

All commands were run from `apps/textbook-agent/backend` unless noted.

## New and changed test modules

| File | Status | Covers |
|---|---|---|
| `tests/planning/test_path_structural_models.py` | new | prompt-facing schema: card cardinality, tolerated drift, JSON-schema shape |
| `tests/planning/test_path_structural_validation.py` | new | context invariants, and the invariants deliberately *not* enforced |
| `tests/planning/test_path_structural_repair.py` | new | the two-attempt repair loop |
| `tests/planning/test_agent_retry_boundary.py` | new | `retries={"output": 0}` at the three constrained sites |
| `tests/test_capture_whole_lesson_evidence_script.py` | new | run-slug validation and traversal rejection |
| `tests/planning/test_path_bridge.py` | modified | fixed the one test that mutated a now-typed model; added a native blocks/components case |
| `tests/v3_execution/test_v3_config_models.py` | modified | node reasoning policy, and that the change is scoped |

## Focused runs

```text
uv run pytest -q tests/planning/test_path_structural_models.py \
                 tests/planning/test_path_structural_validation.py \
                 tests/planning/test_path_structural_repair.py
30 passed in 29.07s
```

```text
uv run pytest -q tests/planning/test_agent_retry_boundary.py \
                 tests/test_capture_whole_lesson_evidence_script.py \
                 tests/v3_execution/test_v3_config_models.py
47 passed, 1 warning in 20.65s
```

```text
uv run pytest -q tests/planning/test_path_bridge.py
14 passed, 1 warning in 29.55s
```

```text
uv run pytest -q tests/planning tests/v3_execution
295 passed, 1 failed        # the one failure is pre-existing, see below
```

The single failure in that last run is
`tests/planning/test_path_contracts.py::test_phase5_prompts_are_verbatim[component-selector-v1.txt-4-Component Selector]`.
It is pre-existing and self-contradicting within the repository: the test asserts
`resources/component-selector-v1.txt` matches an authority-doc section verbatim,
while `scripts/verify_whole_lesson_prompts.py:40` asserts the same file *starts
with* a `# v1 ONLY — do not use on the native path` banner that the authority
section does not contain. Both cannot hold. Neither file was touched by this
work — `git status` reports the prompt unmodified — so the comparison is
identical to what it was at the starting commit.

## Notable assertions worth calling out

**The silent-data-loss guard.**
`test_statement_survives_the_dump_so_the_bridge_can_rename_it` pins that
`model_dump(mode="json", exclude_none=True)` keeps `statement` and omits
`description`. `planning/bridge.py:176` renames `statement` to `description` only
when `description` is *absent from the dict*. Without `exclude_none`, the dump
would carry `description: None`, the rename would never fire, and the
misconception would be dropped at bridge.py:179-181 with no exception and no log
— a card quietly losing content, which then changes `misconception_count` and the
skeleton preview. This is the most dangerous failure mode in the change and it
would not surface as an error.

**The escape-hatch guard.**
`test_accepts_zero_cards_when_objective_concern_is_raised` and the two
`*_short_circuits_every_other_check` tests pin the decision to use `max_length=1`
without `min_length=1`. If a future edit adds the lower bound, a planner response
meaning "this objective does not fit the skeleton" becomes a schema error and its
message is destroyed before the bridge can surface it.

**The negative-space guard.**
`test_ignores_rewritten_objective` and `test_ignores_wrong_card_id` assert the
validator returns *no* errors for drift the bridge assigns away. These exist to
stop a well-meaning future change from "tightening" the validator into
re-checking values that `bridge.py:166-167` already overwrites, which would turn
silent corrections into hard preparation failures.

**The empirical pydantic-ai check.**
`test_no_output_retry_constant_disables_only_output_retries` constructs a real
`Agent` and asserts `_max_output_retries` moves 1 → 0 while `_max_tool_retries`
is unchanged. The parameter name and semantics were verified against the
installed 1.107.1 rather than assumed; `output_retries=` is deprecated there and
was not used.

## Backend lint — `ruff check src/ tests/`

**17 errors, unchanged from the starting commit.**

Proven rather than asserted: the pristine `bb56f89` tree was extracted with
`git archive` and linted with the same ruff binary and config. Both trees report
an identical set of 17 errors (unused imports across `contracts/lectio_page.py`,
`page_blocks.py`, `whole_lesson/service.py`, `whole_lesson/worker.py`, several
test modules, and one `F822` in `v3_execution/prompts/item_prompt.py`).

One error *was* introduced during this work — an `F821` for an unimported
`AsyncSession` annotation in a new bridge test — and it was fixed by matching the
file's existing convention of unannotated fixtures.

So `backend-ruff`, and therefore `validate_repo.py --scope backend`, was already
failing before this work began. No new lint error was added.

## Full backend suite — the comparison that matters

`validate_repo.py --scope backend` runs `ruff check src/ tests/` then the full
`pytest`. Both were measured on this branch and on a pristine `bb56f89` tree
extracted with `git archive`, using the same interpreter and the same `.env`
(copied into the baseline tree — without it, model slots resolve to the shipped
Anthropic defaults instead of DeepSeek, and the comparison is meaningless):

| Tree | Result |
|---|---|
| `bb56f89` (pristine, with `.env`) | **152 failed, 551 passed** in 21m 05s |
| This branch | **93 failed, 675 passed** in 23m 07s |

This branch has **59 fewer failures and 124 more passes** than the commit it
started from. The 65-test increase in total count is exactly the new tests added
here, all of which pass.

The full suite is heavily order-dependent under this `.env`: every file that
fails in the full run passes when run on its own. For example
`tests/planning/test_phase02_visual_pdf_routes.py` and
`tests/planning/test_phase02_worker_failure_policy.py` contribute 20 failures to
the full run and give `20 passed` when invoked directly. The same instability is
present at the starting commit, more severely.

For completeness, the baseline was also run *without* `.env` (61 failed, 642
passed in 5m 49s) — that configuration resolves every model slot to Anthropic and
is much faster, which is why the `.env` copy was necessary for a fair comparison.

**Conclusion:** the pre-existing suite is unreliable in full-run mode and was
already red at the starting commit, on both lint and tests. This change does not
add to that and measurably reduces it. Fixing the underlying test pollution is
out of scope here and is not claimed.

## Prompt verification

```text
uv run python scripts/verify_whole_lesson_prompts.py
prompt_checksums=ok
evidence_root=C:\Projects\lectio\docs\evidence\whole-lesson-runs
EXIT=0
```

No prompt file was modified, so the two inline SHA-256 pins at
`verify_whole_lesson_prompts.py:33-34` did not need updating. The structural
planner's contract was tightened through pydantic field *descriptions*, which
live in `planning/models.py`, not in the prompt resource.

## Migration proof

Run against a disposable database created and dropped on the local server; the
browser-run database was never used for migration experiments.

```text
created scratch database lectio_migration_proof
INFO  [alembic.runtime.migration] Running upgrade 20260803_0031 -> 20260806_0032,
      reconcile development databases already stamped 20260806_0032
alembic upgrade head: OK
scratch alembic_version = ['20260806_0032']
scratch table count = 30
RESULT: PASS
dropped scratch database lectio_migration_proof
```

`uv run alembic heads` reports a single head, `20260806_0032`, before and after.
The real backend now starts with migrations enabled and no `CommandError`.

## Frontend

```text
npm run test
Test Files  78 passed (78)
Tests  323 passed (323)
Duration  557.93s
```

```text
npm run check
COMPLETED 4256 FILES 1 ERRORS 2 WARNINGS 2 FILES_WITH_PROBLEMS
```

The one error is a pre-existing type mismatch in
`src/routes/studio/generations/[id]/+page.svelte:29` (`BookletStatus | "final"`
not assignable to `BookletStatus`), plus two unused-CSS-selector warnings in
`src/routes/units/[id]/+page.svelte`. This change touches **no** frontend file,
so all three predate it.
