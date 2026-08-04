# Pipeline Latency Analysis & Optimization Proposals

**Date:** 2026-03-25
**Scope:** Content generation, diagram generation, validation repair, and overall throughput
**Based on:** Geography run `f1b91c6c` (completed, 2 sections) and Chemistry run `4849a2a0` (timed out, 4 sections)

---

## Part 1: How Things Run Today

### 1.1 The execution flow (per generation)

```
                         ┌─────────────────────┐
                         │  curriculum_planner  │   ~6-9s, 1 LLM call (FAST slot)
                         └──────────┬──────────┘
                                    │
                    LangGraph Send: fan out N sections
                   ┌────────────────┼────────────────┐
                   ▼                ▼                 ▼
            ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
            │ section s-01 │  │ section s-02 │  │ section s-0N │
            │  (parallel)  │  │  (parallel)  │  │  (parallel)  │
            └─────────────┘  └─────────────┘  └─────────────┘
```

Each section runs this internal mini-pipeline:

```
content_generator       ← 60-170s, 1 LLM call (STANDARD), the bottleneck
        │
        ├─ on validation failure → content_generator_repair (STANDARD, 67-174s)
        │
composition_planner     ← <1ms, no LLM, deterministic
        │
   ┌────┴────┐
   │         │
diagram   interaction    ← parallel via asyncio.gather
generator  path             diagram: FAST slot, 20s timeout in DRAFT
   │         │              interaction: no LLM, <1ms
   └────┬────┘
        │
section_assembler       ← <1ms, no LLM
        │
qc_agent                ← 7-10s, 1 LLM call (FAST)
        │
route_after_qc          ← may trigger retry_diagram / retry_field / full rerun
```

### 1.2 Model assignments (DRAFT mode — current default)

| Node | Slot | Model | Input/output cost per 1M tokens |
|------|------|-------|---------------------------------|
| curriculum_planner | FAST | claude-haiku-4-5 | $0.25 / $1.25 |
| content_generator | STANDARD | claude-haiku-4-5 | $0.25 / $1.25 |
| content_generator_repair | STANDARD | claude-haiku-4-5 | $0.25 / $1.25 |
| diagram_generator | FAST | claude-haiku-4-5 | $0.25 / $1.25 |
| qc_agent | FAST | claude-haiku-4-5 | $0.25 / $1.25 |

In DRAFT mode everything uses Haiku. The reports showed `claude-sonnet-4-6` because the runs used BALANCED mode (the report logs show Sonnet was the resolved model).

### 1.3 Concurrency controls

| Control | Value | Effect |
|---------|-------|--------|
| FAST slot semaphore (DRAFT) | 2 concurrent | At most 2 diagram/QC/curriculum calls at once |
| STANDARD slot semaphore (DRAFT) | 2 concurrent | At most 2 content_generator calls at once |
| No semaphore (BALANCED/STRICT) | unlimited | All sections compete freely for API throughput |
| Per-call timeout | 120s | Single `agent.run()` attempt |
| Diagram outer timeout | 20s (DRAFT) | Wraps the entire `run_llm` including retries |
| Generation job timeout | 300s | Hard ceiling for all sections + retries |

### 1.4 Prompt sizes (estimated tokens)

| Node | Input tokens | Output tokens | Notes |
|------|-------------|---------------|-------|
| curriculum_planner | 800-1,200 | 400-800 | Small, fast |
| content_generator | 3,000-5,000 | 2,000-5,000 | Large schema (SectionContent ~30 fields) |
| content_generator_repair | 3,500-5,500 | 2,000-5,000 | Same as above + validation error summary |
| diagram_generator | 600-1,000 | 500-2,000 | SVG output can be large |
| qc_agent | 3,000-7,000 | 200-500 | Receives entire assembled section JSON |

---

## Part 2: Why Latency Is High — Root Causes

### 2.1 Content generator is the overwhelming bottleneck

From the two runs:

