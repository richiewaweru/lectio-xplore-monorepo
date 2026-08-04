# FINDINGS — Page-object experiment

Package: `@lectio/page@0.1.0-experimental.0`  
Repository: `lectio-pageobject` (`main`)

## Did ten objects suffice?

Yes for the photosynthesis reference rebuild. All teaching moves in the three hand-authored pages mapped cleanly onto the ten objects. No eleventh object was required.

## Table absorption

`table` absorbed the comparison equation cleanly with `presentation: "comparison"`. Timeline was not exercised in this fixture; still the likeliest resist case for later lessons.

## Heading

Heading is structural and intent-free. It binds to the following substantive block. Compatibility checks return false for `heading`.

## Page counts (measured)

| Artifact | Pages |
| --- | --- |
| Reference booklet `grade7_photosynthesis_3_lesson_booklet.pdf` | **10** |
| Fixture teacher PDF (`pnpm pdf:fixture`, bg on/off) | **6** (equal for both) |
| Fixture student PDF | **5** (no answer-key page) |

Teacher PDFs are shorter than the hand layout reference (cover + contents + three sections + answer-key page break). Counts come from `/Type /Page` markers in the PDF binary, not visual estimate.

## PDF gate (executed)

`pnpm pdf:fixture` builds the app, previews `/fixtures/photosynthesis-ref?print=1`, and drives Playwright against real `LectioDocumentView`:

- Teacher edition: `out/photosynthesis-ref-bg-on.pdf`, `out/photosynthesis-ref-bg-off.pdf` — same page count; DOM includes all ten objects including `.lectio-answer-key`
- Student edition: `out/photosynthesis-ref-student.pdf` — answer-key absent
- Fail-fast if Chromium missing; `postinstall` runs `playwright install chromium`
- Print route has no `.lectio-review-chrome`

## Pack notes

- FIX 1 `front_matter` applied; v1.1 `base-print.css` used
- Catalogue v1.1.0: capacity + earn/reject on 8 objects; `choose_when`/`not_when` on 11 co-occurring intents; `answer-key.selectable: false`
- Docs pack no longer duplicates intent/object catalogues — canonical files are repo-root `contracts/`
- Artifact C planner comparison and Artifact F backend rewiring were not run
- Brief PATCH 7 full matrix deferred per PATCH v1.3

## Verification meters (target: zero)

| Meter | Status |
| --- | --- |
| Unsafe `as unknown as` in BlockView | zero |
| Generic `Record<string, unknown>` block content | zero |
| String-template PDF rendering | zero |
| `screen.css` imported by LectioDocumentView | zero |
| Credential literals in `.npmrc` | zero |
| Pedagogical boxes outside aside | zero |
