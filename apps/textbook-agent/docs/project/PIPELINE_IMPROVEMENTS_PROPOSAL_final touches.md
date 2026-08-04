# Pipeline Improvements Proposal
**Status:** Ready for implementation
**Grounded in:** Actual pipeline codebase (pipeline.zip)

---

## Overview

Six targeted changes. Each is independent and testable in isolation.
Implement in the order listed — earlier changes are safer and
provide baseline measurements for later ones.

```
Change 1  Lean capacity rules          prompts/shared.py + prompts/content.py
Change 2  Stream section titles        nodes/curriculum_planner.py
Change 3  Draft uses FAST model        nodes/content_generator.py
Change 4  Per-section QC               nodes/qc_agent.py
Change 5  Component-level retry        routers/qc_router.py + graph.py
Change 6  Diagram node timeout         nodes/diagram_generator.py
```

---

## Tracking Checklist

```
- [ ] Change 1 — lean capacity rules
- [ ] Change 2 — stream section titles
- [ ] Change 3 — draft uses FAST model
- [ ] Change 4 — per-section QC
- [ ] Change 5 — component-level retry
- [ ] Change 6 — diagram timeout

Validation after each change:
- [ ] npm run check passes (frontend)
- [ ] LLM diagnostics events confirm token counts
- [ ] End-to-end generation test (calculus, 4 sections)
- [ ] Measure: time to first content, total time
```

---

## Change 1 — Lean Capacity Rules

**Files:** `pipeline/prompts/shared.py`, `pipeline/prompts/content.py`
**Risk:** Low — no behaviour change, only fewer tokens
**Time:** 30 minutes

### Problem

`capacity_reminder()` in `shared.py` is hardcoded with every
capacity rule for every field regardless of template. A
`focus-flow` section never produces a `timeline` or
`comparison_grid` but the model still reads those rules.
Irrelevant input tokens + diluted attention on rules that matter.

### Change in `pipeline/prompts/shared.py`

Remove `capacity_reminder()` entirely. Add `capacity_reminder_for_fields()`.

```python
# REMOVE:
def capacity_reminder() -> str:
    return """Capacity rules (hard limits -- do not exceed):
- hook.headline: 12 words max
- hook.body: 80 words max
- explanation.body: 350 words max
- explanation.emphasis: 3 items max
- practice.problems: 2 min, 5 max
- practice hints per problem: 3 max
- glossary.terms: 8 max
- worked_example.steps: 6 max
- what_next.body: 50 words max
- definition.formal: 80 words max
- definition.plain: 60 words max"""


# ADD:
_CAPACITY_RULES: dict[str, str] = {
    'hook':             'hook.headline 12 words · hook.body 80 words',
    'explanation':      'explanation.body 350 words · emphasis 3 items max',
    'practice':         'practice.problems 2 min / 5 max · hints 3 max per problem',
    'what_next':        'what_next.body 50 words max',
    'definition':       'definition.formal 80 words · definition.plain 60 words',
    'definition_family':'definition_family.definitions 4 max',
    'worked_example':   'worked_example.steps 6 max',
    'process':          'process.steps 8 max',
    'glossary':         'glossary.terms 8 max (warn at 6)',
    'insight_strip':    'insight_strip.cells 2–3',
    'comparison_grid':  'comparison_grid.columns 2–4 · rows 6 max',
    'timeline':         'timeline.events 8 max',
    'pitfall':          'pitfall.misconception 20 words · correction 80 words',
    'diagram':          'diagram.caption 60 words',
    'quiz':             'quiz.options 3–4',
    'reflection':       'reflection.prompt 40 words max',
    'prerequisites':    'prerequisites.items 4 max',
    'interview':        'interview.prompt 35 words max',
}


def capacity_reminder_for_fields(active_fields: list[str]) -> str:
    """
    Emit capacity rules only for fields this template actually uses.
    Pass the union of required_fields + optional_fields.
    """
    rules = [
        rule for field, rule in _CAPACITY_RULES.items()
        if field in active_fields
    ]
    if not rules:
        return ''
    lines = '\n'.join(f'- {r}' for r in rules)
    return f'Capacity rules (hard limits):\n{lines}'
```

