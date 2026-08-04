# Textbook Presentation System — Merged Architecture
**Version:** 2.0 (synthesis of both proposals)
**Status:** Canonical specification — supersedes both prior documents
**Grounded in:** PDF pipeline output, calculus_section1_v2.html,
                 calculus_intro_interactive_book.html

---

## Executive Summary

The content generation pipeline is working. The bottleneck has moved
downstream into presentation architecture.

A generated section can be conceptually correct and still fail
pedagogically if the reading experience is visually noisy, diagram
placement is poorly timed, spacing is dense, interaction is absent,
or print output feels like a downgraded afterthought.

The goal is a deterministic presentation system that turns structured
educational content into high-quality, subject-aware, student-appropriate
HTML and print artifacts — consistently, across all subjects, all
learner groups, all templates.

**The shift:**

> Generate content → assemble document

becomes:

> Generate structured content → resolve layout strategy →
> apply template system → render HTML and print intentionally →
> QA presentation → ship artifact

That shift is not cosmetic. It is the product.

---

## 1. Diagnosis From the Actual Files

### The PDF Pipeline Output (Current state)

The generated PDF has correct structure. The pedagogy is sound.
But the presentation signals "generated document" not "designed artifact."

**Specific failures observed:**

The section headings use a monospace font for prose-level headings.
Monospace belongs to code and notation — applied to "Practice Problems"
it reads as a formatting accident.

The spacing has no rhythm. Large expanses of white below practice
problems feel like the layout ran out of decisions, not like intentional
breathing room.

The definition box works but is minimal. The DEFINITION label has
insufficient separation from the body text below it. The hierarchy
inside the box is underdeveloped.

The blocks are isolated, not connected. Each block floats independently
with no visual thread connecting them into a reading sequence.
The page feels like labeled boxes rather than guided cognitive motion.

**What is already strong:** The SVG diagram of the falling ball
is the best element in the file. Well-constructed, correctly placed,
figure caption appropriately styled. This is the one component that
already reads as intentional.

### calculus_section1_v2.html (Iteration 2 — strong)

This file proves the presentation ceiling is high.

What it gets right: cream background signals academic artifact.
Lora serif is the right body font for mathematical reading.
The hero block is excellent. The margin note sidebar is the
smartest structural decision in any of the three files —
vocabulary terms sticky on the right while the learner reads.
The two-question frame (derivative vs. integral side by side)
makes conceptual structure visible as a spatial relationship.
The insight strip (three-column comparison) is pedagogically
exact and well executed.

**The problem:** this quality was hand-crafted, not generated.
The architecture question is how to make generated output look
like this, consistently, without hand-crafting each file.

**What it still lacks:** the print CSS exists but is incomplete.
The cream background and dark hero need full `@media print`
overrides. The sidebar has no print-specific layout that
preserves its vocabulary content.

### calculus_intro_interactive_book.html (Interactive — different category)

This is a different product from the other two. Dark mode,
Inter sans-serif, football analogy, animated sliders,
quiz buttons with JS feedback.

What it demonstrates: the slider interaction on the runner's
position and the slope steepness slider are genuinely effective
at building intuition before notation arrives. Moving the slider
and watching the runner change position is better than reading
"the function is non-linear" for a first encounter with rates.

The two-column grid (story left, visual right) is the right
layout for interactive content. The inline quiz with immediate
feedback closes the loop without leaving the page.

**The gap:** no print path. Printed, this file produces a page
with static sliders and dead buttons. It is screen-only by design.

### The Core Problem Statement

> How do we transform structured educational content into
> visually coherent, template-driven learning artifacts across
> HTML and print — with subject awareness, learner differentiation,
> determinism, scalability, and cost-aware monetization?

That is the actual product problem.

---

## 2. Product Principles

**Content and presentation must remain separate.**
The generator produces structured educational meaning.
The renderer decides how that meaning appears.
If the LLM is asked to decide content and final visual design
at once, consistency will drift.

**HTML and print are siblings, not copies.**
The print version should not be a flattened screenshot of the HTML.
They share a common semantic structure but use different rendering rules.
Print is a translation of HTML, not a downgrade of it.

**Templates control variability.**
Do not allow every output to invent its own appearance.
Let templates absorb variation in a controlled way.
Deterministic template behaviour beats endless visual experimentation.

