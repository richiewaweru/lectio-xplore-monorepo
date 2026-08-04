# Field-Level Retry — Mini Proposal
**Scope:** Approach 1 — dedicated `field_regenerator` node
**Assumption:** LLMs remain faithful to the template contract.
               No auto-fix trimming. Structural checks already in place.
               This covers semantic failures only.

---

## What This Adds

When QC flags a specific field as blocking, instead of discarding
the entire section and re-running `process_section`, a targeted
`field_regenerator` node regenerates only the failing field using
the rest of the section as context. Everything the model already
produced correctly is preserved.

---

## Files to Change

```
NEW   pipeline/nodes/field_regenerator.py
NEW   pipeline/prompts/field_regen.py
MOD   pipeline/routers/qc_router.py     ← add retry_field route
MOD   pipeline/graph.py                 ← register field_regenerator node
```

No changes to `qc_agent`, `section_assembler`, `process_section`,
`content_generator`, or the state schema.

---

## Tracking Checklist

```
- [ ] pipeline/prompts/field_regen.py created
- [ ] pipeline/nodes/field_regenerator.py created
- [ ] pipeline/routers/qc_router.py updated
- [ ] pipeline/graph.py updated
- [ ] Diagnostic: field retry fires correctly on a seeded failure
- [ ] Diagnostic: preserved fields are unchanged after retry
- [ ] Diagnostic: regenerated field is coherent with the rest of section
```

---

## New File: `pipeline/prompts/field_regen.py`

```python
"""
Prompt builders for the field_regenerator node.

System prompt: lean — template tone + guidance only.
User prompt:   the failing field name, the reason it failed,
               and the rest of the section as context.
"""

from __future__ import annotations

import json

from pipeline.contracts import get_generation_guidance, get_lesson_flow
from pipeline.types.section_content import SectionContent

# Fields the QC agent can flag for targeted retry.
# These map directly to SectionContent field names.
RETRYABLE_FIELDS = {
    'hook',
    'explanation',
    'practice',
    'worked_example',
    'definition',
    'pitfall',
    'glossary',
    'what_next',
}


def build_field_regen_system_prompt(template_id: str) -> str:
    guidance    = get_generation_guidance(template_id)
    lesson_flow = ' → '.join(get_lesson_flow(template_id))

    return f"""You regenerate a single failing field in an educational section.
The rest of the section is already correct and complete.

Template flow: {lesson_flow}
Tone: {guidance['tone']}
Pacing: {guidance['pacing']}
Avoid: {', '.join(guidance['avoid'])}

You receive:
  - the name of the field to regenerate
  - the reason it failed quality review
  - the rest of the section as context (do not reproduce it)

Output only the regenerated field as valid JSON.
Match the schema of the original field exactly.
Do not wrap it. No preamble, no markdown fences.
Example — if regenerating 'hook', output only:
  {{"headline": "...", "body": "...", "anchor": "..."}}"""


def build_field_regen_user_prompt(
    section:      SectionContent,
    failing_field: str,
    reason:       str,
) -> str:
    # Serialise everything except the failing field as context.
    # The model sees what it needs to stay coherent.
    preserved = section.model_dump(
        exclude_none=True,
        exclude={failing_field},
    )

    return f"""Regenerate the '{failing_field}' field.

Reason it failed:
  {reason}

Rest of the section (context only — do not reproduce):
{json.dumps(preserved, indent=2)}

Output only the regenerated '{failing_field}' JSON object."""
```

---

## New File: `pipeline/nodes/field_regenerator.py`