### Change in `pipeline/prompts/content.py`

```python
# BEFORE:
from pipeline.prompts.shared import shared_context, capacity_reminder

# ... in build_content_system_prompt():
{capacity_reminder()}


# AFTER:
from pipeline.prompts.shared import shared_context, capacity_reminder_for_fields

# ... in build_content_system_prompt():
{capacity_reminder_for_fields(required + optional)}
```

The `required` and `optional` variables are already computed in
`build_content_system_prompt` — no new contract calls needed.

### Diagnostic

```bash
python -c "
from pipeline.prompts.content import build_content_system_prompt

for tid in ['guided-concept-path', 'focus-flow', 'timeline-narrative']:
    p = build_content_system_prompt(tid, tid, 'test')
    tokens = len(p) // 4
    cap_start = p.find('Capacity')
    cap_block = p[cap_start:cap_start+400] if cap_start >= 0 else 'none'
    print(f'{tid}: ~{tokens} tokens')
    print(cap_block)
    print()
"
```

Verify: `focus-flow` shows no timeline or comparison_grid rules.
Verify: token count is lower than before the change.

---

## Change 2 — Stream Section Titles Immediately

**File:** `pipeline/nodes/curriculum_planner.py`
**Risk:** Low — additive only, no existing behaviour changes
**Time:** 30 minutes

### Problem

The curriculum plan is ready after 5-8 seconds but nothing
reaches the teacher until content starts arriving at 15-25s.
The teacher waits in silence seeing no progress.

`SectionStartedEvent` is already defined in `pipeline/events.py`
and already handled in the frontend `/textbook/[id]` page.
It just is not being emitted from `curriculum_planner`.

### Change in `pipeline/nodes/curriculum_planner.py`

In the `try` block, after `result = await run_llm(...)` and
before returning, publish one `SectionStartedEvent` per plan:

```python
# ADD after result = await run_llm(...):
from pipeline.events import SectionStartedEvent, event_bus

for plan in result.output.sections:
    event_bus.publish(
        state.request.generation_id or '',
        SectionStartedEvent(
            generation_id=state.request.generation_id or '',
            section_id=plan.section_id,
            title=plan.title,
            position=plan.position,
        ),
    )

return {
    "curriculum_outline": result.output.sections,
    "style_context": style_context,
    "completed_nodes": ["curriculum_planner"],
}
```

### What the teacher sees

```
t=0s   teacher clicks generate
t=6s   outline appears:
         Section 1: Why does calculus exist?
         Section 2: Limits and approaching a value
         Section 3: The derivative — rate of change
         Section 4: Applying derivatives
t=15s  Section 1 content arrives and renders
t=18s  Section 2 content arrives
...
```

The wait is identical in duration. The perceived wait is halved
because the teacher is reading the outline while content generates.

### Diagnostic

Generate a lesson. Verify `section_started` events arrive in
the browser's network tab before any `section_ready` event.
Verify titles match the final generated section titles.

---

## Change 3 — Draft Mode Uses FAST Model for Content

**File:** `pipeline/nodes/content_generator.py`
**Risk:** Low — only affects draft mode generations
**Time:** 45 minutes

### Problem

Draft mode exists for fast exploratory generation before committing
to a full balanced pass. Currently it uses `STANDARD` (sonnet) for
content generation — same model as balanced. Draft should be
meaningfully faster, not just looser on QC.

### Change in `pipeline/nodes/content_generator.py`

The registry already has mode-aware routing via
`get_node_text_model("content_generator", generation_mode=...)`.
Verify the `NODE_REQUIREMENTS` for `content_generator` has a
draft-mode entry that maps to `TEXT_FAST`. If not, add it.

```python
# In providers/registry.py — confirm or add:
NODE_REQUIREMENTS: dict[str, dict[str, NodeModelRequirements]] = {
    "content_generator": {
        "draft":    NodeModelRequirements(
            capability=Capability.TEXT,
            quality_class="low",       # haiku
            latency_class="fast",
            cost_class="cheap",
        ),
        "balanced": NodeModelRequirements(
            capability=Capability.TEXT,
            quality_class="standard",  # sonnet
            latency_class="standard",
            cost_class="standard",
        ),
        "strict":   NodeModelRequirements(
            capability=Capability.TEXT,
            quality_class="high",      # sonnet or better
            latency_class="standard",
            cost_class="standard",
        ),
    },
    # ... other nodes
}
```