| Run | Section | 1st attempt | Repair | Total content time |
|-----|---------|-------------|--------|--------------------|
| Geography s-01 | 64s | — | 64s |
| Geography s-02 | 103s (failed) | 67s | 170s |
| Chemistry s-01 | 62s | — | 62s |
| Chemistry s-02 | 114s (failed) | 174s | 288s |
| Chemistry s-03 | 171s (failed) | >119s (killed) | >290s |
| Chemistry s-04 | 234s (failed) | >54s (killed) | >288s |

**The content_generator consumes 85-95% of total wall time.** Everything else (curriculum planner, diagram, QC, assembly) combined is 15-30s per section.

### 2.2 Why content generation is slow

1. **Large structured output.** The `SectionContent` schema has ~30 optional fields with deeply nested sub-models. pydantic-ai embeds the full JSON schema into the system message, forcing the LLM to produce a carefully structured JSON blob. For Haiku, this is a heavy lift — output tokens for structured JSON are generated sequentially, and the model must maintain schema coherence throughout.

2. **High first-attempt failure rate.** 4 out of 6 content_generator attempts across both runs failed validation (67%). The LLM produces JSON that doesn't match the Pydantic schema. This triggers an expensive repair cycle that essentially doubles the latency.

3. **Repair is nearly as expensive as fresh generation.** The repair prompt sends: the full original user prompt + the validation error summary + the same system prompt. The model must regenerate the entire SectionContent from scratch but now "correctly." This is not a surgical fix — it's a full re-do with extra context.

4. **API throughput contention.** When 4 sections fan out simultaneously, all 4 content_generator calls hit the Anthropic API at the same time. They compete for rate limits and throughput. The later sections (s-03, s-04) consistently take longer (171s, 234s) compared to s-01 (62s), suggesting API-side queuing or throttling.

### 2.3 Why diagrams always timeout at 20s

The 20s timeout is **ours** — set in `diagram_generator.py` line 31. It is not an HTTP standard. The reasoning was: diagrams are optional enrichment, so in DRAFT mode we cap at 20s and ship without if it doesn't finish.

But the diagram LLM call needs to:
1. Acquire the FAST slot semaphore (may wait if 2 calls already in flight)
2. Make an HTTP connection to Anthropic
3. Send ~800 tokens of prompt
4. Generate ~500-2000 tokens of SVG output
5. Parse and validate the response

For Haiku generating SVG, 20s is tight. SVG is verbose (many tokens per visual element) and the model must produce syntactically valid XML. The `run_llm` inner retry logic (up to 3 attempts × 120s each) never gets a chance to trigger because the outer 20s timeout kills the entire coroutine.

### 2.4 The parallelization paradox

**Fan-out does help** — without it, 4 sections at ~100s each would take ~400s sequentially (already past the 300s ceiling). With fan-out, the first section finishes in ~90s.

**But it hurts in two ways:**
1. **API contention.** All sections start content_generator simultaneously. The Anthropic API has per-key rate limits (tokens per minute, requests per minute). With 4 parallel calls each requesting ~5,000 output tokens, we may hit throughput caps, causing later requests to queue or slow down.
2. **Semaphore bottleneck (DRAFT mode).** The STANDARD slot semaphore allows only 2 concurrent calls. With 4 sections, 2 must wait. But in BALANCED mode (what the reports used), there are NO semaphores, so all 4 hit the API simultaneously.

### 2.5 Transport overhead

The HTTP call chain is:
```
pipeline → pydantic-ai → anthropic SDK → httpx → HTTPS to api.anthropic.com
```

Each call involves:
- TLS handshake (first call only, then pooled)
- HTTP/2 or HTTP/1.1 request/response
- JSON serialization/deserialization
- Response streaming (if supported) or full-body wait

The `anthropic` SDK uses httpx with default connection pooling (100 max connections, 20 keep-alive, 5s keep-alive expiry). **The pipeline does not configure custom pooling.** Each `Agent.run()` call may or may not reuse an existing connection depending on timing.