**Subject should influence layout.**
Mathematics benefits from step logic, symbolic prominence, graph adjacency.
Chemistry benefits from comparison tables and reaction flows.
Literature benefits from text flow, side annotations, quotation hierarchy.
Subject-aware layout is not decoration — it reduces cognitive load.

**Cognitive load governs design.**
A layout is not good because it looks expensive. It is good because it
reduces unnecessary processing while preserving challenge.

**Teachers choose a teaching style, not a skin.**
The gallery should feel like choosing how to present ideas,
not browsing colour schemes. That distinction matters deeply.

---

## 3. New Pipeline Architecture

The current pipeline:

```
Teacher Input → Curriculum Planner → Content Generator
→ Diagram Generator → Assembler → Quality Checker → Output
```

The new pipeline:

```
Teacher Input
  → Curriculum Planner
  → Content Generator        [produces semantic field objects]
  → Diagram Generator        [produces diagram specs + SVG assets]
  → Section Layout Resolver  [NEW — decides layout archetype]
  → Template Engine          [applies visual rules and tokens]
  → HTML Renderer            [screen output]
  → Print Renderer           [print output from same semantic data]
  → Presentation QA          [NEW — separate from content QC]
  → Final Output
```

**Four new layers:**

**Section Layout Resolver** — reads the section's subject, learner
profile, concept type, and block composition, then decides which
layout archetype fits. This is a rule-based decision, not an LLM call.
It produces a `layout_type` field that the template engine reads.

**Template Engine** — applies the selected template's visual tokens,
layout rules, interaction rules, and spacing system to the semantic blocks.
Produces a renderable intermediate representation.

**Dual Renderers** — HTML Renderer and Print Renderer both consume the
same template-engine output but apply different surface rules.
They are siblings, not copies.

**Presentation QA** — validates layout quality independently of content
quality. Runs after rendering, before delivery. Has its own failure
categories and its own rerun triggers.

---

## 4. The Semantic Section Object

The renderer consumes a typed section object, not raw prose blobs.

```json
{
  "section_id": "limits_intro_01",
  "subject": "mathematics",
  "grade_band": "secondary",
  "learner_profile": "scaffolded_visual",
  "template_id": "concept_explorer_v1",
  "archetype": "guided_concept_path",
  "layout_type": "hook_splitpanel_formal_practice",
  "blocks": {
    "hook": {
      "type": "hook",
      "title": "string",
      "body": "string"
    },
    "prerequisites": {
      "type": "prerequisites",
      "items": ["string"]
    },
    "plain_explanation": {
      "type": "explanation",
      "body": "string"
    },
    "formal_definition": {
      "type": "definition",
      "term": "string",
      "formal": "string",
      "plain": "string"
    },
    "worked_example": {
      "type": "worked_example",
      "title": "string",
      "steps": [{"label": "string", "content": "string"}],
      "conclusion": "string"
    },
    "pitfall": {
      "type": "pitfall",
      "body": "string"
    },
    "think_prompt": {
      "type": "think",
      "question": "string"
    },
    "practice": {
      "type": "practice",
      "problems": [
        {"difficulty": "warm", "question": "string", "hint": "string"},
        {"difficulty": "medium", "question": "string", "hint": "string"},
        {"difficulty": "cold", "question": "string", "hint": "string"}
      ]
    },
    "interview_anchor": {
      "type": "anchor",
      "prompt": "string"
    },
    "whats_next": {
      "type": "next",
      "body": "string"
    }
  },
  "diagram_specs": [
    {
      "id": "diag_01",
      "type": "svg",
      "placement": "after_plain_explanation",
      "caption": "string",
      "svg_content": "string"
    }
  ],
  "presentation_settings": {
    "template_id": "concept_explorer_v1",
    "interaction_level": "low",
    "writein_lines": 4,
    "print_profile": "clean_academic"
  }
}
```

Three advantages from this structure:
- renderers are deterministic — same object always produces the same output
- templates are swappable without touching content
- Presentation QA can validate structure before any rendering happens

---

## 5. Three Layout Archetypes

Not ten independent templates with no grouping.
Three archetypes that all templates belong to.
Templates within an archetype share a block order and flow logic —
they differ in visual tokens, interaction level, and density.