If the registry already routes this correctly, no change is
needed here. Verify by checking which model is used on a
draft generation via `LLMCallSucceededEvent.model_name`.

### Expected outcome

```
Draft (haiku):    4-section lesson ~20-30 seconds total
Balanced (sonnet): 4-section lesson ~45-60 seconds total
```

Draft is the fast iteration pass. Teacher generates in 20s,
reads the structure, clicks Enhance if they want full quality.

### Diagnostic

```bash
# Run a draft generation and check the LLM events
# LLMCallSucceededEvent.model_name should be haiku for content_generator
# LLMCallSucceededEvent.model_name should be haiku for qc_agent (already is)
```

---

## Change 4 — Per-Section QC

**File:** `pipeline/nodes/qc_agent.py`
**Risk:** Medium — changes QC evaluation timing
**Time:** 1.5 hours

### Problem

`qc_agent` currently iterates over all `assembled_sections` in
one node. This means it waits for every section to finish before
evaluating any of them. For 4 sections finishing at t=15s, t=18s,
t=21s, t=24s — QC cannot start until t=24s and then runs 4
sequential LLM calls (20-40s). Total: 44-64 seconds of post-
generation overhead.

The graph already uses `process_section` as a composite per-section
node. QC needs to move into that per-section context.

### How the graph currently works

```
curriculum_planner
  ↓ fan-out (Send per section)
process_section  ← runs content + diagram + assembler per section
  ↓ join
qc_agent         ← runs over ALL assembled_sections
  ↓
route_after_qc
```

### How it should work

```
curriculum_planner
  ↓ fan-out (Send per section)
process_section  ← content + diagram + assembler + qc per section
  ↓ join
route_after_qc   ← reads qc_reports already populated per section
```

### Change in `pipeline/nodes/qc_agent.py`

Scope QC to `current_section_id` only:

```python
async def qc_agent(
    state: TextbookPipelineState | dict,
    *,
    provider_overrides: dict | None = None,
) -> dict:
    state = TextbookPipelineState.parse(state)

    # CHANGE: only evaluate the current section, not all assembled sections
    sid = state.current_section_id
    if not sid:
        return {"completed_nodes": ["qc_agent"]}

    section = state.assembled_sections.get(sid)
    if section is None:
        return {"completed_nodes": ["qc_agent"]}

    # Skip if already hit retry limit for this section
    if state.rerender_count.get(sid, 0) >= state.max_rerenders:
        return {"completed_nodes": ["qc_agent"]}

    # ... rest of evaluation unchanged, but only for sid ...

    output: dict = {
        "qc_reports":      {**state.qc_reports, sid: report},
        "completed_nodes": ["qc_agent"],
    }
    if rerender_reqs:
        output["rerender_requests"] = rerender_reqs
    if errors:
        output["errors"] = errors
    return output
```

### Change in `pipeline/nodes/process_section.py`

Add `qc_agent` to the per-section step chain:

```python
# BEFORE:
from pipeline.nodes.content_generator import content_generator
from pipeline.nodes.diagram_generator import diagram_generator
from pipeline.nodes.interaction_decider import interaction_decider
from pipeline.nodes.interaction_generator import interaction_generator
from pipeline.nodes.section_assembler import section_assembler

for step in [
    content_generator,
    diagram_generator,
    interaction_decider,
    interaction_generator,
    section_assembler,
]:

# AFTER:
from pipeline.nodes.content_generator import content_generator
from pipeline.nodes.diagram_generator import diagram_generator
from pipeline.nodes.interaction_decider import interaction_decider
from pipeline.nodes.interaction_generator import interaction_generator
from pipeline.nodes.section_assembler import section_assembler
from pipeline.nodes.qc_agent import qc_agent                          # ← ADD

for step in [
    content_generator,
    diagram_generator,
    interaction_decider,
    interaction_generator,
    section_assembler,
    qc_agent,                                                          # ← ADD
]:
```

Also update `process_section` output to forward `qc_reports`:

