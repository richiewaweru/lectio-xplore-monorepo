# 01 — Implementation summary

Starting commit: `bb56f8997a1a4a0a28645c2f92820bd5dcf8afd7`
(`fix(native-execution): close visual callback invariants`), branch
`pageobject-integration`. Working tree carried only untracked evidence and the
untracked `.tmp-xplore-native-phase02-pack/`; the previous run's evidence under
`browser-smoke-two-lessons/` was left intact.

## Fix A — strongly typed structural planner output

`src/planning/models.py` gained four prompt-facing models —
`PathStructuralComponentSlot`, `PathStructuralMisconception`,
`PathStructuralCard`, `PathStructuralSection` — and `PathStructuralPlan` now
reads:

```python
class PathStructuralPlan(StrictModel):
    anchor: PathAnchor
    cards: list[PathStructuralCard] = Field(default_factory=list, max_length=1, ...)
    sections: list[PathStructuralSection] = Field(default_factory=list)
    deviation_request: PathDeviationRequest | None = None
    objective_concern: str | None = None
```

`list[dict]` is gone from both fields.

### Two deliberate departures from the brief

**1. Nested models are `extra="ignore"`, not `extra="forbid"`.**

`structured_output_type_for_model` (`v3_execution/llm_helpers.py:27`) wraps these
types in `PromptedOutput` for DeepSeek, which renders the JSON schema *into the
prompt text*. There is no constrained decoding. `extra="forbid"` therefore cannot
stop the model emitting a stray key — it can only make us reject more of what it
sends. Meanwhile `planning/bridge.py:157-198`
(`_normalize_page_concept_card_payload`) is an existing, deliberate tolerance
layer that absorbs exactly the drift the planner is known to produce: per-card
`concept_id` / `definition` / `body` / `examples`, per-misconception `rationale`,
`statement` in place of `description`, and id-only misconception shells.

Making the nested models strict would have converted every one of those
silently-repaired cases into a new hard 422 — trading a known bug for an unknown
one. The models are typed (which is what the provider needed) and tolerant (which
is what the bridge already assumes). Field *descriptions* carry the contract the
schema cannot enforce, including an explicit instruction that the section key is
`id` and not `slot_id`.

**2. `cards` has `max_length=1` but no `min_length=1`.**

`bridge.py:211-216` checks `deviation_request` and `objective_concern` *before*
the card count. Those are the planner's legitimate escape hatches: a response
meaning "this objective does not fit the skeleton" carries no cards and a concern
message. A schema-level lower bound would turn that into a validation error and
destroy the concern text before the bridge could surface it as a readable 409.
`max_length=1` is what actually stopped the observed three-card failures; the
lower bound moved into the context validator, which runs after the escape hatches.

Both departures were put to the user and approved before implementation.

### Bridge integration — `src/planning/bridge.py`

```python
card_payload = generated.cards[0].model_dump(mode="json", exclude_none=True)
...
section_payload = generated_section.model_dump(mode="json", exclude_none=True)
section_payload.setdefault("components", [])
...
plan_for_slot = page_block_plans.get(generated_section.role or generated_section.id)
```

`exclude_none=True` is part of the contract, not formatting.
`_normalize_page_concept_card_payload` renames `statement` to `description` only
when `description` is *absent from the dict*. A plain `model_dump()` would emit
`description: None`, the rename would never fire, and the misconception would be
dropped at bridge.py:179-181 — no exception, no log, just a card with fewer
misconceptions, which then shifts `misconception_count` and the skeleton preview.
This is pinned by
`tests/planning/test_path_structural_models.py::test_statement_survives_the_dump_so_the_bridge_can_rename_it`.

`setdefault("components", [])` is likewise required: `SectionPlan.components` has
no default and `exclude_none` drops the key when the native planner omits it.

Section `card_id` is now coerced to `lesson.concept_id` rather than validated,
consistent with how the card's `id` and `objective` are already assigned.

## Fix B — one real structural repair attempt

`run_path_structural_planner` (`src/planning/agents.py`) now owns at most two
attempts. Attempt 2 fires only after schema or context validation failure and
carries `{"repair": {"instruction", "previous_output", "validation_errors"}}`
merged into the fixed context. Each attempt is a fresh `_run_structured` call, so
a new `Agent` and no provider message history. Trace ids differ per attempt
(`…:structural1`, `…:structural2`). A second failure raises
`PathStructuralContextError`, which subclasses `ValueError` and therefore maps to
HTTP 422 with the joined violations via `planning/routes.py:246`.

`_schema_errors()` handles a non-obvious detail: with in-library output retry
disabled, a schema failure does **not** arrive as a bare `ValidationError`.
pydantic-ai raises `UnexpectedModelBehavior("Exceeded maximum output retries
(0)")` whose `__cause__` is a `ToolRetryError` whose `tool_retry.content` holds
the pydantic error list. The helper walks that chain, falls back to a direct
`ValidationError`, then to the exception text. Because raw model text never
escapes `_run_structured`, `previous_output` is `None` on that branch; the
pydantic messages are actionable on their own.

New leaf module `src/planning/structural_validation.py` holds
`validate_path_structural_result(plan, *, expected_slots)`. It lives outside the
bridge because `bridge.py:25` imports `planning.agents`, so placing it there would
close an import cycle.

It enforces: exactly one card (only when neither escape hatch is set), section
count against the slots, section `id` and `role` equal to the slots *in order*, no
duplicate ids, non-blank titles, and a null first `transition_note`.

