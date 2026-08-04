# Textbook Generator v3 — Proposal 5: Model Configuration

## Purpose

v3 does not use a LangGraph pipeline. It uses standalone async executor
functions orchestrated by a runner. The v2 pipeline's node-to-slot registry,
draft/balanced/strict mode tiering, and per-node concurrency/timeout/retry
env vars were designed for that pipeline shape and do not apply to v3.

This proposal defines the model configuration for every v3 node, reusing
the existing `core.llm` infrastructure (`ModelSlot`, `ModelSpec`, `build_model`)
rather than the pipeline-specific layer above it. It also identifies which
v2 env vars carry forward and which are dropped.

**Scope:** v3 model slot definitions · node-to-model mapping · timeout budgets ·
retry policy · concurrency policy · env var changes

**Out of scope:** Staging environment · production switchover · database
migrations · auth changes · image provider changes

**Codebase:** Backend only. New file `backend/src/v3_execution/config/models.py`.
No frontend changes. No Lectio changes.

---

## The Key Difference from v2

v2 had three generation modes (draft/balanced/strict) that swapped Haiku
for Sonnet as quality demands increased. Every node picked from a slot
profile determined by the mode.

v3 has no modes. Each node is assigned the right model permanently based
on its role. The Lesson Architect always uses Opus because it is the
reasoning engine the whole system depends on — its quality cannot be
traded for speed. Executors use Sonnet because they produce the actual
student-facing content and quality matters. Fast extraction tasks use
Haiku because they are structured, low-creativity calls.

```
Role                    Model       Reasoning
────────────────────────────────────────────────────────
Lesson Architect        Opus        Extended thinking. Brain of the system.
                                    Quality is non-negotiable.

Signal Extractor        Haiku       Fast structured extraction.
                                    No creativity needed.

Clarification loop      Haiku       Simple question generation from gaps.
                                    Low stakes, fast.

Section Writer          Sonnet      Quality prose. Register and constraints
                                    must be followed precisely.

Question Writer         Sonnet      Cognitive demand must be exact.
                                    Quality determines learning outcome.

Answer Key Generator    Haiku       Formatting existing answers.
                                    Not generative — answers are precomputed.

LLM Coherence Reviewer  Sonnet      Judgment quality matters.
                                    Catching real issues requires reasoning.

Visual Executor         xAI         grok-imagine-image via XAIImageClient.
                                    Already implemented in pipeline.
                                    Not a text model.
```

---

## New Model Slot

The existing `core.llm.ModelSlot` has `FAST` and `STANDARD`. v3 adds
`PREMIUM` for the Lesson Architect. This is the only change to `core.llm`.

**File:** `backend/src/core/llm/__init__.py` (add one line)

```python
class ModelSlot(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"    # new — Opus with extended thinking
```

This addition is backward-compatible. v2 nodes never use `PREMIUM`.
The env var pattern follows the same convention: `V3_PREMIUM_PROVIDER`,
`V3_PREMIUM_MODEL_NAME`.

**Fallback if `core.llm` change causes import or type risk:**
Keep `ModelSlot.PREMIUM` in a v3-local enum in
`backend/src/v3_execution/config/models.py` instead of adding it to
`core.llm`. The v3 config module imports its own slot enum and never
touches the shared one. Prefer adding to `core.llm` if tests pass cleanly
— only use the v3-local enum if there is a concrete conflict.

---

## v3 Model Configuration File

**File:** `backend/src/v3_execution/config/models.py`

