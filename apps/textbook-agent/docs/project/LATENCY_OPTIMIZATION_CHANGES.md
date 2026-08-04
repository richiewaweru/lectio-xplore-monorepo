# Pipeline Latency Optimization — Expanded Change Proposals

**Date:** 2026-03-25
**Companion to:** [LATENCY_ANALYSIS_AND_PROPOSALS.md](LATENCY_ANALYSIS_AND_PROPOSALS.md)

Each proposal below is grounded in specific files and line numbers. The "before" shows current code; the "after" shows the intended change.

---

## Change 1 (P0): Raise diagram timeout from 20s to 30s in DRAFT mode

### What it is

A single constant change. The diagram generator wraps its entire LLM call in `asyncio.wait_for(timeout=20.0)` for DRAFT mode. 20s is too tight — every single diagram across both test runs timed out. The LLM needs ~20s just for SVG token generation, leaving zero margin for network latency or semaphore wait.

### Where it lives

[diagram_generator.py:30-34](../backend/src/pipeline/nodes/diagram_generator.py#L30-L34):

```python
# BEFORE
_DIAGRAM_TIMEOUTS = {
    GenerationMode.DRAFT: 20.0,
    GenerationMode.BALANCED: 35.0,
    GenerationMode.STRICT: 45.0,
}

# AFTER
_DIAGRAM_TIMEOUTS = {
    GenerationMode.DRAFT: 30.0,     # was 20.0 — both test runs hit 100% timeout
    GenerationMode.BALANCED: 40.0,   # slight bump for margin
    GenerationMode.STRICT: 50.0,     # slight bump for margin
}
```

### Why 30s is the right number

The diagram prompt is small (~800 input tokens). The output is SVG (~1000-2000 tokens). Haiku generates structured output at roughly 80-100 tokens/second. So 2000 tokens / 80 t/s = 25s of pure generation. 30s gives a 20% margin for network round-trip and semaphore acquisition. If this still times out consistently, the better fix is Change 7 (structured diagram specs).

### Risk

None. Worst case: diagrams still timeout at 30s instead of 20s, adding 10s to sections that already ship without diagrams. Best case: diagrams start actually succeeding.

### Effort

1 line changed. No tests need updating (the timeout values aren't tested directly).

---

## Change 2 (P0): Scale generation job timeout by section count

### What it is

The hard ceiling for the entire generation job is a flat 300 seconds, set in the shell layer. A 2-section geography textbook completed in 207s — comfortable. A 4-section chemistry textbook hit the 300s wall with 3 sections still in-progress. The timeout should scale with the workload.

### Where it lives

[generation.py:426](../backend/src/generation/routes.py#L426):

```python
# BEFORE
_GENERATION_JOB_TIMEOUT_SECONDS = 300.0
```

The timeout is consumed at [generation.py:668-670](../backend/src/generation/routes.py#L668-L670):

```python
result = await asyncio.wait_for(
    run_pipeline_streaming(command, on_event=on_event),
    timeout=_GENERATION_JOB_TIMEOUT_SECONDS,
)
```

### The change

Replace the flat constant with a function that computes timeout from the `PipelineCommand`:

```python
# BEFORE
_GENERATION_JOB_TIMEOUT_SECONDS = 300.0

# AFTER
_GENERATION_BASE_TIMEOUT_SECONDS = 120.0
_GENERATION_PER_SECTION_TIMEOUT_SECONDS = 90.0
_GENERATION_MAX_TIMEOUT_SECONDS = 720.0   # hard cap at 12 minutes


def _generation_timeout(command: PipelineCommand) -> float:
    """Scale the generation job timeout with the workload.

    Base (120s) covers curriculum planning + overhead.
    Per-section (90s) covers content generation + repair + diagram + QC.
    Cap at 720s to prevent runaway generations.
    """
    return min(
        _GENERATION_BASE_TIMEOUT_SECONDS
        + _GENERATION_PER_SECTION_TIMEOUT_SECONDS * command.section_count,
        _GENERATION_MAX_TIMEOUT_SECONDS,
    )
```

And update the call site:

```python
# BEFORE (generation.py:668-670)
result = await asyncio.wait_for(
    run_pipeline_streaming(command, on_event=on_event),
    timeout=_GENERATION_JOB_TIMEOUT_SECONDS,
)

# AFTER
job_timeout = _generation_timeout(command)
result = await asyncio.wait_for(
    run_pipeline_streaming(command, on_event=on_event),
    timeout=job_timeout,
)
```

Also update the error message at [generation.py:700-702](../backend/src/generation/routes.py#L700-L702) to report the actual timeout used:

```python
# BEFORE
error_message=f"Generation timed out after {int(_GENERATION_JOB_TIMEOUT_SECONDS)} seconds."

# AFTER
error_message=f"Generation timed out after {int(job_timeout)} seconds."
```

This requires `job_timeout` to be accessible in the `except asyncio.TimeoutError` block, so it must be computed before the `try`.

### What this gives us

| Sections | Old timeout | New timeout |
|----------|-------------|-------------|
| 2 | 300s | 300s |
| 3 | 300s | 390s |
| 4 | 300s | 480s |
| 6 | 300s | 660s |
| 8+ | 300s | 720s (cap) |

The chemistry run (4 sections) would get 480s instead of 300s — enough for the s-02 repair that finished 2s before the old timeout, plus time for s-03 and s-04 repairs.

### Risk

Low. The cap at 720s prevents abuse. Long-running generations still get killed, just with a budget that matches their scope.

### Effort

~20 lines. A new function plus updating 2-3 references to the old constant.

---

## Change 3 (P1): Surgical validation repair instead of full re-do

### What it is today

When content_generator's first attempt fails schema validation, the repair path at [content_generator.py:223-243](../backend/src/pipeline/nodes/content_generator.py#L223-L243) calls `run_llm` with `build_content_repair_user_prompt()`. That repair prompt ([content.py:111-141](../backend/src/pipeline/prompts/content.py#L111-L141)) sends:

1. "Your previous response had schema validation issues" (preamble)
2. The validation summary (one line like "Schema validation failed: 3 errors. First: ...")
3. **The entire original user prompt** — section plan, subject, context, grade, learner fit, seed section if present

This forces the model to regenerate all ~3000-5000 output tokens from scratch. It's a full re-do, not a repair. That's why repair takes 67-174s — almost identical to a fresh attempt.

### What the change looks like

**Step 1:** Extract structured error details from the `ValidationError`, not just a one-line summary.

In [content_generator.py](../backend/src/pipeline/nodes/content_generator.py), the `_error_summary` function currently does:

```python
# BEFORE (content_generator.py:68-72)
def _error_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]["msg"] if exc.errors() else "unknown validation error"
        return f"Schema validation failed: {exc.error_count()} errors. First: {first}"
    return str(exc)
```

Change this to produce a structured field-level breakdown:

```python
# AFTER
def _error_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        first = exc.errors()[0]["msg"] if exc.errors() else "unknown validation error"
        return f"Schema validation failed: {exc.error_count()} errors. First: {first}"
    return str(exc)


def _validation_field_errors(exc: ValidationError) -> str:
    """Produce a field-by-field breakdown for targeted repair prompts."""
    lines = []
    for err in exc.errors():
        path = " -> ".join(str(p) for p in err["loc"])
        lines.append(f"- {path}: {err['type']} — {err['msg']}")
    return "\n".join(lines)
```

**Step 2:** Build a repair prompt that tells the model to fix specific fields.

In [content.py](../backend/src/pipeline/prompts/content.py), change `build_content_repair_user_prompt`:

```python
# BEFORE (content.py:111-141) — sends the ENTIRE original prompt
def build_content_repair_user_prompt(..., validation_summary: str, ...) -> str:
    return f"""Your previous response had schema validation issues.
Fix only the structure so it matches the SectionContent schema exactly.
Keep the teaching intent, examples, and progression aligned with the requested section.

Validation summary:
{validation_summary}

{build_content_user_prompt(...all original args...)}"""


# AFTER — sends only the broken fields + the original output for context
def build_content_repair_user_prompt(
    *,
    validation_summary: str,
    field_errors: str,
    original_output_json: str | None = None,
    section_plan: SectionPlan,
    template_id: str,
    **_kwargs,    # remaining args no longer needed
) -> str:
    context_block = ""
    if original_output_json:
        context_block = f"""
Here is your previous output (may contain valid parts — preserve them):
{original_output_json}
"""

    return f"""Your previous response had schema validation issues.

Errors by field:
{field_errors}

{context_block}
Fix ONLY the broken fields listed above. Return the complete SectionContent JSON
with section_id="{section_plan.section_id}" and template_id="{template_id}".
Preserve all valid content unchanged. Output only valid JSON."""
```

**Step 3:** In `content_generator`, capture the raw LLM output before validation fails and pass it to the repair prompt.

This requires a change to how we call `run_llm`. Currently, pydantic-ai raises `ValidationError` internally and we never see the raw text. Two options:

**Option A (simpler):** Don't pass the raw output. Just give the field-level error list. The model infers what to fix from the field error paths.

**Option B (better but more invasive):** Use pydantic-ai's `agent.run()` with `output_type=str` first to get raw text, then manually validate with `SectionContent.model_validate_json()`. If validation fails, we have both the raw output and the errors.

Option A requires changes only to the prompt layer. Option B requires changes to the content_generator node itself.

### Why this helps

Currently: repair prompt = ~4000 input tokens → model regenerates entire ~3500-token SectionContent → 67-174s.

After (Option A): repair prompt = ~500 input tokens → model outputs ~3500 tokens → ~40-60s.

After (Option B): repair prompt = ~4000 input tokens (includes original output) → model outputs ~3500 tokens but most is copy-paste from its memory → ~20-40s. The model can pattern-match the original output and only change the broken fields.

### Risk

Medium. The repair prompt must be precise enough that the model doesn't introduce new errors while fixing old ones. Need to test against the actual validation failures we're seeing.

### Effort

~100 lines across `content_generator.py` and `content.py`. Option A is ~50 lines. Option B adds ~50 more.

---

## Change 4 (P1): Stream LLM responses and detect failures early

### What it is today

Every LLM call goes through `run_llm()` → `_run_agent_with_limits()` → `agent.run()` at [llm_runner.py:179-188](../backend/src/pipeline/llm_runner.py#L179-L188):

```python
async with semaphore:
    return await asyncio.wait_for(
        agent.run(user_prompt=user_prompt),
        timeout=retry_policy.call_timeout_seconds,
    )
```

`agent.run()` waits for the **complete** response, validates it, and returns. If the model spends 100s generating a response that fails validation, we've burned 100s with nothing to show for it.

### What the change looks like

pydantic-ai provides `agent.run_stream()` which yields tokens as they arrive. The change is in `llm_runner.py`:

```python
# AFTER — new function alongside _run_agent_with_limits
async def _run_agent_streaming_with_limits(
    *,
    agent: Any,
    user_prompt: str,
    retry_policy: RetryPolicy,
    generation_mode: GenerationMode,
    slot: ModelSlot,
    early_cancel_check: Callable[[str], bool] | None = None,
) -> Any:
    """Run with streaming, optionally cancelling early on malformed output."""
    semaphore = _draft_semaphore(generation_mode=generation_mode, slot=slot)

    async def _stream():
        async with agent.run_stream(user_prompt=user_prompt) as stream:
            chunks = []
            async for chunk in stream.stream_text():
                chunks.append(chunk)
                partial = "".join(chunks)
                # Check for early signs of failure
                if early_cancel_check and len(partial) > 200:
                    if early_cancel_check(partial):
                        raise ValidationError(
                            "Early cancellation: output structure looks invalid"
                        )
            # Stream complete — get the validated result
            return await stream.get_output()

    if semaphore is None:
        return await asyncio.wait_for(
            _stream(),
            timeout=retry_policy.call_timeout_seconds,
        )
    async with semaphore:
        return await asyncio.wait_for(
            _stream(),
            timeout=retry_policy.call_timeout_seconds,
        )
```

The `early_cancel_check` callback is where the intelligence lives. For content_generator:

```python
def _content_early_cancel(partial_text: str) -> bool:
    """Cancel if the first ~200 chars of output are clearly not JSON."""
    stripped = partial_text.strip()
    # If LLM starts with markdown fences, prose, or non-JSON — bail
    if stripped and not stripped.startswith("{"):
        return True
    return False
```

### What this gives us

1. **Fast failure detection.** If the model starts outputting `"Here is the section content:\n```json"` instead of raw JSON, we detect it within ~2s and cancel, rather than waiting 100s.

2. **Progressive streaming to the frontend.** When a section's content arrives token-by-token, we could (in a future change) parse partial JSON and stream partial content to the UI. The user sees text appearing in real-time instead of staring at a spinner for 60-90s.

3. **Better timeout behavior for diagrams.** The diagram node wraps `run_llm` in a 30s `wait_for`. With streaming, we can see if the SVG generation is making progress (tokens arriving) vs stalled (no tokens for 5s). Progress means "give it more time"; stalled means "cut it off."

### What it does NOT give us

Streaming doesn't make the LLM faster. If the model needs 60s to generate 3000 tokens, streaming still takes 60s. The gains come from:
- Cancelling doomed attempts early (saves ~60-100s per failed attempt)
- Better UX (progressive content display)
- Smarter timeout decisions (activity-based, not clock-based)

### Risk

Medium. pydantic-ai's `run_stream()` API may behave differently from `run()` in edge cases (partial validation, error handling). Needs thorough testing. Also, the `early_cancel_check` must be conservative — false positives would cancel valid outputs.

### Effort

~150 lines in `llm_runner.py`. The content_generator and diagram_generator would opt in by passing a callback. Other nodes continue using `agent.run()` unchanged.

---

## Change 5 (P1): Progressive section delivery to frontend

### What it is today

The SSE stream at [generation.py:1038-1088](../backend/src/generation/routes.py#L1038-L1088) already streams events per section. And the `on_event` callback at [generation.py:556-569](../backend/src/generation/routes.py#L556-L569) already saves the document when a section is ready:

```python
async def on_event(event) -> None:
    nonlocal document
    if isinstance(event, SectionReadyEvent):
        document = _replace_or_append_section(document, event.section)
        await document_repo.save_document(document)
    event_bus.publish(generation.id, event)
```

So the backend **already publishes `SectionReadyEvent` per section and persists incrementally**. The question is: does the frontend act on it?

### The change

This is primarily a **frontend change**. The backend already does the right thing. What needs to happen:

1. **Frontend subscribes to SSE** and renders each `section_ready` event immediately — not waiting for `complete`.
2. **Frontend shows a "generating..." placeholder** for sections that haven't arrived yet.
3. **Frontend appends sections in position order** as they arrive. If s-01 arrives at 90s and s-02 at 200s, the user reads s-01 for 110 seconds while s-02 generates.

If the frontend currently waits for `complete` before rendering, the change is:

```typescript
// BEFORE (pseudocode)
eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type === "complete") {
        fetchDocument(event.document_url);  // renders everything at once
    }
};

// AFTER
eventSource.onmessage = (e) => {
    const event = JSON.parse(e.data);
    if (event.type === "section_ready") {
        appendSection(event.section);  // render immediately
    }
    if (event.type === "complete") {
        finalizeDocument();  // clean up placeholders
    }
};
```

### What this gives us

For the chemistry run (4 sections, 300s timeout):
- s-01 was ready at 92s. User could have been reading for 208 seconds.
- Even with only 1 of 4 sections delivered, the user has content immediately.

**Perceived latency drops from 300s to ~90s** without any backend speed improvement.

### Risk

Low. The backend already supports this. The change is in how the frontend consumes events.

### Effort

~50 lines of frontend TypeScript. The backend is ready as-is.

---

## Change 6 (P2): Split content generation into sub-calls

### What it is today

The content_generator asks the LLM to produce one monolithic `SectionContent` JSON blob in a single call. The `SectionContent` schema ([section_content.py:334-365](../backend/src/pipeline/types/section_content.py#L334-L365)) has:

- 5 **required** top-level fields: `header`, `hook`, `explanation`, `practice`, `what_next`
- 17 **optional** top-level fields: `prerequisites`, `definition`, `worked_example`, `process`, `diagram`, `pitfall`, `quiz`, `reflection`, `glossary`, `simulation`, etc.
- Each field has deeply nested sub-models (e.g., `PracticeContent` has `list[PracticeProblem]`, each with `list[PracticeHint]`, optional `PracticeSolution`, etc.)

pydantic-ai serializes this entire schema as JSON Schema into the system message. The LLM must produce a single JSON object conforming to all of it. This is the #1 reason for the 67% validation failure rate.

### What the change looks like

Split the SectionContent into 2-3 smaller Pydantic models and generate them sequentially:

```python
# New intermediate types (new file: pipeline/types/content_phases.py)

class CoreContent(BaseModel):
    """Phase 1: The teaching backbone — must succeed for the section to exist."""
    section_id: str
    template_id: str
    header: SectionHeaderContent
    hook: HookHeroContent
    explanation: ExplanationContent

class PracticeContent_Phase(BaseModel):
    """Phase 2: Assessment and transitions."""
    practice: PracticeContent
    what_next: WhatNextContent
    pitfall: Optional[PitfallContent] = None
    glossary: Optional[GlossaryContent] = None

class EnrichmentContent(BaseModel):
    """Phase 3: Optional enrichments — only generated if template requires them."""
    worked_example: Optional[WorkedExampleContent] = None
    process: Optional[ProcessContent] = None
    definition: Optional[DefinitionContent] = None
    comparison_grid: Optional[ComparisonGridContent] = None
    timeline: Optional[TimelineContent] = None
    simulation: Optional[SimulationContent] = None
```

The content_generator node becomes:

```python
# Pseudocode — content_generator.py
async def content_generator(state, ...) -> dict:
    # Phase 1: Core (header + hook + explanation)
    core_agent = Agent(model=model, output_type=CoreContent, system_prompt=system_prompt)
    core = await run_llm(..., agent=core_agent, user_prompt=core_prompt)

    # Phase 2: Practice (practice + what_next + pitfall + glossary)
    # Receives phase 1 output as context so it can reference the explanation
    practice_agent = Agent(model=model, output_type=PracticeContent_Phase, system_prompt=system_prompt)
    practice_prompt = build_practice_prompt(core.output, section_plan)
    practice = await run_llm(..., agent=practice_agent, user_prompt=practice_prompt)

    # Phase 3: Enrichment (only if template requires worked_example/process/etc.)
    enrichment = None
    if needs_enrichment(state.contract):
        enrich_agent = Agent(model=model, output_type=EnrichmentContent, system_prompt=system_prompt)
        enrichment = await run_llm(..., agent=enrich_agent, user_prompt=enrichment_prompt)

    # Assemble into SectionContent
    section = SectionContent(
        section_id=sid,
        template_id=template_id,
        header=core.output.header,
        hook=core.output.hook,
        explanation=core.output.explanation,
        practice=practice.output.practice,
        what_next=practice.output.what_next,
        pitfall=practice.output.pitfall,
        glossary=practice.output.glossary,
        worked_example=enrichment.output.worked_example if enrichment else None,
        # ... etc
    )
    generated[sid] = section
```

### Why this helps

**Smaller schemas = fewer validation failures.** `CoreContent` has 5 fields instead of 22. The LLM can handle that more reliably.

**Partial success is preserved.** If phase 2 fails, phase 1's output (header + hook + explanation) is already captured. Repair only needs to redo phase 2 (~25s) instead of the entire section (~100s+).

**Each phase is faster.** Phase 1 outputs maybe ~1500 tokens instead of ~3500. That's ~15-20s per phase instead of ~60s for the monolith. Total sequential time is ~50-60s but with much higher success rate.

### The math

| Metric | Current (monolith) | After (3 phases) |
|--------|-------------------|-------------------|
| Output tokens per call | ~3500 | ~1000-1500 |
| Schema complexity | 22 fields, 30+ nested types | 3-8 fields, 10 nested types |
| Expected failure rate per call | ~67% | ~10-20% |
| Expected section time (no failure) | ~60-80s | ~50-70s (3 sequential calls) |
| Expected section time (with failures) | ~180-290s | ~70-100s (1 phase retried) |

### Trade-offs

- 3 sequential LLM calls instead of 1 → slight overhead in connection setup and prompt re-sending
- Phase 2 and 3 need phase 1's output as context → input tokens increase slightly
- Prompt engineering effort: need to write 3 focused prompts instead of 1 general one
- The `SectionContent` assembly step must handle partial results gracefully

### Risk

High effort, medium risk. The prompt redesign is the hardest part — getting phase boundaries right so each phase has enough context without the full section. But the payoff is large: dramatically fewer failures and faster recovery.

### Effort

~300 lines: new types file (~50 lines), new prompt builders (~100 lines), refactored content_generator (~100 lines), tests (~50 lines).

---

## Change 7 (P2): Replace SVG generation with structured diagram specs

### What it is today

The diagram_generator asks the LLM to produce raw SVG inside a JSON wrapper ([diagram_generator.py:125-129](../backend/src/pipeline/nodes/diagram_generator.py#L125-L129)):

```python
agent = Agent(
    model=model,
    output_type=DiagramOutput,  # { svg_content: str, caption: str, alt_text: str }
    system_prompt=build_diagram_system_prompt(state.style_context),
)
```

The LLM must produce syntactically valid SVG with correct viewBox, xmlns, inline styles, proper font sizes, and meaningful content — all in ~1000-2000 tokens. This is hard for any LLM, especially Haiku.

### What the change looks like

**New output type:**

```python
# AFTER — pipeline/types/diagram_spec.py

class DiagramElement(BaseModel):
    id: str
    label: str
    description: Optional[str] = None
    group: Optional[str] = None

class DiagramConnection(BaseModel):
    from_id: str
    to_id: str
    label: Optional[str] = None
    style: Literal["arrow", "dashed", "bidirectional"] = "arrow"

class StructuredDiagramSpec(BaseModel):
    type: Literal["process-flow", "cycle", "hierarchy", "comparison", "labeled-diagram"]
    title: str
    elements: list[DiagramElement]
    connections: list[DiagramConnection]
    caption: str
    alt_text: str
```

**New diagram prompt:**

```python
# AFTER — prompts/diagram.py (modified system prompt)
"""You generate structured diagram specifications for educational content.
Do NOT generate SVG or HTML. Output a JSON diagram specification.

Output a JSON object with these fields:
  type, title, elements, connections, caption, alt_text

Diagram types:
  process-flow: sequential steps (e.g. lifecycle, algorithm)
  cycle: repeating process (e.g. water cycle)
  hierarchy: tree structure (e.g. taxonomy, org chart)
  comparison: side-by-side (e.g. plant vs animal cell)
  labeled-diagram: annotated image description (e.g. anatomy)

Keep elements to 3-6 items. Keep connections clear.
Caption: max 60 words. alt_text: max 80 words."""
```

**Frontend renderer:**

A new Svelte component that takes a `StructuredDiagramSpec` and renders it using SVG or a library like D3.js:

```svelte
<!-- DiagramRenderer.svelte -->
<script>
  export let spec: StructuredDiagramSpec;
  // Render based on spec.type
  // process-flow → horizontal boxes with arrows
  // cycle → circular arrangement
  // hierarchy → tree layout
  // comparison → two-column layout
</script>
```

### Why this helps

| Metric | Current (SVG) | After (spec) |
|--------|--------------|--------------|
| LLM output tokens | ~1000-2000 (verbose SVG) | ~100-300 (small JSON) |
| Generation time | ~20-30s (always times out) | ~3-5s |
| Validation failure rate | high (SVG syntax is strict) | low (simple JSON) |
| Visual consistency | varies (LLM controls styling) | guaranteed (renderer controls styling) |
| Timeout needed | 30s+ | 10s |

### Trade-offs

- **Limited diagram variety.** A renderer can only draw the diagram types it supports. You can't get a "creative" diagram that the LLM imagined in SVG.
- **Frontend work required.** Need to build 4-5 diagram renderers (one per type).
- **Migration.** Existing sections with raw SVG diagrams still need the old rendering path.

### Risk

High effort, but very high payoff. Eliminates the diagram timeout problem entirely.

### Effort

~400 lines total: new types (~30 lines), modified prompts (~30 lines), modified diagram_generator node (~30 lines), frontend renderers (~300 lines across components).

---

## Change 8 (P2): Prompt caching for repeated system prompts

### What it is

The Anthropic API supports [prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching). When you mark a message block as cacheable, subsequent calls with the same prefix reuse the cached KV state — reducing input processing time by ~85% and cost by 90% on cache hits.

### Why it matters here

The content_generator's system prompt ([content.py:33-56](../backend/src/pipeline/prompts/content.py#L33-L56)) is **identical across all sections** in a generation. For a 4-section run:
- Call 1: cache miss, processes ~2000 system tokens
- Calls 2-4: cache hits, skip ~2000 tokens of processing each

The SectionContent schema (which pydantic-ai embeds in the messages) is ~2000-3000 tokens and also identical across calls.

### What the change looks like

The Anthropic SDK supports cache control via message annotations. pydantic-ai may or may not expose this. If it does:

```python
# In content_generator.py — annotate the system prompt for caching
agent = Agent(
    model=model,
    output_type=SectionContent,
    system_prompt=build_content_system_prompt(...),
    # If pydantic-ai supports this:
    system_prompt_cache_control="ephemeral",
)
```

If pydantic-ai doesn't expose cache control, we'd need to use the Anthropic SDK directly for the content_generator call, bypassing pydantic-ai for this specific node. That's more invasive but doable.

### Expected improvement

- Time-to-first-token drops ~1-2s per call after the first (cached prefix skips KV computation)
- For 4 sections × ~4000 cached tokens: saves processing ~12,000 input tokens
- At Haiku prices: negligible cost savings ($0.003). At Sonnet prices: meaningful ($0.036 per run)
- The time savings compound: ~5-10s saved across a 4-section generation

### Risk

Low. Cache misses silently fall back to normal processing. No behavior change.

### Effort

~50 lines if pydantic-ai supports cache control. ~150 lines if we need to bypass pydantic-ai for content_generator.

---

## Change 9 (P3): Speculative parallel content generation

### What it is

Instead of generating content once and repairing on failure, launch 2 parallel content_generator calls with slightly different configurations. Take the first valid result. Cancel the loser.

### Where it lives

This is a change to the content_generator node at [content_generator.py:187-196](../backend/src/pipeline/nodes/content_generator.py#L187-L196):

```python
# BEFORE
result = await run_llm(
    generation_id=..., node="content_generator",
    agent=agent, model=model, user_prompt=base_prompt,
    section_id=sid, generation_mode=state.request.mode,
)

# AFTER
async def _speculative_content(agent, model, prompt, state, sid):
    """Race two content generation attempts, return first valid result."""
    task_a = asyncio.create_task(
        run_llm(
            generation_id=state.request.generation_id or "",
            node="content_generator",
            agent=agent, model=model, user_prompt=prompt,
            section_id=sid, generation_mode=state.request.mode,
        )
    )
    # Variant B: slightly different prompt or temperature
    task_b = asyncio.create_task(
        run_llm(
            generation_id=state.request.generation_id or "",
            node="content_generator",
            agent=agent_variant_b, model=model, user_prompt=prompt_variant_b,
            section_id=sid, generation_mode=state.request.mode,
        )
    )

    done, pending = await asyncio.wait(
        {task_a, task_b},
        return_when=asyncio.FIRST_COMPLETED,
    )

    # Cancel the loser
    for task in pending:
        task.cancel()

    # Return the winner
    for task in done:
        if not task.exception():
            return task.result()

    # Both failed — raise the first exception
    raise done.pop().exception()
```

### How to make variant B different

The two attempts need to be **not** identically likely to fail. Options:

1. **Different temperature:** Variant A at temp=0.7 (default), variant B at temp=0.4 (more conservative, more likely to stick to schema)
2. **Simplified prompt:** Variant B omits some optional fields, making the schema smaller
3. **Different ordering:** Variant B lists required fields in a different order in the system prompt

### What this gives us

With a 67% per-attempt failure rate:
- P(both fail) = 0.67 × 0.67 = 45% (if failures are correlated — likely some correlation)
- Realistic P(both fail) = ~30-50%
- **Effective failure rate drops from 67% to 30-50%**

Wall time is unchanged (parallel execution), but the probability of needing a repair drops by half.

### Trade-offs

- **2x API cost** for content generation (the biggest single cost component)
- **2x API throughput pressure** — now we're sending 8 content_generator calls for 4 sections instead of 4
- The semaphore (2 concurrent STANDARD calls in DRAFT) would need to increase to 4
- If failures are highly correlated (same schema confusion), the benefit is smaller

### Risk

Medium. Cost increase is real. But at Haiku prices ($0.25/1M input, $1.25/1M output), doubling content generation cost adds maybe $0.01-0.02 per generation.

### Effort

~100 lines in content_generator.py.

---

## Summary: Implementation Order

```
Week 1 (quick wins):
  ✓ Change 1: Diagram timeout 20s → 30s (1 line)
  ✓ Change 2: Dynamic generation timeout (20 lines)

Week 2 (repair quality):
  ✓ Change 3: Surgical validation repair (100 lines)

Week 3 (streaming + UX):
  ✓ Change 4: Streaming LLM responses (150 lines)
  ✓ Change 5: Progressive section delivery in frontend (50 lines)

Week 4+ (architecture):
  ✓ Change 6: Split content into sub-calls (300 lines)
  ✓ Change 7: Structured diagram specs (400 lines)
  ✓ Change 8: Prompt caching (50-150 lines)
  ✓ Change 9: Speculative execution (100 lines)
```

**Expected combined effect of Changes 1-5:** Section failure rate drops from ~67% to ~40%. Repair time drops from ~170s to ~40s. Perceived latency drops from 300s to ~90s. Diagram success rate goes from 0% to ~50%.

**Expected combined effect of all 9 changes:** Section failure rate drops to ~10-20%. Repair time drops to ~15-30s. All diagrams succeed. Perceived latency ~30-60s (streaming). Total generation time for 4 sections drops from >300s to ~120-180s.