```python
"""
field_regenerator node.

Regenerates a single failing field in an already-assembled section.
All other fields are preserved exactly as the model originally produced them.

STATE CONTRACT
    Reads:  current_section_id, generated_sections, assembled_sections,
            rerender_requests, contract
    Writes: generated_sections[sid] (field patched),
            assembled_sections[sid] (field patched),
            rerender_requests (clears processed request),
            completed_nodes, errors
    Model:  FAST  — short targeted output, no need for STANDARD
    Skips:  if no rerender_request for current_section_id
            if block_type is not in RETRYABLE_FIELDS
"""

from __future__ import annotations

import json

from pydantic import BaseModel
from pydantic_ai import Agent

from pipeline.prompts.field_regen import (
    RETRYABLE_FIELDS,
    build_field_regen_system_prompt,
    build_field_regen_user_prompt,
)
from pipeline.providers.registry import get_node_text_model
from pipeline.state import PipelineError, TextbookPipelineState
from pipeline.llm_runner import run_llm
from pipeline.providers.registry import (
    get_node_text_route,
    get_node_text_spec,
)


class FieldOutput(BaseModel):
    """
    The regenerated field value.
    Parsed as raw dict — the field schema varies per block_type.
    Validated downstream by section_assembler when re-run.
    """
    value: dict


async def field_regenerator(
    state: TextbookPipelineState | dict,
    *,
    provider_overrides: dict | None = None,
) -> dict:
    state = TextbookPipelineState.parse(state)
    sid   = state.current_section_id

    # Find the rerender request for this section
    request = next(
        (r for r in state.rerender_requests if r.section_id == sid),
        None,
    )

    if not request:
        return {"completed_nodes": ["field_regenerator"]}

    if request.block_type not in RETRYABLE_FIELDS:
        # Not a text field — should have gone to retry_diagram
        return {"completed_nodes": ["field_regenerator"]}

    section = state.generated_sections.get(sid)
    if section is None:
        return {
            "errors": [PipelineError(
                node="field_regenerator",
                section_id=sid,
                message=f"No generated content found for {sid}",
                recoverable=False,
            )],
            "completed_nodes": ["field_regenerator"],
        }

    model = get_node_text_model(
        "field_regenerator",
        provider_overrides,
        generation_mode=state.request.mode,
    )
    route = get_node_text_route(
        "field_regenerator",
        generation_mode=state.request.mode,
    )
    spec = get_node_text_spec(
        "field_regenerator",
        generation_mode=state.request.mode,
    )

    # Raw string output — the field JSON varies per block_type
    # Parse it ourselves rather than using a typed output_type
    from pydantic_ai.models import Model

    agent = Agent(
        model=model,
        output_type=str,
        system_prompt=build_field_regen_system_prompt(state.contract.id),
    )

    try:
        result = await run_llm(
            generation_id=state.request.generation_id or '',
            node="field_regenerator",
            route=route,
            spec=spec,
            agent=agent,
            user_prompt=build_field_regen_user_prompt(
                section=section,
                failing_field=request.block_type,
                reason=request.reason,
            ),
            section_id=sid,
        )

        # Parse the raw field JSON
        raw_field = json.loads(result.output)

        # Patch only the failing field into the existing section
        patched_section = section.model_copy(
            update={request.block_type: raw_field}
        )

        # Update both generated and assembled with the patched section
        new_generated = {**state.generated_sections, sid: patched_section}
        new_assembled = {**state.assembled_sections, sid: patched_section}

        # Clear this rerender request — it has been processed
        remaining_requests = [
            r for r in state.rerender_requests
            if r.section_id != sid
        ]

        return {
            "generated_sections":  new_generated,
            "assembled_sections":  new_assembled,
            "rerender_requests":   remaining_requests,
            "completed_nodes":     ["field_regenerator"],
        }

    except json.JSONDecodeError as e:
        return {
            "errors": [PipelineError(
                node="field_regenerator",
                section_id=sid,
                message=f"Failed to parse regenerated field JSON: {e}",
                recoverable=True,
            )],
            "completed_nodes": ["field_regenerator"],
        }
    except Exception as e:
        return {
            "errors": [PipelineError(
                node="field_regenerator",
                section_id=sid,
                message=f"Field regeneration failed: {e}",
                recoverable=True,
            )],
            "completed_nodes": ["field_regenerator"],
        }
```

---

## Modified: `pipeline/routers/qc_router.py`

Add `retry_field` as a third routing outcome alongside the
existing `retry_diagram` path (from Change 5) and the full
`process_section` retry.