```python
from __future__ import annotations

import os
from core.llm import ModelFamily, ModelSlot, ModelSpec, build_model

# ── Node names ────────────────────────────────────────────────────────────────

SIGNAL_EXTRACTOR = "signal_extractor"
CLARIFICATION = "clarification"
LESSON_ARCHITECT = "lesson_architect"
SECTION_WRITER = "section_writer"
QUESTION_WRITER = "question_writer"
ANSWER_KEY_GENERATOR = "answer_key_generator"
LLM_COHERENCE_REVIEWER = "llm_coherence_reviewer"

# ── Node → slot mapping ───────────────────────────────────────────────────────

V3_NODE_SLOTS: dict[str, ModelSlot] = {
    SIGNAL_EXTRACTOR: ModelSlot.FAST,
    CLARIFICATION: ModelSlot.FAST,
    LESSON_ARCHITECT: ModelSlot.PREMIUM,
    SECTION_WRITER: ModelSlot.STANDARD,
    QUESTION_WRITER: ModelSlot.STANDARD,
    ANSWER_KEY_GENERATOR: ModelSlot.FAST,
    LLM_COHERENCE_REVIEWER: ModelSlot.STANDARD,
}

# ── Default model specs ───────────────────────────────────────────────────────

# IMPORTANT: Model names below must be verified against currently supported
# Anthropic model IDs in the project environment before coding.
# Use the model IDs already configured in the project or environment.
# Treat these names as reference placeholders, not guaranteed strings.
V3_DEFAULT_SPECS: dict[ModelSlot, ModelSpec] = {
    ModelSlot.FAST: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-haiku-4-5-20251001",  # verify current ID
    ),
    ModelSlot.STANDARD: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-sonnet-4-6",           # verify current ID
    ),
    ModelSlot.PREMIUM: ModelSpec(
        family=ModelFamily.ANTHROPIC,
        model_name="claude-opus-4-6",             # verify current ID
    ),
}

# ── Extended thinking config (Lesson Architect only) ──────────────────────────

LESSON_ARCHITECT_THINKING_BUDGET = int(
    os.getenv("V3_ARCHITECT_THINKING_BUDGET_TOKENS", "10000")
)

# ── Env var overrides (same pattern as v2 PIPELINE_* vars) ───────────────────
# V3_FAST_PROVIDER, V3_FAST_MODEL_NAME, V3_FAST_API_KEY_ENV
# V3_STANDARD_PROVIDER, V3_STANDARD_MODEL_NAME, V3_STANDARD_API_KEY_ENV
# V3_PREMIUM_PROVIDER, V3_PREMIUM_MODEL_NAME, V3_PREMIUM_API_KEY_ENV

def _load_slot_spec(slot: ModelSlot) -> ModelSpec:
    prefix = f"V3_{slot.name}"
    provider = os.getenv(f"{prefix}_PROVIDER")
    model_name = os.getenv(f"{prefix}_MODEL_NAME")
    if provider and model_name:
        return ModelSpec(
            family=ModelFamily(provider),
            model_name=model_name,
            api_key_env=os.getenv(f"{prefix}_API_KEY_ENV", "ANTHROPIC_API_KEY"),
        )
    return V3_DEFAULT_SPECS[slot]

def get_v3_model(node_name: str):
    """Return a built model instance for a v3 node."""
    slot = V3_NODE_SLOTS[node_name]
    spec = _load_slot_spec(slot)
    return build_model(spec)

def get_v3_spec(node_name: str) -> ModelSpec:
    """Return the ModelSpec for a v3 node (for reporting)."""
    slot = V3_NODE_SLOTS[node_name]
    return _load_slot_spec(slot)
```

---

## Timeout Budgets

v2 had per-node timeout env vars for the LangGraph pipeline. v3 uses
async functions with `asyncio.wait_for`. Timeouts are defined in the
config and applied by the runner.

```python
# backend/src/v3_execution/config/timeouts.py

import os

V3_TIMEOUTS: dict[str, int] = {
    "signal_extractor":      int(os.getenv("V3_TIMEOUT_SIGNAL_SECONDS", "30")),
    "clarification":         int(os.getenv("V3_TIMEOUT_CLARIFY_SECONDS", "30")),
    "lesson_architect":      int(os.getenv("V3_TIMEOUT_ARCHITECT_SECONDS", "180")),
    "section_writer":        int(os.getenv("V3_TIMEOUT_SECTION_SECONDS", "90")),
    "question_writer":       int(os.getenv("V3_TIMEOUT_QUESTION_SECONDS", "60")),
    "answer_key_generator":  int(os.getenv("V3_TIMEOUT_ANSWER_KEY_SECONDS", "30")),
    "llm_coherence_reviewer":int(os.getenv("V3_TIMEOUT_REVIEWER_SECONDS", "60")),
    "visual_executor_frame": int(os.getenv("V3_TIMEOUT_VISUAL_FRAME_SECONDS", "45")),
    "assembly":              int(os.getenv("V3_TIMEOUT_ASSEMBLY_SECONDS", "30")),
    # Total generation cap — runner enforces this as an outer asyncio.wait_for
    # wrapping the entire run_generation() call. Prevents runaway generations.
    "generation_total":      int(os.getenv("V3_TIMEOUT_GENERATION_TOTAL_SECONDS", "600")),
}
```