For a 62s content_generator call, the transport overhead (TLS, HTTP headers, serialization) is <1s. **Transport is not the bottleneck — LLM inference time is.** The model is spending 60-230s thinking and generating tokens.

---

## Part 3: Answers to Your Questions

### Q: Did we set the timeout or is it HTTP standards?

**We set every timeout ourselves:**
- 20s diagram timeout → `diagram_generator.py` line 31 (our choice, per generation mode)
- 120s per-call timeout → `llm_runner.py` line 40 (our choice)
- 300s generation job timeout → `generation.py` line 426 (our choice)

HTTP standard timeouts (TCP keepalive, TLS handshake) are in the 10-60s range and never trigger here because the API does respond — it just takes long to generate output.

### Q: Does fan-out have advantages over serialization?

**Yes, significant advantages:**

| Approach | 4 sections, no failures | 4 sections, 3 failures + repair |
|----------|------------------------|-------------------------------|
| Serial | ~4 × 80s = 320s | ~80s + 3 × 250s = 830s |
| Parallel (current) | ~80-100s (limited by slowest) | ~290s (limited by slowest repair) |

Parallel is 3-4x faster in the happy path and still 2-3x faster with failures. **The API does support multiple parallel calls.** The issue is not parallelism itself — it's that content generation per section is too slow and fails too often.

### Q: Can we parallelize other components within sections?

Currently diagram + interaction run in parallel. The remaining candidates:

| Component pair | Can parallelize? | Why / why not |
|----------------|-----------------|---------------|
| content_generator + diagram_generator | **No** | Diagram needs content output (explanation text, hook) as input |
| content_generator + qc_agent | **No** | QC needs the assembled section |
| qc_agent + section_assembler | **No** | QC needs assembler output |
| composition_planner + content_generator | **No** | Composition planner runs after content |

**The per-section pipeline is fundamentally sequential** — each node depends on the previous node's output. The only parallelism possible is diagram ∥ interaction (already done) and across sections (already done).

### Q: Are there faster transport alternatives to HTTPS?

| Transport | Latency improvement | Feasibility |
|-----------|-------------------|-------------|
| **HTTP/2 multiplexing** | Minor (~50-200ms saved on connection setup). httpx may already use HTTP/2 with Anthropic. | Already happening if the SDK negotiates it |
| **WebSockets** | Eliminates per-request overhead, enables bidirectional streaming. | Anthropic API doesn't offer WebSocket endpoints |
| **gRPC** | Lower serialization overhead, persistent connections. | Anthropic API doesn't offer gRPC |
| **Streaming responses** | See tokens as they arrive instead of waiting for full response. | **Available today** — Anthropic supports streaming. pydantic-ai supports it via `agent.run_stream()`. We don't use it. |
| **Server-Sent Events** | One-way streaming. | This is how Anthropic's streaming API works under the hood |
| **Batch API** | Anthropic offers a Batches API at 50% cost, but responses arrive asynchronously (up to 24h). | Not suitable for interactive generation |

**Bottom line:** Transport is not the bottleneck. The LLM takes 60-230s to think and generate tokens. Even with zero transport latency, content generation would still take 59-229s. The real gains come from reducing what the LLM has to do.

---

## Part 4: Implementable Solutions — Prioritized

### Tier 1: High impact, implementable now

#### 1A. Split the SectionContent schema into smaller chunks

**Problem:** The LLM must produce one massive JSON blob (~30 fields) in a single call. This is the #1 cause of both slowness and validation failures.

**Solution:** Break content generation into 2-3 sequential sub-calls per section:

```
Call 1 (core):    header + hook + explanation + process     (~40s)
Call 2 (practice): practice + pitfall + glossary + what_next (~25s)
Call 3 (optional): worked_example + definition + simulation  (~15s, only if template requires)
```