### Archetype A — Guided Concept Path

**Best for:** middle school math, introductory science,
scaffolded learners, below-average and average groups

**Block order:**
```
Hook → Prerequisite refresh → Plain explanation →
Visual model → Formal definition → Worked example →
Practice → Reflection / what's next
```

**Why it works:** stable, predictable, low cognitive friction.
Clear progression from intuition to formality.
The learner always knows where they are in the sequence.

**Layout patterns used:**
single column with breathing room, optional margin note sidebar,
diagrams placed immediately after the concept they explain.

---

### Archetype B — Concept + Compare + Apply

**Best for:** chemistry, biology, social studies, concept families
where contrast or classification is central to understanding

**Block order:**
```
Hook → Core idea → Comparison panel or dual diagram →
Labeled visual → Worked example or case study →
Pitfall / misconception → Practice set → Extension
```

**Why it works:** supports classification learning,
works well with tables, card grids, and split panels,
good for distinguishing similar concepts.

**Layout patterns used:**
two-column panels for comparisons, data tables,
side-by-side concept cards, reaction flow diagrams.

---

### Archetype C — Formal Track / Problem-Solving Notebook

**Best for:** advanced mathematics, proof-based content,
higher rigor tracks, gifted learners, exam prep

**Block order:**
```
Precision setup → Notation and assumptions →
Formal statement → Derivation or proof sketch →
Worked example → Challenge problems →
Connection to future formalism
```

**Why it works:** respects advanced learners,
allows less hand-holding without losing structure,
visually signals rigor and seriousness.
Less analogy, more formal development.

**Layout patterns used:**
tight typographic grid, equation numbering,
derivation step layout, minimal decorative elements.

---

### Archetype Selection Rules (Section Layout Resolver)

The resolver is a deterministic rule function, not an LLM call.

```python
def resolve_archetype(section: SectionObject) -> Archetype:

    grade = section.grade_band           # primary | secondary | advanced
    subject = section.subject
    profile = section.learner_profile    # scaffolded | standard | advanced
    concept_type = section.concept_type  # definition | procedure | comparison
                                         # proof | application

    # Formal track: advanced profile + proof/derivation concept
    if profile == "advanced" and concept_type in ("proof", "derivation"):
        return Archetype.FORMAL_TRACK

    # Compare+Apply: comparison or classification concept type
    if concept_type == "comparison":
        return Archetype.COMPARE_APPLY

    # Compare+Apply: subjects where contrast is structurally important
    if subject in ("chemistry", "biology", "social_studies") \
       and concept_type in ("comparison", "classification"):
        return Archetype.COMPARE_APPLY

    # Default: guided concept path
    return Archetype.GUIDED_CONCEPT_PATH
```

---

## 6. Five-Layer Template Structure

A template is not a CSS file. It is a complete rendering strategy
packaged into five layers.

### Layer 1 — Visual Tokens

The design system variables:

```python
class VisualTokens(BaseModel):
    # Typography
    font_body: str            # e.g. "Lora" | "Source Serif 4"
    font_heading: str         # e.g. "DM Sans" | "IBM Plex Mono"
    font_mono: str            # e.g. "DM Mono" | "JetBrains Mono"
    font_size_body: str       # e.g. "17px"
    line_height_body: float   # e.g. 1.75

    # Colours — screen values
    colour_background: str
    colour_surface: str
    colour_ink: str
    colour_ink_mid: str
    colour_ink_light: str
    colour_accent_primary: str
    colour_accent_secondary: str
    colour_accent_warning: str
    colour_accent_info: str
    colour_rule: str

    # Colours — print-safe equivalents (validated against #ffffff)
    print_background: str     # always white or near-white
    print_ink: str            # always near-black
    print_accent_primary: str
    print_accent_secondary: str
    print_accent_warning: str
    print_accent_info: str

    # Shape
    radius_sm: str
    radius_md: str
    radius_lg: str
    shadow: str               # e.g. "none" | "0 2px 8px rgba(0,0,0,0.08)"
```

### Layer 2 — Layout Rules