Lesson Architect gets 180s because extended thinking with a 10k token
budget takes longer than a standard completion. Visual executor timeout
is per frame (one Imagen call), not per series.

---

## Retry Policy

v2 had per-node retry env vars. v3 uses `ExecutorOutcome.retried`
(defined in Proposal 2) with a simple policy per node type.

```python
# backend/src/v3_execution/config/retries.py

import os

V3_MAX_RETRIES: dict[str, int] = {
    "signal_extractor":       int(os.getenv("V3_RETRY_SIGNAL_MAX", "2")),
    "clarification":          int(os.getenv("V3_RETRY_CLARIFY_MAX", "1")),
    "lesson_architect":       int(os.getenv("V3_RETRY_ARCHITECT_MAX", "1")),
    "section_writer":         int(os.getenv("V3_RETRY_SECTION_MAX", "1")),
    "question_writer":        int(os.getenv("V3_RETRY_QUESTION_MAX", "1")),
    "answer_key_generator":   int(os.getenv("V3_RETRY_ANSWER_KEY_MAX", "1")),
    "llm_coherence_reviewer": int(os.getenv("V3_RETRY_REVIEWER_MAX", "1")),
    "visual_executor_frame":  int(os.getenv("V3_RETRY_VISUAL_MAX", "1")),
}
```

Lesson Architect gets max 1 retry — if Opus fails twice something is
genuinely wrong and the teacher should know. Visual executor per-frame
gets 1 retry — diagram series consistency can break on retry so
escalate quickly rather than looping.

---

## Concurrency Policy

v2 had per-mode concurrency env vars for sections, diagrams, and QC.
v3 uses `asyncio.gather` with a semaphore per executor type to prevent
overloading the Anthropic API with too many concurrent Opus/Sonnet calls.

```python
# backend/src/v3_execution/config/concurrency.py

import asyncio
import os

def make_semaphores() -> dict[str, asyncio.Semaphore]:
    return {
        # Lesson Architect: always 1 — one per generation, no parallel benefit
        "lesson_architect": asyncio.Semaphore(1),

        # Section writers: parallel across sections, but cap Sonnet concurrency
        "section_writer": asyncio.Semaphore(
            int(os.getenv("V3_CONCURRENCY_SECTION_MAX", "3"))
        ),

        # Question writers: parallel across sections
        "question_writer": asyncio.Semaphore(
            int(os.getenv("V3_CONCURRENCY_QUESTION_MAX", "3"))
        ),

        # Visual executor: Imagen has its own rate limits
        "visual_executor": asyncio.Semaphore(
            int(os.getenv("V3_CONCURRENCY_VISUAL_MAX", "2"))
        ),

        # Answer key: single call, no concurrency needed
        "answer_key_generator": asyncio.Semaphore(1),

        # Coherence reviewer: single call after all executors complete
        "llm_coherence_reviewer": asyncio.Semaphore(1),
    }
```

Default section concurrency of 3 gives a good balance between speed and
API load — a 5-section lesson runs in roughly 2 waves rather than 5
sequential calls.

**Scope of these semaphores:** Per-generation only. If three teachers
generate simultaneously, you get 3 × section concurrency across the
process. The existing `GENERATION_MAX_CONCURRENT_PER_USER` admission
control from v2 still applies and limits how many concurrent generations
a single user can run. A global `V3_GLOBAL_CONCURRENCY_STANDARD_MAX`
across all users is not implemented now — build it later if API pressure
becomes measurable. The per-generation semaphores are the right starting
point.