**Benefits:**
- Each call has a smaller schema → fewer validation failures
- Each call generates fewer output tokens → faster
- If call 2 fails, call 1's output is preserved
- Individual calls can be retried cheaply without re-doing everything

**Trade-off:** 2-3 sequential calls per section instead of 1, so ~80s total vs ~62s for a successful single call. But the expected value is better because repair cycles drop dramatically.

**Expected improvement:** Validation failure rate drops from ~67% to ~10-20%. Total section time including repairs drops from avg ~180s to ~100s.

#### 1B. Use streaming to detect failures early

**Problem:** We wait 60-230s for a full response, then discover it fails validation.

**Solution:** Use `agent.run_stream()` instead of `agent.run()`. Monitor the incoming token stream for structural issues:
- If the JSON structure is clearly wrong after 30% of expected tokens → cancel and retry immediately
- Parse partial JSON as it arrives to detect schema violations early
- Cancel on malformed output rather than waiting for completion

**Benefits:**
- Cut wasted time on doomed attempts from ~100s to ~20-30s
- First byte arrives in ~1-2s, giving a "is this going anywhere" signal
- Can also stream section content to the frontend progressively

**Implementation:** pydantic-ai supports `agent.run_stream()`. The change is primarily in `run_llm()` and `content_generator.py`.

#### 1C. Increase diagram timeout to 30s in DRAFT mode

**Problem:** The 20s timeout is too tight for SVG generation. Every single diagram in both runs timed out.

**Solution:** Raise `_DIAGRAM_TIMEOUTS[GenerationMode.DRAFT]` from 20.0 to 30.0. This is a one-line change.

**Why 30s:** The diagram prompt is small (~800 input tokens). The bottleneck is SVG output generation (~1000-2000 tokens). Haiku generates at roughly 100 tokens/second for structured output. 2000 tokens / 100 t/s = 20s of pure generation, plus connection overhead. 30s gives a 50% margin.

**Alternative:** If 30s still isn't enough, consider generating simplified diagram descriptions (text-based) instead of raw SVG, and render them client-side with a library like Mermaid.js or D3.

#### 1D. Raise the generation job timeout based on section count

**Problem:** 300s is not enough for 4 sections with repair cycles.

**Solution:** Dynamic timeout: `base_timeout + (per_section_timeout × section_count)`

```python
# Example: 60s base + 90s per section
# 2 sections → 240s
# 4 sections → 420s
# 6 sections → 600s (cap at 10 min)
timeout = min(60 + 90 * section_count, 600)
```

**Why:** The current flat 300s punishes larger generations. The timeout should scale with workload.

### Tier 2: Medium impact, moderate effort

#### 2A. Smarter validation repair — surgical fix instead of full re-do

**Problem:** The repair prompt resends the entire context and asks the model to regenerate everything. This is wasteful.

**Solution:** Parse the Pydantic `ValidationError` to identify exactly which fields failed. Send a targeted repair prompt:

```
The following fields had validation errors:
- practice.problems[2].hints: expected list[str], got str

Here is the original output (valid parts preserved):
{original_output_json}

Fix ONLY the broken fields. Return the complete JSON with corrections.
```

**Benefits:**
- The model doesn't re-generate already-valid content
- Faster because it focuses on the broken fields
- Higher success rate because the scope is narrow

**Estimated improvement:** Repair time drops from ~67-174s to ~15-30s.

#### 2B. Pre-validate with a grammar/schema check before sending to LLM

**Problem:** The LLM doesn't "see" the Pydantic schema the same way we do. It has to infer JSON structure from pydantic-ai's schema injection.

**Solution:** Add explicit structural examples to the system prompt:

```json
// Example of valid SectionContent structure (abbreviated):
{
  "header": {"title": "...", "subtitle": "..."},
  "hook": {"headline": "...", "body": "...", "anchor": "..."},
  "explanation": {"body": "...", "callouts": [...]},
  "practice": {"problems": [{"level": "warm", "stem": "...", "answer": "...", "hints": ["..."]}]}
}
```