```python
# ADD to the output dict in process_section:
if sid and sid in typed_final.qc_reports:
    output["qc_reports"] = {sid: typed_final.qc_reports[sid]}
```

### Change in `graph.py`

The top-level `qc_agent` node is no longer needed.
`route_after_qc` reads from `qc_reports` which is now populated
per section inside `process_section`.

```python
# BEFORE:
workflow.add_node("curriculum_planner", curriculum_planner)
workflow.add_node("process_section",    process_section)
workflow.add_node("qc_agent",           qc_agent)           # ← REMOVE

workflow.add_edge("process_section", "qc_agent")            # ← REMOVE
workflow.add_conditional_edges("qc_agent", route_after_qc)  # ← CHANGE


# AFTER:
workflow.add_node("curriculum_planner", curriculum_planner)
workflow.add_node("process_section",    process_section)
# qc_agent is now internal to process_section — not a graph node

# After all process_section runs complete, route based on qc_reports
workflow.add_conditional_edges("process_section", route_after_qc)
```

### Expected outcome

```
t=15s  section 1 assembles → QC runs immediately → section_ready fires
t=18s  section 2 assembles → QC runs immediately → section_ready fires
t=21s  section 3 assembles → QC runs immediately → section_ready fires
t=24s  section 4 assembles → QC runs immediately → section_ready fires
# No post-generation QC wait
```

Total time saved: 20-40 seconds on a 4-section lesson.

---

## Change 5 — Component-Level Retry

**Files:** `pipeline/routers/qc_router.py`, `pipeline/nodes/process_section.py`
**Risk:** Medium — changes retry routing logic
**Time:** 2 hours
**Depends on:** Change 4 complete first

### Problem

Any QC blocking failure currently rerenders the entire section via
`process_section` — all of content_generator, diagram_generator,
assembler, and QC rerun. A failed diagram discards a perfectly
good hook, explanation, and practice set.

The `RerenderRequest` already has `block_type`. The router just
does not use it to pick a narrower retry path.

### Severity tiers that trigger retry vs ship

```
BLOCKING — retry the specific component:
  required field null or missing
  SVG invalid or empty string
  field wrong type (list expected, got string)
  practice.problems count < 2
  worked_example.steps empty

WARNING — ship with note, no retry:
  word count 10–20% over limit
  item count 1 over limit
  optional field absent
  semantic quality feedback from QC agent

IGNORED — not logged:
  prose style choices
  content preference opinions
```

### Change in `pipeline/routers/qc_router.py`

```python
def route_after_qc(state: TextbookPipelineState | dict) -> list[Send] | str:
    state = TextbookPipelineState.parse(state)

    if any(not e.recoverable for e in state.errors):
        return END

    sends = []
    for section_id, report in state.qc_reports.items():
        blocking = [
            i for i in report.issues
            if i.get('severity') == 'blocking'
        ]
        if not blocking or not state.can_rerender(section_id):
            continue

        plan = next(
            (p for p in (state.curriculum_outline or [])
             if p.section_id == section_id),
            None,
        )
        if not plan:
            continue

        block_type = blocking[0].get('block', '')
        base = {**state.model_dump(),
                'current_section_id': section_id,
                'current_section_plan': plan.model_dump()}

        # CHANGED: route to narrowest possible retry scope
        if block_type in ('diagram', 'diagram_series', 'diagram_compare'):
            # Only diagram failed — skip content_generator
            sends.append(Send('retry_diagram', base))
        else:
            # Text content failed — full process_section retry
            sends.append(Send('process_section', base))

    return sends if sends else END
```

### Add `retry_diagram` node in `graph.py`