---

## env.example Changes

Drop all v2 pipeline-specific vars. Add v3 vars.

**v2 env vars — keep in .env.example, marked as legacy:**

Do not remove v2 pipeline env vars while v2 exists on its branch and
rollback is possible. Mark them clearly so they are not confused with v3:

```bash
# ── Legacy v2 pipeline vars — not used by v3 ─────────────────────────────────
# Keep until v2 branch is fully retired. Do not delete during v3 development.

PIPELINE_CONCURRENCY_DRAFT_SECTION_MAX=6
PIPELINE_CONCURRENCY_DRAFT_DIAGRAM_MAX=2
# ... (all existing v2 PIPELINE_* vars remain, labelled as legacy)
```

The coding agent must not remove any existing PIPELINE_* vars from
.env.example. Only add the new V3_* section beneath them.

**Add to .env.example:**
```bash
# ── v3 model slots ────────────────────────────────────────────────────────────
V3_FAST_PROVIDER=anthropic
V3_FAST_MODEL_NAME=claude-haiku-4-5-20251001
V3_FAST_API_KEY_ENV=ANTHROPIC_API_KEY

V3_STANDARD_PROVIDER=anthropic
V3_STANDARD_MODEL_NAME=claude-sonnet-4-6
V3_STANDARD_API_KEY_ENV=ANTHROPIC_API_KEY

V3_PREMIUM_PROVIDER=anthropic
V3_PREMIUM_MODEL_NAME=claude-opus-4-6
V3_PREMIUM_API_KEY_ENV=ANTHROPIC_API_KEY

# ── v3 Lesson Architect ───────────────────────────────────────────────────────
V3_ARCHITECT_THINKING_BUDGET_TOKENS=10000

# ── v3 timeouts (seconds) ─────────────────────────────────────────────────────
V3_TIMEOUT_SIGNAL_SECONDS=30
V3_TIMEOUT_CLARIFY_SECONDS=30
V3_TIMEOUT_ARCHITECT_SECONDS=180
V3_TIMEOUT_SECTION_SECONDS=90
V3_TIMEOUT_QUESTION_SECONDS=60
V3_TIMEOUT_ANSWER_KEY_SECONDS=30
V3_TIMEOUT_REVIEWER_SECONDS=60
V3_TIMEOUT_VISUAL_FRAME_SECONDS=45
V3_TIMEOUT_ASSEMBLY_SECONDS=30
V3_TIMEOUT_GENERATION_TOTAL_SECONDS=600  # outer cap for entire generation

# ── v3 retries ────────────────────────────────────────────────────────────────
V3_RETRY_SIGNAL_MAX=2
V3_RETRY_CLARIFY_MAX=1
V3_RETRY_ARCHITECT_MAX=1
V3_RETRY_SECTION_MAX=1
V3_RETRY_QUESTION_MAX=1
V3_RETRY_ANSWER_KEY_MAX=1
V3_RETRY_REVIEWER_MAX=1
V3_RETRY_VISUAL_MAX=1

# ── v3 concurrency ────────────────────────────────────────────────────────────
V3_CONCURRENCY_SECTION_MAX=3
V3_CONCURRENCY_QUESTION_MAX=3
V3_CONCURRENCY_VISUAL_MAX=2
```

**Keep unchanged:**
```
ANTHROPIC_API_KEY                  — same API key, all models
PIPELINE_IMAGE_PROVIDER=xai        — set to xai for v3
PIPELINE_IMAGE_BASE_URL            — https://api.x.ai/v1 (required for xai)
PIPELINE_IMAGE_API_KEY_ENV=XAI_API_KEY  — points to xAI key env var
XAI_API_KEY                        — xAI API key
GENERATION_MAX_CONCURRENT_PER_USER — admission control still applies
REPORT_OUTPUT_DIR                  — generation reports still written
DATABASE_URL                       — unchanged
JWT_SECRET_KEY etc                 — auth unchanged
```