```python
class LayoutRules(BaseModel):
    content_max_width: str          # e.g. "720px" | "800px"
    content_padding: str            # e.g. "0 2rem"
    has_sidebar: bool
    sidebar_width: str              # e.g. "220px"
    has_hero: bool
    hero_style: str                 # "dark" | "light" | "accent" | "none"
    allow_split_panels: bool        # two-column content layout
    allow_floating_diagrams: bool
    max_line_length: int            # characters, e.g. 72
    prefer_short_blocks: bool
    block_order_override: list[str] # if archetype default is overridden
    diagram_placement: str          # "after_reference" | "inline" | "end"
```

### Layer 3 — Interaction Rules (HTML only)

```python
class InteractionRules(BaseModel):
    level: Literal["none", "low", "medium", "high"]
    # none:   static HTML, zero JS, fully print-safe
    # low:    <details>/<summary> collapsibles, no JS required
    # medium: CSS animations, reveal-next-step, no sliders
    # high:   sliders, live SVG, inline quiz, Pyodide code cells

    allow_sliders: bool
    allow_reveal_steps: bool        # step-by-step worked example
    allow_quiz: bool
    allow_animated_diagrams: bool
    allow_toggle_formal: bool       # toggle between plain and formal view
    allow_motion: str               # "none" | "subtle" | "full"
```

**Interaction level implementation:**

*None:* Pure HTML and CSS. `<details>/<summary>` for hints uses no JS.

*Low:* Adds `IntersectionObserver` for fade-in on scroll.
No sliders. No live computation. `@media print` disables all animation.

*Medium:* Everything in low, plus SVG path draw-on-scroll,
step-by-step worked example progression.
Print: all steps revealed, animations stripped.

*High:* Everything in medium, plus sliders tied to live SVG updates,
inline quiz with JS feedback, optional Pyodide code cells.
Print: sliders replaced with static mid-state diagram,
quiz buttons replaced with write-in blanks.

### Layer 4 — Print Rules

```python
class PrintRules(BaseModel):
    page_margin_top: str            # e.g. "2.2cm"
    page_margin_bottom: str
    page_margin_outer: str
    page_margin_binding: str        # wider if double-sided
    font_size_body_print: str       # e.g. "11pt"
    grayscale_safe: bool
    writein_lines: int              # blank lines per practice problem
    writein_line_height: str        # e.g. "2em"
    # Blocks that must never split across pages
    avoid_break_inside: list[str]
    # Interactive element print replacements
    slider_print_replacement: str   # "static_midstate" | "table" | "hide"
    quiz_print_replacement: str     # "writein" | "hide"
    hint_print_behaviour: str       # "always_visible" | "hide"
```

**The print translation contract:**

Every interactive element has a defined print equivalent.
This is not a downgrade — it is a translation.

| Screen element | Print translation |
|---|---|
| Interactive slider | Static diagram at slider midpoint |
| Animated graph | Annotated static SVG |
| Collapsible hint | Fully visible hint text |
| Quiz buttons | Write-in blank lines |
| Step reveal | All steps fully expanded |
| Sticky sidebar | Content moved to page margin notes |
| Dark hero block | Light equivalent with border |

### Layer 5 — Generation Guidance

This layer links the template to the upstream content generator.
It is injected as formatting constraints into the ContentGenerator prompt.
It does not change what concepts are generated — only how verbosely
and what structural elements are included.

```python
class GenerationGuidance(BaseModel):
    verbosity: str              # "concise" | "moderate" | "rich"
    max_hook_words: int
    max_explanation_words: int
    max_definition_words: int
    max_worked_example_steps: int
    max_practice_problems: int
    diagram_density: str        # "minimal" | "standard" | "rich"
    formalism_delay: str        # "immediate" | "after_intuition" | "late"
    example_count: int
    prefer_visual_metaphors: bool
    sentence_density: str       # "sparse" | "standard" | "dense"
```

---

## 7. Template Configuration Schema

The complete template config is the union of all five layers:

