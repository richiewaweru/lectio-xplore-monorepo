# Handoff: Simulation Smart Frame & Simulation-First Templates

**Status**: implemented, builds clean, pending visual browser smoke test
**Related runbook**: `docs/project/runs/simulation-smart-frame-and-templates.md`
**Repos touched**: `C:\Projects\lectio` (primary), `C:\Projects\Textbook agent` (Python type mirror + contracts)

## Key Design Decision

**Simulations are LLM-generated, not per-type Svelte components.** The pipeline's interaction node produces a complete, self-contained HTML document (with embedded CSS/JS) for each simulation. `SimulationBlock` is a **smart frame** — it renders whatever HTML the LLM produces inside a sandboxed iframe and provides chrome (expand, collapse, metadata). The `SimulationType` enum (`graph_slider`, `probability_tree`, etc.) is guidance for the LLM prompt, not a component selector.

## What Changed

| Area | Outcome | Primary files |
| --- | --- | --- |
| Type system | Added `html_content?: string` to `SimulationContent` in both TypeScript and Python. When present, the frame renders a live iframe. When absent, falls back to diagram or scaffold. | `lectio/src/lib/types.ts` (line ~411), `backend/src/pipeline/types/section_content.py` (line ~327) |
| SimulationBlock | Rewrote from scaffold placeholder to smart iframe frame. Sandboxed iframe via `srcdoc`, expand/collapse overlay with backdrop dismiss and Escape key, type badge and metadata panel. | `lectio/src/lib/components/lectio/SimulationBlock.svelte` |
| Interactive Lab template | New template: simulation-first, inductive learning. Single-column layout. Simulation sits immediately after hook as the hero element. Lesson flow: Hook → Simulate → Explain → Define → Example → Practice → What next. | `lectio/src/lib/templates/interactive-lab/` (config, layout, presets, preview) |
| Guided Discovery template | New template: explanation-first, deductive learning. Two-column layout with glossary sidebar. Simulation appears after explanation to confirm understanding. Lesson flow: Hook → Explain → Define → Simulate → Example → Practice → Reflect → What next. | `lectio/src/lib/templates/guided-discovery/` (config, layout, presets, preview) |
| Preview simulations | Three hand-crafted HTML simulations embedded as `html_content` strings for testing. F=ma graph slider (interactive-lab preview + component gallery), probability tree (guided-discovery preview). | `lectio/src/lib/templates/interactive-lab/preview.ts`, `lectio/src/lib/templates/guided-discovery/preview.ts`, `lectio/src/lib/dummy-content.ts` |
| Template registry | Both templates registered. Registry now has 12 templates. | `lectio/src/lib/template-registry.ts` |
| Contract export | Both templates added to the export script. Backend contracts directory updated. | `lectio/scripts/export-contracts.ts`, `backend/contracts/interactive-lab.json`, `backend/contracts/guided-discovery.json` |

## Template Design Rationale

The two templates represent complementary pedagogical approaches to simulation-based learning:

| | Interactive Lab | Guided Discovery |
| --- | --- | --- |
| **Family** | `visual-exploration` | `guided-concept` |
| **Intent** | `explain-visually` | `introduce-concept` |
| **Approach** | Inductive — explore first, explain second | Deductive — explain first, verify with simulation |
| **Layout** | Single column (simulation is hero) | Two-column with glossary sidebar |
| **Simulation position** | Immediately after hook (slot 2) | After explanation and definition (slot 4) |
| **Best for** | STEM topics where manipulation reveals the concept | Topics that need context before interaction makes sense |
| **Required components** | header, hook, simulation, explanation, practice, what-next | header, hook, explanation, simulation, practice, what-next |
| **Subjects** | mathematics, physics, chemistry, statistics | mathematics, physics, biology, chemistry |

Both templates list `simulation-block` as a required component — they are the first templates to do so.

## SimulationBlock Architecture