xAI is the confirmed image provider for v3. `XAIImageClient` with
`grok-imagine-image` is already implemented and tested in
`pipeline/media/providers/xai_image_client.py`.

The visual executor in v3 uses the existing `get_image_client()` from
the pipeline media registry — no new image client code needed. The
registry reads `PIPELINE_IMAGE_PROVIDER=xai` and returns `XAIImageClient`
automatically.

**Visual provider is configurable via env, not hardcoded in the executor.**
If xAI has reliability issues, switching to a different provider requires
only an env var change — no code change. This is the correct approach:
the executor calls `get_image_client()` and works with whatever the
registry returns. Never hardcode a provider name inside the executor.

---

## What v2 Knowledge Carries Forward

The v2 pipeline configs were not wasted — they tell us what to watch for:

**Timeout lessons:** v2 set `PIPELINE_TIMEOUT_DIAGRAM_NODE_BUDGET_SECONDS=90`
with an inner per-call limit of 45s. v3 applies the same pattern:
`V3_TIMEOUT_VISUAL_FRAME_SECONDS=45` per xAI image call, enforced
in the visual executor, not globally. The xAI client uses a 60s
urllib timeout internally — the v3 frame timeout at 45s gives headroom
for the runner to cancel before the client's own timeout fires.

**Retry lessons:** v2 set diagram retries to 1 (`PIPELINE_RETRY_DIAGRAM_MAX_ATTEMPTS=1`)
because retrying image generation too many times wastes cost with
diminishing returns. v3 keeps the same policy for visual frames.

**Concurrency lessons:** v2 strict mode ran only 3 concurrent sections
to protect Sonnet API throughput. v3 defaults to 3 section writers
for the same reason. The Lesson Architect is always 1 — there's no
benefit to parallelising a single large reasoning call.

**Mode tiering lesson:** v2 draft/balanced/strict modes existed because
the system had no other way to signal quality requirements. v3 doesn't
need modes because each node is permanently assigned the right model.
The section writer always uses Sonnet. The Lesson Architect always uses
Opus. Quality is structural, not a teacher-selected dial.

---

## Generation Report Updates

The generation report (per-generation JSON with per-node latency, token
counts, and cost) gains v3 node entries.

Each executor outcome records:
```json
{
  "node": "section_writer",
  "section_id": "section_2",
  "model": "claude-sonnet-4-6",
  "slot": "standard",
  "input_tokens": 1240,
  "output_tokens": 380,
  "duration_ms": 4200,
  "retried": false,
  "ok": true
}
```

Lesson Architect records extended thinking token usage separately:
```json
{
  "node": "lesson_architect",
  "model": "claude-opus-4-6",
  "slot": "premium",
  "thinking_tokens": 8340,
  "input_tokens": 2100,
  "output_tokens": 1800,
  "duration_ms": 32000,
  "retried": false,
  "ok": true
}
```

Visual executor records image provider and model — not token counts:
```json
{
  "node": "visual_executor",
  "provider": "xai",
  "model": "grok-imagine-image",
  "visual_id": "l_shape_step_3",
  "frame_index": 2,
  "duration_ms": 39000,
  "retried": false,
  "ok": true
}
```

This gives visibility into cost per generation, flags where Opus
thinking budget is being under- or over-used, and surfaces image
generation latency and retry patterns per provider.

---

## Implementation Order

```
Step 1 — Add ModelSlot.PREMIUM to core.llm
  One line addition to ModelSlot enum
  Backward compatible — v2 nodes never use it
  Verify existing tests still pass

Step 2 — Write v3 model config
  Write backend/src/v3_execution/config/models.py
  get_v3_model() and get_v3_spec() functions
  Env var override pattern matching v2 convention

Step 3 — Write timeout and retry configs
  Write backend/src/v3_execution/config/timeouts.py
  Write backend/src/v3_execution/config/retries.py
  All values env-var overridable

Step 4 — Write concurrency config
  Write backend/src/v3_execution/config/concurrency.py
  Semaphore factory function
  Runner imports and applies semaphores in Wave 1

Step 5 — Wire into runner and executors
  Each executor imports get_v3_model(node_name)
  Runner wraps each executor with asyncio.wait_for(timeout)
  Runner applies semaphore per executor type
  Retry logic reads V3_MAX_RETRIES[node_name]

Step 6 — Update .env.example
  Drop all v2 PIPELINE_CONCURRENCY_*, PIPELINE_TIMEOUT_*,
  PIPELINE_RERENDER_*, PIPELINE_RETRY_* vars
  Add all V3_* vars with documented defaults

Step 7 — Update generation report
  Add v3 node entries to GenerationReportRecorder
  Lesson Architect records thinking_tokens separately
  Verify report JSON is valid for all four persona blueprints
```