```json
{
  "template_id": "concept_explorer_v1",
  "name": "Concept Explorer",
  "description": "General math and science. Balanced, visual-first, safe default.",
  "archetype": "guided_concept_path",
  "subjects": ["mathematics", "physics", "intro_science"],
  "grade_bands": ["secondary"],
  "learner_profiles": ["scaffolded", "standard"],
  "tier": "standard",

  "tokens": {
    "font_body": "Lora",
    "font_heading": "DM Sans",
    "font_mono": "DM Mono",
    "font_size_body": "17px",
    "line_height_body": 1.75,
    "colour_background": "#fdfaf5",
    "colour_surface": "#ffffff",
    "colour_ink": "#1a1714",
    "colour_ink_mid": "#4a4540",
    "colour_accent_primary": "#3d2fa8",
    "colour_accent_secondary": "#0e6b50",
    "colour_accent_warning": "#8c3012",
    "colour_accent_info": "#0d4fa8",
    "colour_rule": "#e2dbd0",
    "print_background": "#ffffff",
    "print_ink": "#111111",
    "print_accent_primary": "#3d2fa8",
    "print_accent_warning": "#8c3012",
    "radius_md": "10px",
    "radius_lg": "16px",
    "shadow": "none"
  },

  "layout": {
    "content_max_width": "720px",
    "has_sidebar": true,
    "sidebar_width": "220px",
    "has_hero": true,
    "hero_style": "dark",
    "allow_split_panels": true,
    "max_line_length": 72,
    "diagram_placement": "after_reference"
  },

  "interaction": {
    "level": "low",
    "allow_sliders": false,
    "allow_reveal_steps": false,
    "allow_quiz": false,
    "allow_motion": "none"
  },

  "print": {
    "page_margin_top": "2.2cm",
    "page_margin_bottom": "2cm",
    "page_margin_outer": "2cm",
    "page_margin_binding": "2.5cm",
    "font_size_body_print": "11pt",
    "grayscale_safe": true,
    "writein_lines": 4,
    "avoid_break_inside": [
      "worked_example", "definition", "practice_item",
      "hook", "pitfall", "figure"
    ],
    "slider_print_replacement": "static_midstate",
    "quiz_print_replacement": "writein",
    "hint_print_behaviour": "always_visible"
  },

  "generation_guidance": {
    "verbosity": "moderate",
    "max_hook_words": 80,
    "max_explanation_words": 300,
    "max_definition_words": 120,
    "max_worked_example_steps": 5,
    "max_practice_problems": 3,
    "diagram_density": "standard",
    "formalism_delay": "after_intuition",
    "example_count": 2,
    "prefer_visual_metaphors": true,
    "sentence_density": "standard"
  }
}
```

---

## 8. HTML Component Library

Each template provides implementations of these named components.
The component names are fixed. The implementations differ per template.

```
HeroIntroBlock        — section title, subtitle, level pills, subject symbol
HookCard              — intuition hook with icon and border treatment
PrerequisiteStrip     — compact horizontal list of assumed knowledge
SplitExplainVisual    — two-column: prose left, diagram right
DefinitionCard        — formal definition with term, formal, and plain fields
WorkedExampleStepper  — numbered steps with optional reveal-next behaviour
MisconceptionAlert    — pitfall box with warning treatment
ThinkPromptPause      — think prompt with visual pause cue
PracticeTierGrid      — warm/medium/cold problems with hint behaviour
InterviewAnchor       — interview prompt with distinct visual treatment
WhatsNextBridge       — what's next with forward connection
MarginNote            — sticky sidebar vocabulary item
InsightStrip          — three-column comparison cell
```

The renderer calls `template.render_component(component_name, block_data)`
and receives HTML. The renderer never writes HTML directly —
it assembles components. This is the determinism guarantee.

---

## 9. @media print — Complete Implementation

The print block is never optional and never added later.
Every template ships with a complete `@media print` block on day one.
This is the complete required structure:

```css
@media print {

  /* 1. Hide navigation and UI chrome */
  nav, .sidebar, .print-btn, .no-print,
  .hint-toggle-btn, .quiz-buttons,
  .slider-wrap, .step-reveal-btn { display: none !important; }

  /* 2. Page setup */
  @page {
    margin: 2.2cm 2cm 2cm 2.5cm;
    size: A4;
  }
  @page :first { margin-top: 3cm; }

  /* 3. Background and colour reset */
  body, .page-wrap, .content-band,
  .section-hero, .padded {
    background: white !important;
    color: #111111 !important;
  }

  /* 4. Block print overrides — every block type */
  .block-hook {
    background: #f5fff8 !important;
    border-left: 3px solid #006830 !important;
    color: #111111 !important;
  }
  .block-definition {
    background: #f9f7ff !important;
    border-left: 3px solid #3d2fa8 !important;
    color: #111111 !important;
  }
  .block-pitfall {
    background: #fff8f5 !important;
    border-left: 3px solid #8c3012 !important;
    color: #111111 !important;
  }
  .block-anchor {
    background: #f5f8ff !important;
    border-left: 3px solid #0d4fa8 !important;
    color: #111111 !important;
  }
  .block-next {
    background: #fffdf0 !important;
    border-left: 3px solid #7a5500 !important;
    color: #111111 !important;
  }

  /* 5. SVG print overrides — dark backgrounds become white */
  svg { background: white !important; }
  svg rect[fill="#0b1020"],
  svg rect[fill="#121933"],
  svg rect[fill="#1a1714"],
  svg rect[fill="#141414"] { fill: white !important; }
  svg text { fill: #111111 !important; }

  /* 6. Page break rules — never negotiable */
  table, figure,
  .block-worked, .block-definition, .block-hook,
  .block-pitfall, .block-anchor, .problem-card,
  .insight-strip, .two-q-frame, .code-wrap {
    break-inside: avoid;
    page-break-inside: avoid;
  }
  h1, h2, h3, h4 {
    break-after: avoid;
    page-break-after: avoid;
  }
  p { orphans: 3; widows: 3; }

  /* 7. Interactive element print replacements */
  .slider-print-replacement { display: block !important; }
  .writein-space { display: block !important; }
  .quiz-writein { display: block !important; }
  .hint-body { display: block !important; } /* hints always visible */

  /* 8. Write-in lines for practice problems */
  .writein-line {
    border-bottom: 1px solid #cccccc;
    height: 2em;
    margin-bottom: 0.25rem;
    display: block;
  }

  /* 9. Font sizes for print */
  body { font-size: 11pt; line-height: 1.65; }
  h1   { font-size: 26pt; }
  h2   { font-size: 18pt; }
  h3   { font-size: 13pt; }
  .code-block { font-size: 9pt; }

  /* 10. Code blocks — keep dark for print legibility */
  .code-block {
    background: #f4f4f4 !important;
    color: #111111 !important;
    border: 1px solid #cccccc;
    white-space: pre;
  }
}
```

---

## 10. Presentation QA Layer

This layer runs after rendering, before delivery.
It is completely separate from the content QC node.
Content QC validates educational substance.
Presentation QA validates visual and layout quality.

### Six QA Categories

**Structural QA**
- Heading hierarchy is consistent (no H4 without H3 parent)
- No heading followed immediately by another heading
- Block order matches archetype for the selected template
- No empty blocks or placeholder text
- All practice problems have exactly the required difficulty levels

**Visual QA**
- All text colours pass 4.5:1 contrast on both screen background and white
- No forbidden colour combinations (red/green, yellow/white, etc.)
- All callout boxes have corresponding print colour overrides
- No SVG with dark background lacking print override

**Cognitive Load QA**
- No more than two consecutive prose-only blocks without a visual break
- No paragraph exceeding 120 words
- No worked example with more than allowed steps for template
- No more than one pitfall block per section (unless pitfall-specific section)
- Diagram placement: within two blocks of the concept it illustrates

**Accessibility QA**
- All images have alt text or figure captions
- All interactive elements have keyboard-accessible equivalents
- Interactive elements that lack JS fallbacks are flagged
- Colour is never the sole means of conveying meaning

**Print QA**
- No table estimated taller than 60% of a print page without
  `break-before: page` class
- No code lines exceeding 80 characters without overflow handling
- No figure separated from its caption across a page break
- Write-in lines present if `writein_lines > 0` in print config
- All interactive elements have print replacements present in HTML

**Tier Compliance QA**
- Basic tier: no JS-dependent interactions present
- Standard tier: interaction level matches template config
- Premium tier: all interactive elements have validated print fallbacks

### QA Failure Actions

| Category | On failure |
|---|---|
| Structural | Re-run content generator for affected section |
| Visual | Re-run renderer with corrected token values |
| Cognitive load | Re-run content generator with tighter verbosity constraint |
| Accessibility | Re-run renderer with missing attributes |
| Print | Re-run renderer with corrected print rules |
| Tier compliance | Re-run renderer; do not regenerate content |

---

## 11. The Ten Templates — Mapped to Archetypes