```
┌──────────────────────────────────────────┐
│  Simulation  [type badge]                │
│  "Manipulate and discover"               │
│  [explanation text]                       │
│                                          │
│  ┌─────────────────────────────────┐ [⤢] │
│  │                                 │     │
│  │     IFRAME (sandboxed)          │     │
│  │     srcdoc={html_content}       │     │
│  │                                 │     │
│  └─────────────────────────────────┘     │
│                                          │
│  Type | Goal | Dimensions | Print mode   │
└──────────────────────────────────────────┘
```

Three rendering paths:
1. **`html_content` present** → sandboxed iframe with `srcdoc`, expand button, overlay pop-out
2. **`html_content` absent, `fallback_diagram` present** → static SVG diagram with caption
3. **Both absent** → scaffold placeholder with "will mount here" message

The expand overlay uses backdrop click dismiss + Escape key handling, same chrome pattern as the template preview overlay.

## Simulation Fixtures

| Simulation | Template | Description | Interactivity |
| --- | --- | --- | --- |
| F=ma slider (full) | interactive-lab | Two sliders (force 1-50N, mass 1-20kg), SVG bar chart, arrow animation, live equation | Two range inputs, real-time update |
| F=ma slider (simple) | component gallery | One slider (force 1-40N), fixed 5 kg mass, bar + equation | Single range input |
| Probability tree | guided-discovery | P(heads) slider (0.01-0.99), flip count buttons (2/3/4), SVG tree with bezier curves, leaf probabilities | Slider + button group, dynamic SVG redraw |

All three are self-contained HTML documents (~60-120 lines each) with inline CSS and JS. No external dependencies. Styled to match the template's accent color scheme.

## Validation

| Command | Result |
| --- | --- |
| `npx svelte-check` in `lectio/` | 0 errors, 0 warnings |
| `npm run package` in `lectio/` | Built clean |
| `export-contracts` | 12 templates exported |

## Not Done Yet

- **Visual browser smoke test**: Start `npm run dev` in Lectio and verify simulations render and expand/collapse works.
- **Textbook Agent frontend validation**: The consuming app has not been rebuilt after this Lectio change.
- **Pipeline integration**: The pipeline's `interaction_generator` node needs to produce `html_content` in its output. Currently only the hand-crafted fixtures demonstrate the flow.
- **Iframe communication**: No postMessage bridge exists yet. If simulations ever need to report state back to the frame (e.g., completion tracking), a message protocol will be needed.
- **Print/PDF**: The `print_translation` field is in the spec, but no print stylesheet or rendering path consumes it yet.

## Start Here Next Time

1. **Visual test**: `cd C:\Projects\lectio && npm run dev` → navigate to `/components` (scroll to SimulationBlock) and `/templates` (click Interactive Lab or Guided Discovery). Verify iframes render, sliders work, expand/collapse overlay functions.
2. **Pipeline wiring**: Read `backend/src/pipeline/nodes/` to find the interaction generator node. It needs to emit `html_content` in `SimulationContent` output. The `InteractionSpec` fields guide the LLM prompt.
3. **SimulationBlock component**: Read `lectio/src/lib/components/lectio/SimulationBlock.svelte` for the frame implementation. The iframe sandbox policy is `allow-scripts` only.
4. **Template contracts**: Read `lectio/src/lib/templates/interactive-lab/config.ts` and `lectio/src/lib/templates/guided-discovery/config.ts` for the generation guidance, lesson flow, and component requirements.
5. **Type sync**: Any changes to `SimulationContent` or `InteractionSpec` must be mirrored in both `lectio/src/lib/types.ts` and `backend/src/pipeline/types/section_content.py`.

## Risks

- Do not create per-type Svelte simulation components. The simulation `type` field is LLM guidance, not a component selector. All simulation types render through the same iframe frame.
- Do not weaken the iframe sandbox policy without review. `allow-scripts` is sufficient for current simulations. Adding `allow-same-origin` would let iframe JS access the parent page.
- The hand-crafted HTML fixtures are developer test data. Do not treat their structure as a stable contract — the LLM will produce its own HTML with varying structure.
- Both new templates require `simulation-block`. If a generation lacks a simulation, the template will show a scaffold placeholder in that slot, which is intentional graceful degradation.