---

## Non-Negotiable Rules for the Coding Agent

```
1.  ModelSlot.PREMIUM added to core.llm if tests pass cleanly.
    If core.llm change causes import/type risk, use a v3-local slot enum
    in v3_execution/config/models.py instead.
2.  V3 model config in backend/src/v3_execution/config/models.py.
    Does not import from pipeline.providers.registry.
3.  Model names treated as placeholders — verify against currently
    supported Anthropic model IDs in the project before coding.
4.  Lesson Architect always uses ModelSlot.PREMIUM (Opus) — never STANDARD.
5.  Extended thinking always enabled for Lesson Architect —
    budget from V3_ARCHITECT_THINKING_BUDGET_TOKENS.
6.  Section Writer and Question Writer always use ModelSlot.STANDARD (Sonnet).
7.  Signal Extractor, Clarification use ModelSlot.FAST (Haiku).
8.  Answer Key Generator uses FAST only when expected_answer present on
    every question. Escalates to STANDARD if full_working is required
    and expected_working is missing.
9.  Visual executor calls get_image_client() from existing pipeline media
    registry — never hardcodes a provider name in the executor code.
    xAI is the confirmed v3 provider, set via PIPELINE_IMAGE_PROVIDER=xai.
10. All node timeouts applied via asyncio.wait_for in runner.
    Total generation timeout (V3_TIMEOUT_GENERATION_TOTAL_SECONDS) applied
    as an outer asyncio.wait_for wrapping all of run_generation().
11. Semaphores created once per generation via make_semaphores().
    GENERATION_MAX_CONCURRENT_PER_USER admission control still applies.
12. V2 PIPELINE_* env vars kept in .env.example under a legacy section —
    not deleted. New V3_* vars added in a separate v3 section.
13. Generation report records model + slot + tokens + duration per text node.
    Lesson Architect records thinking_tokens separately.
    Visual executor records provider + model + duration (no token counts).
```

---

## Definition of Done

Proposal 5 is complete when:

```
1.  ModelSlot.PREMIUM exists (in core.llm or v3-local enum) and
    existing tests still pass
2.  get_v3_model("lesson_architect") returns an Opus model
3.  get_v3_model("section_writer") returns a Sonnet model
4.  get_v3_model("signal_extractor") returns a Haiku model
5.  V3_PREMIUM_MODEL_NAME env override works correctly
6.  Lesson Architect call uses extended thinking with
    V3_ARCHITECT_THINKING_BUDGET_TOKENS budget
7.  All node timeouts applied in runner via asyncio.wait_for
8.  Total generation timeout (V3_TIMEOUT_GENERATION_TOTAL_SECONDS)
    applied as outer asyncio.wait_for on run_generation()
9.  Semaphores limit section writer to V3_CONCURRENCY_SECTION_MAX
10. Answer key generator escalates to STANDARD when expected_answer
    is missing and full_working style is required
11. Visual executor calls get_image_client() — does not hardcode xAI
12. .env.example has all V3_* vars in a new section and retains all
    v2 PIPELINE_* vars under a clearly labelled legacy section
13. Generation report records model + slot + tokens + duration per
    text node, thinking_tokens for Lesson Architect, and
    provider + model + duration for visual executor
14. End-to-end: Amara persona brief → Lesson Architect runs on Opus →
    section writers run on Sonnet → report shows correct model per node
    with visual executor showing provider=xai
```
