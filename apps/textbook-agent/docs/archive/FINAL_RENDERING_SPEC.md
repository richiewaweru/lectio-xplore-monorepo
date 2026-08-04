# The Lively Textbook — Final Rendering System Specification
**Plain language. Built from everything we learned.**
**Version:** Final

---

## The One Thing to Understand First

Right now the system generates good content and puts it in a template.
The result looks like a printed document that happened to be opened
in a browser. Nothing moves. Nothing responds. Nothing feels alive.

The goal of this spec is to describe exactly how we make the generated
textbook feel like a real learning tool — something you can navigate,
expand, zoom into, step through, and read on any screen.

The fix is not making the template fancier. The fix is separating
three jobs that are currently all being done by one system:

```
Job 1 — LAYOUT:     decide how to arrange the content on the page
Job 2 — BEHAVIOUR:  decide what the page does when you interact with it
Job 3 — GUARANTEE:  make sure basic interactions work no matter what
```

Currently the LLM is trying to do all three at once, which is why
it copies the template layout without adding any behaviour, and why
it squeezes content into components that do not fit.

---

## The Architecture in Plain English

Think of the system as a theatre.

**The template** is the stage — it decides the visual style, the colour
scheme, the fonts, and the general rules for how things are arranged.

**The behaviour library** is the motion vocabulary — a shared set of
interaction patterns (expand, zoom, step, scroll, tab) that any page
can use regardless of which template it is using.

**The LLM** is the choreographer — it reads the content, understands
what it is, and decides which layout and which behaviours make sense
for that specific content. It works within the stage's rules.

**The universal runtime** is the safety net — it guarantees that
even if the LLM makes poor choices, the page will still have basic
navigation, hints will still toggle, and diagrams will still zoom.

**The QC agent** is the director — it looks at the finished page,
spots bad choices, and sends specific instructions back to fix them.

---

## The Pipeline — Step by Step

```
1. Content is generated
   (CurriculumPlanner → ContentGenerator → DiagramGenerator)
   Output: structured content blocks — hook, definition,
           worked example, practice problems, diagram, etc.

2. Layout is planned
   The LLM reads the content and decides how to arrange it.
   For each block it answers: which template component fits
   this amount of content? If the content is too dense for
   the default component, which alternative should I use?
   Output: a LayoutPlan — a simple record of these decisions.

3. Behaviour is planned
   The LLM reads the content again and decides what should
   be interactive. Some decisions are automatic (practice
   hints always toggle). Some require judgment (should this
   diagram get a zoom button?).
   Output: a BehaviorPlan — a record of which interactions
   apply to which blocks and why.

4. Responsive behaviour is planned
   The LLM decides how the page adapts to different screens.
   Desktop: sidebar visible, two-column layout allowed.
   Tablet: sidebar becomes a pull-out drawer.
   Mobile: single column, sections optionally become tabs.
   Output: a ResponsivePlan.

5. HTML is rendered
   The template engine takes the three plans and produces HTML.
   The LLM writes the content into the HTML structure.
   It does NOT write any JavaScript.
   It marks every interactive element with a data attribute:
   data-behaviour="hint-toggle" or data-behaviour="zoom" etc.

6. Universal baseline is applied
   A small JS file called universal.js runs first, before
   anything else. It adds basic behaviour to the page
   regardless of what the LLM did or did not do:
   — nav links scroll to their sections
   — a reading progress bar appears at the top
   — tables that are too wide get horizontal scroll
   — dense diagrams get a zoom trigger automatically
   — keyboard navigation works throughout
   This guarantees the page is never completely dead.

7. The behaviour runtime activates
   A second JS file called runtime.js reads all the
   data-behaviour attributes and brings them to life:
   — hint-toggle hides hints until clicked
   — step-reveal shows worked example steps one at a time
   — accordion expands and collapses content blocks
   — zoom opens diagrams in a full-screen overlay
   — sticky-sidebar keeps vocabulary terms visible as you scroll
   — section-tabs turns sections into swipeable tabs on mobile

8. QC reviews the rendered page
   The QC agent loads the page in a headless browser,
   scrolls through it, and checks for problems.
   It catches: squeezed content, broken nav links,
   missing zoom on detailed diagrams, contrast failures,
   touch targets that are too small on mobile.
   For fixable problems it applies a patch directly.
   For bigger problems it sends the specific block back
   for regeneration — not the whole section.

9. Delivered to the learner
   The page is live and behaves correctly.
```

---

## The Two JavaScript Files

