# Patch — Lectio Page-Object Architecture Pack v1 → v1.1

Four corrections found in review. None is architectural: one missing concept and three implementation slips. Apply before handing to any implementation agent.

Replacement file: `contracts/base-print.css` (rewritten in full).

---

## FIX 1 — Front matter has no home (missing concept)

**Problem.** The v2 document schema is `{ metadata, sections[], answer_key }`. There is nowhere for a cover page, table of contents, or running head.

The current V3 booklet path already produces all three — the student PDF carries School / Teacher / Date / Student Name and a contents list. Shipping v2 as specified is a **regression** against working output.

**Decision.** Front matter is *renderer furniture*, not an authored page object. It is derived from `metadata` plus section titles. It does not become an eleventh object, because nothing generates it and nothing edits it.

**Schema change** — add to `lectio-document-v2.schema.json` top level:

```jsonc
"front_matter": {
  "type": "object",
  "properties": {
    "cover":    { "type": "boolean", "default": true },
    "contents": { "type": "boolean", "default": true },
    "running_head": { "type": ["string", "null"] },
    "fields": {
      "type": "array",
      "description": "Blank labelled lines on the cover, e.g. Student Name, Date.",
      "items": { "type": "string" }
    }
  }
}
```

**CSS added:** `.lectio-cover`, `.lectio-cover-title`, `.lectio-cover-subtitle`, `.lectio-cover-fields`, `.lectio-cover-field`, `.lectio-contents`, `.lectio-contents-entry`.

**Note on running heads and page numbers.** Chromium has no reliable CSS margin boxes. These come from Playwright's `display_header_footer` + `headerTemplate` / `footerTemplate`. Artifact E already says this; the point here is that `front_matter.running_head` is the field the exporter reads. Body bottom margin and footer template must be tested together for collision — the current V3 output has page numbers colliding with body text.

---

## FIX 2 — Answer lines vanish on browser print

**Problem.** `.lectio-answer-lines` used `repeating-linear-gradient`, which is a background image.

The Playwright export passes `print_background=True`, so PDFs were fine. But the builder's `printDocument()` calls `window.print()`, and **Chrome's print dialog defaults "Background graphics" to OFF.**

Result: a teacher pressing Ctrl+P silently gets questions with no writing space — in a booklet whose purpose is ruled answer room.

**Fix.** Borders, not backgrounds. The renderer emits one `.lectio-answer-line` element per required line.

```css
.lectio-answer-lines { margin-top: 7.5pt; }
.lectio-answer-line  { height: 16pt; border-bottom: .5pt solid #999; }
```

**Verified:** rendered through Chromium 141 with `print_background=False`. Lines present.

**General rule to adopt:** nothing load-bearing may depend on background rendering. Applies to any future tint, rule, or fill.

---

## FIX 3 — Hardcoded millimetres break the presets

**Problem.** The gutter was a variable in one place and a literal in another:

```css
.lectio-document     { --gutter: 62mm }
.lectio-aside        { margin: 0 -62mm 15pt 6mm }   /* literal */
.lectio-figure--span { width: 174mm }                /* literal */
```

Change `--gutter` in a `compact` preset and asides land in the middle of the text column. `174mm` is A4 minus 18mm margins — correct today, silently wrong the moment `@page` changes.

Artifact E promises typography and density presets, so this bites on the first preset that isn't `standard`.

**Fix.** All geometry derives from three roots:

```css
--page-width: 210mm;
--page-margin: 18mm;
--content: calc(var(--page-width) - (2 * var(--page-margin)));
--gutter: 62mm;
--main: calc(var(--content) - var(--gutter));
--aside-gap: 6mm;
--aside-width: calc(var(--gutter) - var(--aside-gap));
```

`.lectio-aside` uses `calc(-1 * var(--gutter))`. Span modifiers use `var(--content)`.

**Invariant for review:** no rule below the geometry block may contain a millimetre value that depends on page size, gutter, or margin. Small fixed values (padding, hanging indents) are fine.

---

## FIX 4 — Table can span but had no span modifier

**Problem.** The object catalogue gives Table `placement: ['main', 'spanning']`. The CSS only defined `width: var(--main)`. Figure got a `--span` modifier; Table did not.

A wide comparison table spanning the full measure is exactly the case that motivated the two-track layout.

**Fix.**

```css
.lectio-table--span { width: var(--content); }
```

---

## Verification performed

Rendered through headless Chromium 141 via Playwright (same engine as the PDF exporter), at A4, with `print_background=False` to simulate the worst case.

Confirmed: cover breaks to its own page; heading binding holds; aside floats into the margin at the calc-derived offset; table header styling intact; question marks align right; **answer lines render with backgrounds disabled.**
