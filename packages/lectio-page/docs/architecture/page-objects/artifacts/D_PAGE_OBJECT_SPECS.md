# D. Ten Page-Object Specifications

## Governing geometry

```text
A4 page, 18mm outer page margin

┌──────────────────────────────────────────┐
│ main text: 112mm │ 6mm gap │ margin 56mm│
│ ~65–75 chars     │         │ asides      │
│ prose/tables/Qs  │         │ captions    │
│ figures may span main + gap + margin      │
└──────────────────────────────────────────┘
```

The margin implementation uses the proven float recipe:

```css
.lectio-page-flow { padding-right: 62mm; }

.lectio-aside--margin {
  float: right;
  clear: right;
  width: 56mm;
  margin-right: -62mm;
}
```

CSS grid is rejected for page flow because margin items claim grid rows and create dead space during fragmentation.

## Global rules

- Root carries `lang`.
- Baseline rhythm uses 15pt as the base line.
- Main measure is 112mm and approximately 68 characters.
- Four type sizes only: body, caption, subheading, heading.
- One accent color maximum.
- Meaning must survive black-and-white photocopy.
- Rules and whitespace are preferred to filled surfaces.
- Only `aside` may have a border or background.
- Screen review decorations wrap page objects and are excluded from the print subtree.
- No object prints its internal name.


## Heading

**Content model**

```json
{
  "level": "1|2|3",
  "text": "string",
  "number": "string|null"
}
```

**Placement:** main, spanning

**Page behavior:** Must be bound with the first following block in one break-inside:avoid wrapper. Never render alone.

**Emphasis mechanism:** Type size, weight, rule, and spacing only. No box.

**Screen decoration:** Review wrapper may show selection and hierarchy controls outside the print subtree.

**Failure cases to test**
- heading at page bottom
- heading followed by tall figure
- heading as final section block
- two heading levels in succession

## Prose

**Content model**

```json
{
  "paragraphs": "RichParagraph[]"
}
```

**Placement:** main

**Page behavior:** Splits freely with widows/orphans. Paragraphs may split.

**Emphasis mechanism:** Inline weight, italic, small caps, and whitespace. No background or border.

**Screen decoration:** Optional hover boundary and edit handle outside print subtree.

**Failure cases to test**
- very long paragraph
- inline math near page break
- unbreakable URL/term
- language missing on root

## List

**Content model**

```json
{
  "style": "ordered|unordered|steps|glossary",
  "lead_in": "RichText|null",
  "items": "ListItem[]"
}
```

**Placement:** main, margin

**Page behavior:** List may split between items; individual item avoids splitting when practical.

**Emphasis mechanism:** Markers, hanging indent, weight, and spacing. No box.

**Screen decoration:** Editing controls wrap list; no student-visible object label.

**Failure cases to test**
- single long item
- nested list
- numbered procedure across pages
- margin glossary list

## Table

**Content model**

```json
{
  "columns": "TableColumn[]",
  "rows": "TableRow[]",
  "caption": "string|null",
  "presentation": "standard|comparison|timeline"
}
```

**Placement:** main, spanning

**Page behavior:** May split across pages. thead repeats. Rows avoid splitting.

**Emphasis mechanism:** Rules, alignment, weight, and sparse header tint only when photocopy-safe. No enclosing box.

**Screen decoration:** Column resize/edit affordances outside print subtree.

**Failure cases to test**
- header repetition
- wide cells
- row taller than remaining space
- timeline presentation pressure

## Figure

**Content model**

```json
{
  "asset": "FigureAsset",
  "caption": "string|null",
  "alt_text": "string",
  "width": "main|span"
}
```

**Placement:** main, spanning

**Page behavior:** Figure and caption are atomic. May move to next page.

**Emphasis mechanism:** Scale, whitespace, caption typography, and optional hairline around the plate only—not a card.

**Screen decoration:** Asset status and replacement controls outside print subtree.

**Failure cases to test**
- caption orphaning
- oversized SVG
- missing asset
- full-span figure after heading

## Aside

**Content model**

```json
{
  "label": "string|null",
  "body": "RichText"
}
```

**Placement:** margin, main

**Page behavior:** Atomic. Margin placement uses float, clear:right, and negative margin. Move cleanly if it does not fit.

**Emphasis mechanism:** The only object allowed a border or background. Default is a single vertical rule with restrained label.

**Screen decoration:** Can receive intent badge in teacher review only; badge excluded from print.

**Failure cases to test**
- two adjacent asides
- tall aside near page break
- aside longer than margin capacity
- photocopy legibility

## Worked Example

**Content model**

```json
{
  "title": "string|null",
  "problem": "RichText",
  "steps": "WorkedStep[]",
  "answer": "RichText",
  "check": "RichText|null"
}
```

**Placement:** main, spanning

**Page behavior:** May split between steps. A step avoids internal split where practical. Final step and answer stay together.

**Emphasis mechanism:** Numbered steps, hanging labels, indentation, and rules. No enclosing box.

**Screen decoration:** Step editing and collapse controls may exist only in review shell.

**Failure cases to test**
- eight-step example
- long formula
- answer separated from final step
- step with figure

## Questions

**Content model**

```json
{
  "items": "QuestionItem[]",
  "instructions": "RichText|null"
}
```

**Placement:** main, spanning

**Page behavior:** Split between questions, never inside a question. Prompt stays with minimum answer space.

**Emphasis mechanism:** Hanging numbers, marks aligned to edge, ruled answer space. No cards.

**Screen decoration:** Teacher may inspect answer metadata in adjacent review panel.

**Failure cases to test**
- prompt plus insufficient answer space
- marks alignment
- long multi-part question
- question at page bottom

## Choices

**Content model**

```json
{
  "stem": "RichText",
  "options": "ChoiceOption[]",
  "marks": "number|null"
}
```

**Placement:** main

**Page behavior:** Atomic when it fits; otherwise keep stem with at least two options and split only between options.

**Emphasis mechanism:** Letters A/B/C/D, hanging indent, whitespace. Never radio controls.

**Screen decoration:** Interactive selection may appear in review mode but print renderer emits letters only.

**Failure cases to test**
- long options
- split options
- more than four choices
- no radio-circle leakage

## Answer Key

**Content model**

```json
{
  "groups": "AnswerGroup[]"
}
```

**Placement:** main, spanning

**Page behavior:** Split between entries. Entry keeps question reference with first answer line.

**Emphasis mechanism:** Heading hierarchy, compact typography, rules. No card.

**Screen decoration:** Teacher-only visibility control outside document content.

**Failure cases to test**
- teacher-only suppression
- long rubric
- alternative answers
- question ID mismatch

## Heading binding implementation

Chromium's `break-after: avoid` protects only the immediately following element. It does not safely bind a heading through a short lead paragraph to a figure.

The document renderer therefore groups each heading with the first following block:

```svelte
<HeadingBinding>
  <HeadingView block={heading} />
  <BlockView block={firstFollowingBlock} />
</HeadingBinding>
```

```css
.lectio-heading-binding {
  break-inside: avoid;
}
```

The remaining blocks render normally after the binding wrapper.

Normalization rejects:

- a final heading with no following block;
- two headings with no substantive block between them, unless explicitly representing nested hierarchy and bound to one following block.

## Screen review architecture

```text
ReviewFrame (selection, issue count, controls)
└── PrintObject (clean semantic markup)
```

The PDF route renders only `PrintObject`.

The review frame may show:

- object and intent in a side inspector;
- drag handle;
- QC markers;
- comment count;
- generation provenance;
- edit affordance.

None of these are children of the print document node.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** B and E