A concrete example reduces schema misinterpretation. Could also use pydantic-ai's `output_type` with `json_schema_extra` to inject examples.

#### 2C. Implement progressive section delivery

**Problem:** The frontend waits for all sections to complete. If 1/4 finishes in 90s and the rest timeout at 300s, the user sees nothing for 5 minutes.

**Solution:** Stream each section to the frontend as soon as it passes QC. The SSE infrastructure already exists. When s-01 is ready at 90s, the user can start reading while s-02/s-03/s-04 are still generating.

**Benefits:**
- Perceived latency drops from 300s to 90s for first content
- Users can start reviewing and potentially cancel remaining sections if the first one isn't what they wanted
- Better UX even with no backend speed improvement

#### 2D. Adaptive concurrency based on API response times

**Problem:** The fixed semaphore (2 per slot) may be too conservative or too aggressive depending on current API load.

**Solution:** Track rolling average latency per slot. If latency increases when adding more concurrent calls, back off. If latency is stable, allow more.

```python
# Start with 2 concurrent, measure latency
# If avg latency < 80s with 2 concurrent → try 3
# If avg latency > 120s with 2 concurrent → drop to 1
```

### Tier 3: High impact, significant effort

#### 3A. Replace raw SVG generation with structured diagram specs

**Problem:** Asking an LLM to generate valid SVG is slow and error-prone. SVG is a verbose format with strict syntax.

**Solution:** Instead of generating SVG, have the LLM output a structured diagram specification:

```json
{
  "type": "process-flow",
  "steps": [
    {"label": "Tectonic stress", "description": "Plates begin to diverge"},
    {"label": "Crustal thinning", "description": "Lithosphere stretches"}
  ],
  "connections": [{"from": 0, "to": 1, "label": "causes"}]
}
```

Then render to SVG client-side using D3.js, Mermaid.js, or a custom renderer.

**Benefits:**
- Diagram LLM output drops from ~2000 tokens (SVG) to ~200 tokens (JSON spec)
- Generation time drops from >20s to ~3-5s
- Validation becomes trivial (simple JSON schema vs. valid SVG)
- Consistent visual style (the renderer controls aesthetics)
- No more diagram timeouts

**Trade-off:** Requires a frontend rendering component. Limits diagram variety to what the renderer supports.

#### 3B. Implement speculative execution for content generation

**Problem:** If the first content_generator attempt fails, we've wasted 60-170s.

**Solution:** Launch 2 parallel content_generator calls with slightly different prompts (e.g., different temperature, rephrased instruction). Take the first one that passes validation. Cancel the other.

```python
results = await asyncio.gather(
    run_content_with_variant_a(section_plan),
    run_content_with_variant_b(section_plan),
    return_exceptions=True,
)
# Use first non-exception result
```

**Benefits:**
- Validation failure rate effectively drops from 67% to ~67% × 67% = 45% (both fail)
- Wall time is the same as a single call (parallel execution)
- Cost doubles, but with Haiku at $0.25/1M input tokens, cost is negligible

**Trade-off:** 2x token cost. Needs careful prompt differentiation to avoid correlated failures.

#### 3C. Implement prompt caching for repeated context

**Problem:** The system prompt (template context, lesson flow, capacity rules, schema) is identical across all sections and all retries. It gets resent on every call.

**Solution:** Anthropic's API supports prompt caching. The system prompt can be cached and reused across calls within a session. This reduces input token processing time and cost.

**Benefits:**
- ~2000-3000 fewer input tokens processed per call after the first
- Faster time-to-first-token on subsequent calls
- 90% discount on cached input tokens

**Implementation:** Requires using the Anthropic SDK directly (or configuring pydantic-ai to pass cache control headers). The system prompt for content_generator is a prime candidate — it's large, stable, and reused across all sections.

---

## Part 5: What's Noise vs. Meaningful in Reports