Templates are organised by archetype family.
Within a family, templates share block order and flow logic.
They differ in visual tokens, interaction level, and density.

### Family A — Guided Concept Path

**T01 — Concept Explorer** *(Standard)*
The safe default. Balanced, visual-first, academic serif.
Based on `calculus_section1_v2.html` — already 80% built.
Cream background, Lora body, margin note sidebar.
Best for: general mathematics, introductory science.
Interaction: low. Print: excellent.

**T02 — Notebook Calm** *(Basic)*
Minimal, high readability, soft structure.
White background, larger type, more spacing.
SPED-friendly, high-contrast, no decorative elements.
Best for: any subject, scaffolded learners.
Interaction: none. Print: excellent.

**T03 — Middle School Momentum** *(Standard)*
Chunked blocks, brighter visual cues, lower intimidation factor.
Rounder corners, stronger colour, more generous spacing.
Best for: K-8, below-average and average groups.
Interaction: low. Print: excellent.

**T04 — Interactive Fieldbook** *(Premium)*
Sliders, live SVG, inline quiz. Dark navy, Inter sans-serif.
Based on `calculus_intro_interactive_book.html` — already built.
Best for: calculus, physics, any concept needing manipulation.
Interaction: high. Print: fair (with static replacements).

### Family B — Compare + Apply

**T05 — Science Studio** *(Standard)*
Split panels, labeled diagrams, comparison emphasis.
Blue-teal system, data table layout, scientific illustration style.
Best for: biology, chemistry, physics.
Interaction: medium. Print: good.

**T06 — Chem Structure Lab** *(Standard)*
Reaction-flow friendly, molecule and labeled-figure oriented.
Structured comparison grids, step-reaction diagrams.
Best for: chemistry specifically.
Interaction: low. Print: good.

**T07 — Probability Cases** *(Standard)*
Tree diagrams, outcome boxes, scenario grids.
Amber accent system, case study layout.
Best for: probability and statistics.
Interaction: medium (tree expansion). Print: good.

### Family C — Formal Track

**T08 — Proof Track** *(Premium)*
Advanced mathematics. Precise typography, derivation-centric.
EB Garamond, tight spacing, equation numbering, minimal colour.
Best for: advanced mathematics, gifted learners.
Interaction: none. Print: excellent.

**T09 — Exam Builder** *(Standard)*
Rigor-forward, compact spacing, worked-example heavy.
Preparation aesthetic. Problem density higher than other templates.
Best for: exam prep, challenge sets.
Interaction: low. Print: excellent.

### Universal

**T10 — Minimal Print-First** *(Basic)*
Pure white, system serif, maximum content density.
Zero decorative elements. Black-and-white laser printing optimised.
Best for: any subject, high print volume, ink cost management.
Interaction: none. Print: best of all templates.

### Template Selection Matrix

| Template | Archetype | Subject fit | Interaction | Print | Tier |
|---|---|---|---|---|---|
| T01 Concept Explorer | A | STEM general | Low | Excellent | Standard |
| T02 Notebook Calm | A | Universal | None | Excellent | Basic |
| T03 Middle School | A | K-8 universal | Low | Excellent | Standard |
| T04 Interactive Fieldbook | A | STEM intro | High | Fair | Premium |
| T05 Science Studio | B | Bio/Chem/Physics | Medium | Good | Standard |
| T06 Chem Structure Lab | B | Chemistry | Low | Good | Standard |
| T07 Probability Cases | B | Statistics | Medium | Good | Standard |
| T08 Proof Track | C | Advanced math | None | Excellent | Premium |
| T09 Exam Builder | C | Any exam prep | Low | Excellent | Standard |
| T10 Minimal Print | Universal | Any | None | Best | Basic |

---

## 12. Template Gallery Design

The gallery is the teacher-facing product surface.
It should show outcomes, not names.

Each template card shows:
- Name and short promise
- Subject fit
- Learner group fit
- Interaction level (visual indicator, not just text)
- Print friendliness rating
- Thumbnail preview (actual rendered sample, not mock)
- Tier badge
- Archetype family

**Gallery filters (launch):**
- Subject
- Interaction level / visual richness
- Print friendliness

**Gallery filters (later):**
- Grade band
- Learner support level
- Formalism level
- Tier

