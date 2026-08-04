# Adaptive HTML Rendering System — Final Practical Specification

This document describes the final architecture for rendering AI‑generated textbook sections into high‑quality interactive HTML pages. It merges all best ideas discussed: template systems, behaviour vocabulary, LLM reasoning, universal runtime behaviours, and visual QA.

The goal is simple:

**Generate textbook content → render it as a living, interactive learning page that works across templates, devices, and future expansions.**

This spec is written in straightforward language so both product and engineering teams can use it.

---

# 1. Core Idea

We separate the system into **four responsibilities**:

1. **Content generation** — what the section teaches
2. **Layout** — where content appears on the page
3. **Behaviour** — how the page responds to the learner
4. **Quality control** — verifying the rendered page actually works

Each responsibility is handled by a different part of the system.

This separation keeps the system stable while still allowing flexibility.

---

# 2. Rendering Pipeline

The rendering pipeline works in stages.

```
Teacher input
      ↓
Curriculum Planner
      ↓
Content Generator
      ↓
Diagram Generator
      ↓
Semantic Section Object
      ↓
TemplateConfig
      ↓
LayoutPlan
      ↓
BehaviorPlan
      ↓
ResponsivePlan
      ↓
Template Renderer
      ↓
Universal Runtime Behaviours
      ↓
Interactive Behaviour Runtime
      ↓
Visual QC Agent
      ↓
Final HTML Output
```

Every stage has a clear job.

---

# 3. Semantic Section Object

All rendering begins with a **structured section object**.

Example:

```
{
  section_id: "limits_intro",
  subject: "math",
  blocks: {
    hook: {...},
    explanation: {...},
    definition: {...},
    worked_example: {...},
    practice: {...}
  },
  diagrams: [...]
}
```

This contains the educational content but **no layout or behaviour decisions yet**.

---

# 4. Template System

Templates define the visual identity and layout rules.

A template includes:

- colours
- typography
- spacing
- layout zones
- allowed behaviours
- responsive rules
- print rules

Templates do **not** define behaviour logic.

They only declare what behaviours are allowed.

Example template capability declaration:

```
{
  allow_sticky_sidebar: true,
  allow_tabs: false,
  allow_accordion: true,
  allow_zoom: true
}
```

This keeps the LLM from using behaviours that would break the template.

---

# 5. LayoutPlan

The LayoutPlan decides **where blocks appear on the page**.

Example:

```
hook → hero card
explanation → main column
diagram → right column
practice → bottom accordion stack
```

The LayoutPlan only controls placement and grouping.

It does **not** control interaction yet.

---

# 6. Behaviour System

Behaviours make the page interactive.

Instead of defining behaviours per template, the system maintains a **shared behaviour vocabulary**.

Examples of behaviours:

- hint-toggle
- step-reveal
- accordion
- tabs
- zoom
- tooltip
- sticky-sidebar
- quiz-check
- toggle-view

The LLM selects behaviours based on content and template capabilities.

Example output:

```
<div data-behaviour="accordion">
<figure data-behaviour="zoom">
<section data-section-index="2">
```

The runtime activates these behaviours.

---

# 7. BehaviourPlan

The BehaviourPlan records which behaviours should apply to each block.

Example:

```
worked_example → step-reveal
practice → accordion
key_terms → sticky-sidebar
figure → zoom
```

The LLM generates this plan using the behaviour vocabulary.

---

# 8. ResponsivePlan

The ResponsivePlan defines how the layout adapts to screen sizes.

Examples:

Desktop

- sidebar visible
- two column layout

Tablet

- sidebar collapses
- stacked columns

Mobile

- glossary becomes drawer
- sections may become tabs

This ensures the page works across devices.

---

# 9. Universal Runtime Behaviours

Some behaviours should always exist, even if the LLM forgets them.

These are injected automatically by `universal.js`.

Examples:

1. Hint toggle
2. Section anchor navigation
3. Reading progress bar
4. Zoom on dense diagrams
5. Overflow scroll for wide tables
6. Keyboard navigation
7. External link safety

These guarantee a minimum level of usability.

---

# 10. Behaviour Runtime

The runtime reads behaviour attributes and activates components.

Example behaviours implemented by runtime:

- accordions
- tab switching
- step reveal
- tooltips
- zoom overlays
- quizzes

Unknown behaviours are logged but do not break the page.

---

# 11. Behaviour Safety System

If the LLM outputs a behaviour that is not recognised:

1. runtime logs the behaviour
2. page falls back to static rendering
3. QC records the unknown behaviour

This allows the behaviour vocabulary to evolve safely.

---

# 12. Visual Quality Control

After rendering, the system verifies the page visually.

The Visual QC agent:

1. renders the page in a headless browser
2. scrolls the page
3. captures screenshots
4. runs rule checks
5. runs vision checks

Problems detected include:

- clipped diagrams
- overflowing text
- unreadable components
- broken navigation
- inconsistent layout

QC returns a structured report.

---

# 13. Targeted Rerender System

If QC detects problems, only the failing part is regenerated.

Example fixes:

```
diagram too small → regenerate diagram
component overflow → change layout component
missing behaviour → rerun behaviour reasoning
```

Content itself is preserved unless necessary.

This prevents drift during corrections.

---

# 14. Three Confidence Levels

The system balances reliability and flexibility using three behaviour tiers.

Tier 1 — Deterministic

Always applied automatically.

Examples:

- hint toggles
- navigation
- zoom detection

Tier 2 — LLM Reasoned

LLM selects behaviours from vocabulary.

Examples:

- accordion
- step reveal
- toggle view

Tier 3 — Graceful Fallback

If behaviour fails, safe fallback rendering is used.

Examples:

- inline layout
- expanded blocks
- static diagrams

---

# 15. Behaviour Categories

Behaviours fall into categories.

Disclosure behaviours

- hint-toggle
- step-reveal
- accordion

Visual behaviours

- zoom
- highlight-row
- tooltip

Navigation behaviours

- sticky-sidebar
- section-anchor

Assessment behaviours

- quiz-check
- toggle-view

This structure helps the LLM reason more clearly.

---

# 16. Universal Design Principles

Every rendered page should follow these principles:

- interaction must improve understanding
- dense information must be expandable
- diagrams must be readable
- navigation must always work
- print output must remain usable

Avoid interactions that are decorative but educationally meaningless.

---

# 17. Handling New Templates

When a new template is introduced:

The author provides

- style tokens
- component templates
- capability declarations

The system automatically applies

- universal behaviours
- behaviour vocabulary reasoning
- visual QC

This allows new templates to work without new runtime code.

---

# 18. Implementation Phases

Phase 1 — Foundation

- universal runtime behaviours
- behaviour vocabulary
- behaviour dispatcher

Phase 2 — Behaviour reasoning

- BehaviourPlan generation
- template capability system

Phase 3 — QC system

- rule-based checks
- visual screenshot checks

Phase 4 — automated repair

- rerender instructions
- targeted regeneration

---

# 19. Final Philosophy

Templates define **structure**.

Behaviours define **motion**.

The LLM chooses **appropriate motion**.

The runtime guarantees **baseline usability**.

QC ensures **visual correctness**.

Together they create a robust generative UI system.

---

# 20. End Result

The system moves from:

```
content → static HTML
```

To:

```
content → adaptive layout → behaviour reasoning → interactive runtime → visual QA
```

The result is a textbook page that is:

- interactive
- readable
- responsive
- printable
- resilient to new templates

This is the foundation of a scalable **AI‑generated learning interface**.