### universal.js — The Safety Net

Runs on every page, first, unconditionally.
The LLM cannot affect it. Templates cannot disable it.
It is the guarantee that every page has minimum liveliness.

What it does automatically:
- Smooth scroll when a nav link is clicked
- Reading progress bar at the top of the page
- Any table wider than its container gets horizontal scroll
- Any SVG that has text smaller than 10px gets a zoom button
- Keyboard: arrow keys move between sections
- All external links open in a new tab safely

Why this matters: even if everything else goes wrong, the page
still works at a basic level. You can never produce a completely
dead page.

### runtime.js — The Behaviour Engine

Runs after universal.js, reads every `data-behaviour` attribute
on the page, and activates the corresponding interaction.

The LLM's job is to put the right attribute on the right element.
The runtime's job is to make it work. These two jobs never mix.

---

## The Behaviour Vocabulary

Every behaviour has a name. The LLM uses these names.
The runtime implements them. Templates declare which ones
they allow. This vocabulary is shared across all templates.

### DISCLOSURE — showing and hiding content
```
hint-toggle     Practice problem hints, hidden by default
step-reveal     Worked example steps, one at a time
accordion       Any content block that expands/collapses
expand-card     A small summary card that opens to full detail
```

### VISUAL — how content is seen
```
zoom            Figure opens in full-screen overlay on click
highlight-row   Table row highlights on hover for readability
tooltip         Small label appears on hover for a term
compare-toggle  Switch between two versions of the same content
```

### NAVIGATION — moving around the page
```
anchor-nav      Nav links scroll to section anchors
scrollspy       Active nav link updates as you scroll
sticky-sidebar  Vocabulary rail sticks and updates by section
section-tabs    Sections become horizontal tabs
reading-progress  Progress bar at top of page
```

### ASSESSMENT — checking understanding
```
quiz-check      Multiple choice with immediate right/wrong feedback
self-check      Learner marks their own answer as correct/incorrect
toggle-view     Reveal a different representation of the same idea
```

### SUBJECT — domain-specific interactions
```
graph-slider       Slider drives a live mathematical graph update
timeline-scrubber  Scrub through a sequence of historical events
equation-reveal    Derivation steps appear one line at a time
tree-stepper       A tree diagram expands node by node
```

### PREMIUM — higher complexity, selective use
```
pyodide-cell    Runnable Python code in the browser
simulation      Live physics or math simulation with controls
```

---

## The Three Levels of Behaviour Confidence

Not every behaviour decision is equally certain. The system
handles them differently based on confidence.

**Level 1 — Automatic (no LLM decision needed)**

These are applied without any LLM judgment.
If the block type is in the template's preferred list, the
behaviour is applied. Period.

Examples:
- Practice hints → hint-toggle. Always.
- Worked examples → step-reveal. Always.
- Vocab terms → sticky-sidebar. Always.
- Nav links → anchor-nav. Always.

**Level 2 — LLM judgment (within allowed options)**

The LLM decides, but only within what the template allows.
It must write a brief reason for its choice.

Examples:
- Should this motivation diagram get zoom treatment?
  (LLM checks: does it contain fine detail? yes → add zoom)
- Should this overview card be accordion or inline?
  (LLM checks: how much content? → accordion if dense)
- Should mobile use scroll or tabs for this textbook?
  (LLM checks: how many sections? → tabs if 4 or more)

**Level 3 — Safe fallback (when in doubt)**

If a behaviour choice is uncertain or QC rejects it, the system
falls back to a simpler, always-readable static layout.

An accordion that breaks becomes plain expanded content.
A slider that fails becomes a static diagram at its midpoint.
A sticky sidebar that overflows becomes inline vocab terms.

The fallback is never exciting. It is always readable.

---

## Template Capability Declaration

Every template declares what it allows, what it prefers,
and what the fallbacks are. This is a simple JSON block.

```json
{
  "template_id": "concept_explorer_v1",
  "interaction_level": "medium",

  "allowed_behaviours": {
    "hint-toggle":     true,
    "step-reveal":     true,
    "accordion":       true,
    "zoom":            true,
    "sticky-sidebar":  true,
    "anchor-nav":      true,
    "scrollspy":       true,
    "section-tabs":    true,
    "quiz-check":      false,
    "graph-slider":    false,
    "pyodide-cell":    false
  },

  "preferred_behaviours": {
    "practice":         "hint-toggle + accordion",
    "worked_example":   "step-reveal",
    "key_terms":        "sticky-sidebar",
    "dense_diagram":    "zoom"
  },

  "responsive_fallbacks": {
    "sticky-sidebar":   "inline vocab strip",
    "two-column":       "single column stacked",
    "section-tabs":     "long scroll",
    "accordion":        "expanded flat list"
  }
}
```