It deliberately does **not** check `cards[0].id` or `cards[0].objective` against
the lesson. `bridge.py:166-167` assigns both — the code comment reads "Assignment
makes drift impossible" — so validating raw output there would convert cases the
bridge silently corrects today into hard failures. `expected_slots` is derived
from `fixed_context["slots"][*]["slot_id"]`, which is the same list the bridge
checks against, so the two cannot disagree.

## Fix C — model/node policy for constrained nodes

`src/v3_execution/config/models.py`:

```python
V2_PATH_STRUCTURAL_PLANNER: False,   # was "high"
V2_FORM_PLANNER: False,              # was "low"
```

`V2_PATH_PLANNER` and `V2_LESSON_APPROACH_PLANNER` keep `"high"`.

This suppresses `openai_reasoning_effort` and
`extra_body={"thinking": {"type": "enabled"}}` for those two nodes
(`get_v3_model_settings`, models.py:205-227).

Note this is only meaningful because this machine's `.env` overrides every slot to
DeepSeek (`V3_FAST_MODEL_NAME=deepseek-v4-flash`,
`V3_STANDARD_MODEL_NAME=deepseek-v4-pro`, provider `openai_compatible`). Against
the shipped Anthropic defaults in `V3_DEFAULT_SPECS` the reasoning table is inert,
because the gate at models.py:214-218 requires an OpenAI-compatible `deepseek-`
model. Both changes are therefore no-ops for Anthropic deployments.

**Caveat carried forward:** disabling reasoning on `V2_PATH_STRUCTURAL_PLANNER` is
unproven. Blocker 1 was schema drift, not an empty response — the planner did
return content. It is set to `False` as the brief requires and to keep one
variable set for the rerun, but it should be re-evaluated toward `"medium"` with
evidence once the typed schema and repair loop have been observed working.

## Fix D — the DeepSeek request boundary

Investigated rather than assumed. Installed pydantic-ai is **1.107.1**
(`pyproject.toml` pins `>=1.102.0,<2`). `Agent.__init__` accepts
`retries: int | AgentRetries | None`; `output_retries=` still works but only via
`**_deprecated_kwargs` with a `DeprecationWarning`, so it was not used.

On the PromptedOutput text path, a validation failure raises `ToolRetryError` and
`CallToolsNode` (`_agent_graph.py:1248`) appends a new `ModelRequestNode` to the
**same** `message_history`. The model's own prior assistant message is therefore
replayed to the provider. When that message was reasoning-only its `content` is
empty, and DeepSeek answers `HTTP 400: Invalid assistant message: content or
tool_calls must be set` — the observed `planning_forms` failure.

`v3_execution/llm_helpers.py` now exports:

```python
NO_OUTPUT_RETRY = {"output": 0}
```

applied at the three call sites that each own an explicit outer repair loop:
`planning/agents.py` (`_run_structured`),
`planning/whole_lesson/form_agent.py` (`_call_form_model`),
`planning/whole_lesson/teaching_agent.py` (`_call_teaching_model`).

`llm_helpers.run_json_agent` was deliberately **not** changed — it has no outer
loop, so removing its in-library retry would be a straight regression. A test
pins that exclusion.

Verified empirically rather than by reading docs: constructing an `Agent` with
`retries={"output": 0}` moves `_max_output_retries` from `1` to `0` and leaves
`_max_tool_retries` untouched.

Repair now has exactly one owner per node: a failure surfaces immediately to our
loop instead of being replayed inside the library.

## Fix E — Alembic revision 20260806_0032

Searched before writing anything: `git log --all -S"20260806_0032"` (no hits),
the full migrations directory history, `git stash list` (one unrelated stash,
checked), and `git rev-list --all --objects` (only SHA coincidences containing the
digits). The revision exists in no commit, branch, stash, or dangling object.
Recovery (Resolution A) was therefore impossible.

Added `versions/20260806_0032_reconcile_lost_revision.py`:
`revision = "20260806_0032"`, `down_revision = "20260803_0031"`, empty `upgrade()`
and `downgrade()`, with a docstring recording that schema inspection found no
delta from ORM expectations (29 model tables vs 31 database tables, zero missing
tables or columns). The database was never stamped backward and no row was edited.

`RUN_MIGRATIONS_ON_STARTUP=false` is no longer used anywhere. `.env` already had
`RUN_MIGRATIONS_ON_STARTUP=true`; the previous run's workaround was a process
environment variable only, and it has been dropped.

## Fix F — evidence capture CLI

`scripts/capture_whole_lesson_evidence.py` replaced the hard-coded four-element
`choices` list with `run_slug()` (`^[a-z0-9][a-z0-9-]{0,63}$`) plus
`resolve_run_dir()`, which resolves the joined path and refuses anything that does
not sit directly under `EVIDENCE_ROOT`. The four official run slugs still pass;
`browser-smoke-science` and `browser-smoke-economics` now pass; traversal,
absolute paths, backslashes, uppercase, spaces, underscores, leading hyphens, the
empty string and over-length slugs are rejected. `run_whole_lesson_proof.py` keeps
its own `RUNS` whitelist, so the proof driver's surface did not widen.

## Diagnostics

New `src/planning/planner_diagnostics.py` exposes
`log_planner_attempt_failed(...)`, used by both the structural and form planners.
It records node, model name, provider family, attempt, error class (or
`context_validation` when the model answered but failed our checks), HTTP status,
the node's reasoning policy, error count, the first five validator strings,
whether a repair payload was attached, and whether a retry follows.

It never logs API keys, base-url credentials, system prompts, user payloads,
`previous_output`, or raw model text. Validator strings contain only slot ids.