```python
from pipeline.nodes.diagram_generator import diagram_generator
from pipeline.nodes.section_assembler import section_assembler
from pipeline.nodes.qc_agent import qc_agent


async def retry_diagram(
    state: TextbookPipelineState | dict,
    *,
    provider_overrides: dict | None = None,
) -> dict:
    """
    Re-run diagram_generator → section_assembler → qc_agent only.
    Text content in generated_sections[sid] is preserved exactly.
    """
    typed = TextbookPipelineState.parse(state)
    raw = typed.model_dump()

    for step in [diagram_generator, section_assembler, qc_agent]:
        result = await step(raw, provider_overrides=provider_overrides)
        for key, value in result.items():
            if isinstance(value, dict) and isinstance(raw.get(key), dict):
                raw[key] = {**raw[key], **value}
            elif isinstance(value, list) and isinstance(raw.get(key), list):
                raw[key] = raw[key] + value
            else:
                raw[key] = value

    typed_final = TextbookPipelineState.parse(raw)
    sid = typed.current_section_id
    output: dict = {"completed_nodes": ["retry_diagram"]}

    if sid and sid in typed_final.generated_sections:
        output["generated_sections"] = {sid: typed_final.generated_sections[sid]}
    if sid and sid in typed_final.assembled_sections:
        output["assembled_sections"] = {sid: typed_final.assembled_sections[sid]}
    if sid and sid in typed_final.qc_reports:
        output["qc_reports"] = {sid: typed_final.qc_reports[sid]}

    new_errors = typed_final.errors[len(typed.errors):]
    if new_errors:
        output["errors"] = new_errors

    return output


# In build_graph():
workflow.add_node("retry_diagram", retry_diagram)
workflow.add_conditional_edges("retry_diagram", route_after_qc)
```

### Expected outcome

```
Diagram fails QC:
  Before: discard hook + explanation + practice + diagram
          regenerate everything → 25-40s
  After:  preserve hook + explanation + practice
          regenerate diagram only → 8-15s
```

---

## Change 6 — Diagram Node Timeout

**File:** `pipeline/nodes/diagram_generator.py`
**Risk:** Low — defensive only, no change to happy path
**Time:** 45 minutes

### Problem

A slow or hanging diagram call blocks the entire section from
delivering. No hard limit exists — the call can run indefinitely.

### Change in `pipeline/nodes/diagram_generator.py`

Wrap the `run_llm` call in `asyncio.wait_for`:

```python
import asyncio

# Existing run_llm call — wrap it:
# BEFORE:
result = await run_llm(
    generation_id=...,
    node="diagram_generator",
    ...
)

# AFTER:
try:
    result = await asyncio.wait_for(
        run_llm(
            generation_id=state.request.generation_id or '',
            node="diagram_generator",
            route=route,
            spec=spec,
            agent=agent,
            user_prompt=build_diagram_user_prompt(...),
            section_id=sid,
        ),
        timeout=25.0,
    )
except asyncio.TimeoutError:
    return {
        "completed_nodes": ["diagram_generator"],
        "errors": [PipelineError(
            node="diagram_generator",
            section_id=sid,
            message="Diagram generation timed out (25s) — section delivered without diagram",
            recoverable=True,
        )],
    }
```

### Expected outcome

Diagram calls that hang or exceed 25 seconds produce a
recoverable error and the section ships without a diagram.
The diagram can be regenerated on demand later. No section
is ever blocked indefinitely by a diagram call.

---

## Measurement Plan

Run a calculus lesson (4 sections, `guided-concept-path`,
`blue-classroom`) before and after each change.
Record from `LLMCallSucceededEvent` events:

```
Metric                  Before    Target after all changes
────────────────────────────────────────────────────────
Time to first content   45-60s    8-12s  (Change 2)
Total generation time   90-120s   40-60s (all changes)
Content prompt tokens   ~850      ~700   (Change 1)
Draft total time        90-120s   20-30s (Change 3)
Post-generation QC      20-40s    0s     (Change 4)
Diagram failure cost    25-40s    8-15s  (Change 5)
Max diagram wait        unbounded 25s    (Change 6)
```

---

## Implementation Order

```
1. Change 1  lean capacity rules      → no risk, measure token reduction
2. Change 2  stream section titles    → no risk, immediate UX improvement
3. Change 3  draft uses FAST model    → low risk, isolated to draft mode
4. Change 6  diagram timeout          → low risk, defensive only
5. Change 4  per-section QC           → medium risk, test thoroughly
6. Change 5  component-level retry    → medium risk, depends on Change 4
```

---

*Each change is independently deployable.*
*Each has a clear diagnostic to verify it worked.*
*None requires changes to the frontend or Lectio.*