The `interaction_level` field is a hard ceiling:
- `none` → only universal.js behaviours
- `light` → hint-toggle, tooltip, anchor-nav
- `medium` → accordion, step-reveal, zoom, sticky-sidebar
- `high` → quiz-check, graph-slider, simulation

The LLM cannot assign any behaviour above the template's ceiling.
QC enforces this as a hard rule.

---

## What the LLM Actually Does

The LLM's job in the rendering pipeline is narrow and specific.

**Before writing any HTML, it produces three plans:**

**LayoutPlan** — for each content block:
what component fits this amount of content?
if it overflows, what alternative should I use?

**BehaviorPlan** — for each content block:
which Level 1 behaviours apply automatically?
which Level 2 decisions do I need to make?
what is my reason for each Level 2 choice?

**ResponsivePlan** — for the whole section:
how does the layout adapt at tablet width?
how does it adapt at mobile width?
should mobile use tabs or long scroll?

**Then it writes the HTML with:**
- The right component for each block
- `data-behaviour` attributes on every interactive element
- `id` attributes on every section for navigation anchors
- `data-term` and `data-definition` on vocabulary terms
- `data-zoom="true"` on any diagram with fine detail
- A brief HTML comment at the top recording its layout decisions

**What the LLM never does:**
- Never writes JavaScript
- Never writes inline event handlers
- Never invents behaviour names not in the registry
- Never assigns behaviours the template has not allowed
- Never forces content into a component it does not fit

---

## Layout Decision Rules — When to Override the Default

These are the specific rules the LLM follows when deciding
whether the default component fits the content.

| If content is... | Default component | Override when | Use instead |
|---|---|---|---|
| 3-item comparison | insight-strip | Any item > 2 lines | comparison-grid |
| 3-item comparison | insight-strip | Items have sub-bullets | accordion |
| 4+ dated events | prose | Always | timeline-flow |
| 3+ step process | prose | Always | stepped-flow |
| Definition > 80 words | definition-card | Always | definition-card with plain/formal toggle |
| Worked example > 3 steps | flat steps | Always | step-reveal |
| Practice problems | flat list | Always | stacked cards with hint-toggle |
| Vocabulary term | inline text | First use of any defined term | key-term span with data attributes |
| Diagram with small text | inline | If text < 10px at normal zoom | add data-zoom="true" |
| Two-column where image taller than text | two-column | Always | single column, image below |

---

## The QC Agent — What It Checks and How

The QC agent loads the rendered page in a headless browser.
It scrolls through at three screen widths: desktop, tablet, mobile.

It catches problems in four categories:

**Structural problems (code-level checks)**
- Nav links with no matching anchor target
- Empty blocks or placeholder text
- Behaviour attributes not in the registry
- Missing step numbers on step-reveal blocks
- Sidebar with no vocabulary terms

**Layout problems (measurements)**
- Any element wider than its container
- insight-strip cells containing more than ~50 words
- Accordion groups with more than 6 items
- Sticky sidebar taller than the viewport without internal scroll

**Visual problems (rendered at each breakpoint)**
- Diagrams too small to read their labels
- Cards that have collapsed to an unreadable width
- Two-column layout that breaks below tablet breakpoint
- Touch targets smaller than 44px on mobile view

**Behaviour problems (interaction testing)**
- Hint-toggle not hiding hints on load
- Step-reveal not progressive (all steps visible)
- Section tabs not matching section count
- Zoom overlay not appearing on click

**When QC finds a problem:**

If it is a simple CSS or attribute fix → apply the patch directly, no rerender.

If the block needs to be regenerated → send only that block back
with the specific issue described. Not the whole section. Not the
whole page. Just the broken block.

```
Example QC issue report:

Location:    section-01 > core-idea > motivation-diagram
Problem:     insight-strip cells contain 4 bullet points each.
             Cells are overflowing and text is clipped at tablet width.
Severity:    blocking
Fix:         Replace insight-strip with accordion-group.
             Three items, each accordion item open by default.
Confidence:  needs_rerender
Action:      Send block back to LLM with this instruction.
```

---

## The Two Display Modes

### Long Scroll (default)

All sections on one page, stacked vertically.
Sticky nav tracks which section is in view.
Reading progress bar shows how far through the document you are.
Best for: desktop, focused reading sessions.