### Always noise (filter these out mentally)

| Node | Why it's noise |
|------|---------------|
| `composition_planner` | <1ms, no LLM, just reads contract and writes a plan dict |
| `interaction_decider` | <1ms, no LLM, checks if contract needs interactions |
| `interaction_generator` | <1ms, no LLM, generates interaction spec from template |
| `section_assembler` | <6ms, no LLM, stitches section parts into final JSON |

### Always meaningful (watch these)

| Node | Why it matters |
|------|---------------|
| `content_generator` | 85-95% of wall time. Failures here cascade. |
| `content_generator_repair` | Indicates a first-attempt validation failure. If you see this, the section took 2x time. |
| `diagram_generator` | Tracks whether diagrams succeed/timeout/skip |
| `qc_agent` | Tracks quality pass/fail and may trigger rerenders |

### Meaningful but expected

| Signal | Meaning |
|--------|---------|
| `diagram_outcome: timeout` | Diagram didn't finish in 20s. Section shipped without it. Expected in DRAFT mode. |
| `validation_repair_attempts: 1` | Content failed schema validation once, repair attempted. Common (~67% of sections). |
| `warning_count: N` | QC advisory feedback. Does NOT block delivery. Informational only. |

### Red flags (investigate if you see these)

| Signal | Meaning |
|--------|---------|
| `llm_transport_retries > 0` | API returned 429/500/502/503/504. Rate limit or API instability. |
| `validation_repair_successes < validation_repair_attempts` | A repair failed — the section either retried from scratch or failed permanently. |
| `qc_rerenders > 0` | QC found blocking issues and triggered a section rerun. Expensive. |
| `stalled_sections > 0` | A section stopped making progress. Potential deadlock or resource starvation. |
| `blocking_issue_count > 0` | QC found issues severe enough to block delivery. |

---

## Part 6: Recommended Implementation Order

| Priority | Change | Effort | Impact | Risk |
|----------|--------|--------|--------|------|
| **P0** | 1C: Raise diagram timeout to 30s | 1 line | Diagrams may start succeeding | None |
| **P0** | 1D: Dynamic generation timeout by section count | ~20 lines | 4-section runs stop timing out | Low |
| **P1** | 2C: Progressive section delivery (stream ready sections to frontend) | ~50 lines | Perceived latency drops by 60-70% | Low |
| **P1** | 2A: Surgical validation repair | ~100 lines | Repair time drops from 67-174s to 15-30s | Medium |
| **P1** | 1B: Streaming responses + early failure detection | ~150 lines | Wasted time on failed attempts drops 60-80% | Medium |
| **P2** | 1A: Split SectionContent into sub-calls | ~300 lines | Validation failures drop dramatically | High (prompt redesign) |
| **P2** | 3A: Structured diagram specs + client-side render | ~400 lines | Eliminates diagram timeouts entirely | High (frontend work) |
| **P2** | 3C: Prompt caching | ~50 lines | 10-20% latency reduction on subsequent calls | Low |
| **P3** | 3B: Speculative execution | ~100 lines | Effective failure rate drops ~50% | Medium (cost) |
| **P3** | 2D: Adaptive concurrency | ~150 lines | Better throughput utilization | Medium |

---

## Appendix: Run Comparison Summary

| Metric | Geography (f1b91c6c) | Chemistry (4849a2a0) |
|--------|---------------------|---------------------|
| Template | figure-first | interactive-lab |
| Sections planned | 2 | 4 |
| Sections delivered | 2 | 1 |
| Wall time | 207s | 300s (timeout) |
| Content validation failures | 1/2 (50%) | 3/4 (75%) |
| Successful repairs | 1/1 | 1/3 |
| Diagram timeouts | 2/2 (100%) | 1/1 (100%) |
| QC pass | yes | yes (s-01 only) |
| Total LLM calls | 7 | 10 |
| Slowest node | content_generator (170.7s) | content_generator (288.4s) |