```python
from langgraph.graph import END
from langgraph.types import Send

from pipeline.state import TextbookPipelineState

# Text fields that field_regenerator handles
_TEXT_FIELDS = {
    'hook', 'explanation', 'practice', 'worked_example',
    'definition', 'pitfall', 'glossary', 'what_next',
}

# Diagram fields that retry_diagram handles  
_DIAGRAM_FIELDS = {
    'diagram', 'diagram_series', 'diagram_compare',
}


def route_after_qc(
    state: TextbookPipelineState | dict,
) -> list[Send] | str:
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
        base = {
            **state.model_dump(),
            'current_section_id':   section_id,
            'current_section_plan': plan.model_dump(),
        }

        if block_type in _DIAGRAM_FIELDS:
            # Only diagram failed — skip text regeneration
            sends.append(Send('retry_diagram', base))

        elif block_type in _TEXT_FIELDS:
            # Specific text field failed — targeted field retry
            sends.append(Send('retry_field', base))

        else:
            # Unknown or multi-field coherence failure — full retry
            sends.append(Send('process_section', base))

    return sends if sends else END
```

---

## Modified: `pipeline/graph.py`

Register `field_regenerator` as `retry_field` and wire its
edges. After `retry_field` completes, run `section_assembler`
and `qc_agent` again via the existing `process_section`
re-validation path — or route directly back to `route_after_qc`.

```python
from pipeline.nodes.field_regenerator import field_regenerator

# In build_graph():

# Register the new node
workflow.add_node("retry_field", field_regenerator)

# After field retry: re-assemble and re-evaluate
# The patched section needs section_assembler to re-validate
# and qc_agent to confirm the fix is good.
# Re-use the existing route_after_qc to handle any remaining issues.
workflow.add_conditional_edges("retry_field", route_after_qc)
```

Note: `retry_field` patches `assembled_sections` directly with
the corrected section, so `route_after_qc` reads the updated
`qc_reports` on the next pass. If the regenerated field still
fails and `can_rerender` is still true, it will retry again up
to `max_rerenders`.

---

## Register in Provider Registry

Add `field_regenerator` to `NODE_REQUIREMENTS` in
`pipeline/providers/registry.py`. Uses `FAST` — short targeted
output, no need for full `STANDARD` quality:

```python
"field_regenerator": {
    "draft":    NodeModelRequirements(
        capability=Capability.TEXT,
        quality_class="low",
        latency_class="fast",
        cost_class="cheap",
    ),
    "balanced": NodeModelRequirements(
        capability=Capability.TEXT,
        quality_class="low",     # FAST — output is short and targeted
        latency_class="fast",
        cost_class="cheap",
    ),
    "strict": NodeModelRequirements(
        capability=Capability.TEXT,
        quality_class="standard",  # upgrade to STANDARD for strict mode
        latency_class="standard",
        cost_class="standard",
    ),
},
```

---

## Diagnostic

```python
# Seed a known failure to verify the retry path fires correctly.
# Run this after implementing all four files.

# 1. Generate a section normally
# 2. Manually inject a bad practice field into qc_reports:
#
#    from pipeline.state import QCReport
#    state.qc_reports['s-01'] = QCReport(
#        section_id='s-01',
#        passed=False,
#        issues=[{
#            'block': 'practice',
#            'severity': 'blocking',
#            'message': 'Problems are not graduated in difficulty',
#        }],
#        warnings=[],
#    )
#
# 3. Run route_after_qc — verify it returns Send('retry_field', ...)
# 4. Run field_regenerator — verify:
#    a. only 'practice' field changes in generated_sections['s-01']
#    b. hook, explanation, what_next are byte-for-byte identical
#    c. rerender_requests is cleared for s-01
#    d. new practice has graduated difficulty (warm → medium → cold)
```

---

## What the Retry Flow Looks Like End to End

```
content_generator produces full SectionContent    (all fields)
  ↓
section_assembler validates structure             (passes)
  ↓
qc_agent evaluates semantics
  practice: problems not graduated                ← blocking
  hook: ✓  explanation: ✓  worked_example: ✓
  ↓
route_after_qc → Send('retry_field', s-01)
  ↓
field_regenerator
  receives: full section (hook, explanation, worked_example intact)
  receives: "practice — problems not graduated in difficulty"
  regenerates: practice only, with section context
  patches: section.model_copy(update={"practice": new_practice})
  ↓
route_after_qc re-evaluates updated qc_reports
  all fields pass → END
  ↓
section_ready fires with corrected section
Teacher sees: correct section, no visible retry
```

Hook, explanation, worked example — never touched.
Cost: one FAST model call (~3-5s) instead of full process_section
rerun (~25-40s).