**The UX principle:**
Teachers should feel they are choosing a teaching style.
Not browsing colour schemes.
The template name and short promise carry this:
"Concept Explorer — for learners who need intuition before formalism"
is choosing a teaching philosophy.
"Blue academic theme" is browsing skins.

---

## 13. Monetisation — Three Tiers

Content quality is identical across all tiers.
Factual accuracy, pedagogical soundness, curriculum alignment,
structural completeness — none of these vary by tier.
Tiering is only around presentation richness.

**Free / Entry**
- T02 Notebook Calm and T10 Minimal Print
- Static diagrams only
- No JavaScript interactions
- Basic print profile
- Solid but restrained appearance

**Standard / Teacher Pro**
- T01, T03, T05, T06, T07, T09
- Full design system per template
- Collapsible hints (CSS `<details>`)
- Improved print control and write-in space
- Moderate subject-aware differentiation

**Premium / Studio**
- T04 Interactive Fieldbook and T08 Proof Track
- Interactive diagrams, sliders, live computation
- Maximum diagram density
- Highly polished print profiles with full interactive fallbacks
- Institution branding options (future)
- Advanced customisation

**The honest cost basis:**
Premium costs more to generate because interactive diagrams
require richer SVG with JS event handlers, more model calls
for diagram complexity, and validation of interaction logic.
Basic diagrams are static SVG — genuinely cheaper.
The tier reflects actual cost differences, not artificial scarcity.

---

## 14. Skill-Based Future Architecture

The current system uses template configs as the presentation
control mechanism. That is the right starting point.
The natural evolution is toward composable skills.

**The five-step migration path:**

```
1. Internal template configs         ← build this now
2. Internal presentation modules     ← extract as templates stabilise
3. Internal skill packages           ← extract repeated patterns
4. Admin-level template authoring    ← institution customisation
5. Constrained user-authored skills  ← teacher community layer
```

Do not jump straight to step 5.
Each step earns the next. Prompt spaghetti is what happens
when you go from step 1 to step 5 without the intermediate work.

**What a skill package eventually contains:**
- layout policy
- allowed block organizations
- diagram instructions
- visual density rules
- tone and explanatory guidance
- print behaviour
- QA checks specific to this skill

This turns "prompting" into "productized rendering behaviour."
The teacher community layer (OpenClaw equivalent) then operates
at the skill level — teachers share skills that produced their
best booklets, not raw prompt text.

---

## 15. Implementation Sequence

### Phase 1 — Stabilise foundations

1. Finalise semantic section schema (Pydantic)
2. Define three archetype block orders
3. Build `TemplateConfig` schema with all five layers
4. Define print profile structure
5. Write `@media print` base block (complete, not partial)

### Phase 2 — Build first rendering engine

6. T01 Concept Explorer (already 80% built — formalise into Jinja2)
7. T02 Notebook Calm (simplest, best QA test)
8. T10 Minimal Print-First (validates print pipeline)
9. Jinja2 component library — all 13 block components
10. Template config loader

### Phase 3 — Presentation QA

11. Structural QA checks
12. Visual/contrast checks
13. Print overflow and page-break checks
14. Cognitive load checks
15. Interactive fallback checks

### Phase 4 — Expand templates and gallery

16. T03 Middle School Momentum
17. T05 Science Studio
18. T08 Proof Track
19. T04 Interactive Fieldbook (port from existing interactive book)
20. Template gallery UI with filters

### Phase 5 — Premium and skills

21. Remaining templates (T06, T07, T09)
22. Skill extraction from stable templates
23. Institution-level preset customisation
24. Teacher community configuration sharing

---

## 16. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Too much template freedom | Constrain templates to approved archetype families |
| HTML becomes flashy but pedagogically worse | Require interactions to have defined cognitive benefit |
| Print becomes visibly second-class | Complete `@media print` block on every template, day one |
| Monetisation degrades educational trust | Never gate correctness or completeness — only presentation richness |
| Subject specificity explodes complexity | Shared archetypes with subject-specific token overrides |
| Prompting layer becomes unmanageable | Generation guidance lives in template config, not ad hoc instructions |
| First template is slow to build | Start with T01 — 80% already exists in `calculus_section1_v2.html` |

---

*End of Merged Presentation Architecture v2.0*
*Both source documents superseded by this specification.*