### Section Tabs

Each section is a separate tab.
A tab bar at the top lets you switch between sections.
On mobile: swipe left or right to move between sections.
On desktop: click tabs or use left/right arrow keys.
Best for: mobile, Chromebook, classroom tablet, short sessions.

The teacher selects the display mode when generating the textbook.
The content is identical — only the navigation wrapper changes.

---

## Responsive Behaviour — Three Screen Widths

**Desktop (above 900px)**
- Two-column layout available (content + sidebar)
- Sidebar sticky, full height
- Full nav bar with all section links
- All behaviours active

**Tablet (600px to 900px)**
- Single column
- Sidebar becomes a pull-out drawer (tap to open)
- Nav bar compact, shows section numbers not full titles
- Accordions collapse by default to reduce scroll

**Mobile (below 600px)**
- Single column, larger font size
- Sidebar becomes inline vocab strip at section end
- Nav collapses to hamburger or section counter
- Section tabs mode available (teacher-selected)
- All touch targets minimum 44px
- Swipe left/right on section tabs

**Classroom display (above 1400px)**
- Content column widens to 960px
- Font size increases for projector viewing
- Diagrams scale up proportionally

---

## Fixing the History Textbook — Before and After

These are the specific failures in the rendered history PDF
and exactly what the new system does to each one.

**The motivation diagram (Economic / Religious / Political)**

Was: three-column insight-strip with 4 bullets per column,
     text clipped, nearly unreadable at normal size.

Now: LLM detects 3 × 4 items = 12 data points, insight-strip
     capacity = 3 × 2 lines = 6 max. Overflow detected.
     LayoutPlan records: use accordion-group instead.
     BehaviorPlan: accordion, open by default, zoom available.
     QC would have caught this even if LLM missed it.
     Result: three readable cards, each expandable.

**Key terms appearing as flat text at the bottom**

Was: KEY TERM blocks as plain text divs at the end of each section,
     disconnected from the reading flow, duplicated.

Now: Every defined term gets `data-term` and `data-definition`
     attributes on its first use. The sticky sidebar runtime
     builds a vocabulary rail automatically and updates it as
     the reader scrolls into each section. Level 1 — automatic.

**No navigation between sections**

Was: No links, no nav, no way to jump between sections.

Now: anchor-nav is Level 1 — always applied. The assembler
     adds section IDs and the nav bar with section links.
     universal.js adds smooth scroll. scrollspy updates
     the active link as the reader scrolls. Always present.

**Practice hints always visible**

Was: All hints open on the page at all times.

Now: hint-toggle is Level 1 for practice blocks — always applied.
     Hints are hidden by default and reveal on click.
     On print: always visible (print CSS overrides the hidden state).

**Worked example as a flat numbered list**

Was: All five steps visible at once, nothing to engage with.

Now: step-reveal is Level 1 for worked examples — always applied.
     Step 1 visible on load. "Show next step →" button reveals
     each subsequent step. Learner works through the reasoning.

**No progress indicator, no sense of place in the document**

Was: One long scroll with no orientation.

Now: reading-progress bar always added by universal.js.
     Scrollspy keeps the active section highlighted in the nav.
     Optional section-tabs mode for mobile.

---

## Summary — The Complete System

```
WHAT EACH PART DOES

Template            Visual identity, layout rules, behaviour permissions,
                    interaction level ceiling, responsive fallbacks.
                    The stage.

Behaviour library   A shared vocabulary of named interactions available
                    to all templates. Not owned by any one template.
                    The motion vocabulary.

LLM                 Reads content. Produces LayoutPlan, BehaviorPlan,
                    ResponsivePlan. Writes HTML with data attributes.
                    Never writes JavaScript. Works within template rules.
                    The choreographer.

universal.js        Runs first, unconditionally. Guarantees minimum
                    liveliness regardless of all other choices.
                    The safety net.

runtime.js          Reads data-behaviour attributes, activates all
                    named interactions. One file, all templates.
                    The behaviour engine.

QC agent            Renders the page, scrolls it, checks it at three
                    screen widths. Patches simple problems. Sends
                    specific blocks back for regeneration when needed.
                    The director.
```

The page that comes out of this system is not a static document.
It navigates. It breathes. It responds. It reads well on a phone
and looks serious on a projector. And when you print it, it produces
a clean, properly formatted page with all hints visible and all
interactive elements replaced with their static equivalents.

That is a living learning artifact.

---

*End of Final Rendering System Specification*
