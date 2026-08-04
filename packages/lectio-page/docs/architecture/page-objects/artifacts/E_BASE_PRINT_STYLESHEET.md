# E. Base Print Stylesheet

The normative implementation is `contracts/base-print.css`.

## Design intent

The stylesheet states positive document rules only:

- A4 geometry;
- body type;
- baseline rhythm;
- correct measure;
- widows and orphans;
- hyphenation;
- float-based scholar's margin;
- heading binding;
- table-header repetition;
- figure-caption atomicity;
- hanging question and choice markers;
- answer lines;
- answer-key entry binding.

It contains:

- no `!important`;
- no old component selectors;
- no card stripping;
- no hidden builder controls;
- no palette-specific rules;
- no screen behavior;
- no print-mode branches.

## Required host behavior

The rendered root must provide:

```html
<html lang="en">
```

or another correct language code. Without `lang`, `hyphens:auto` silently does nothing.

The Playwright PDF invocation remains responsible for:

- `print_background`;
- `prefer_css_page_size`;
- page-number/footer template;
- teacher/student edition selection.

Page geometry itself belongs to Lectio via `@page`.

## Page-number integration

Chromium does not provide reliable CSS margin boxes. The PDF exporter should continue using Playwright header/footer templates.

The body bottom margin and footer template must be tested together to prevent collision.

## Presets

Only typography/density presets are allowed:

```ts
type PrintPreset = 'generous' | 'standard' | 'compact';
```

They may vary:

- body size;
- line height;
- heading size;
- answer-space defaults;
- table density.

They may not create different color systems or surface styles.

## Growth rule

The base stylesheet is expected to remain under roughly 60 formatted lines. Minified line count is irrelevant; track rule count and selector count.

Any new rule must answer:

1. Which page-object behavior does it implement?
2. Why is it not expressible in the object markup?
3. Is it a positive document rule?
4. Does it apply to more than one fixture?

A rule that exists to undo screen decoration is rejected.

**DOCUMENT VERSION:** 1.0  
**DEPENDS ON:** margin-test reference and D
