# Source Manifest

## Uploaded references included in this pack

- `margin-test-2.html` — working Chromium geometry recipe.
- `margin-test-2.pdf` — proof of float margin, table header repeat, figure atomicity, widows/orphans, and hanging numbers.
- `margin-test.pdf` — earlier comparison render.
- `Photosynthesis_Booklet.docx` — target content vocabulary and restrained booklet structure.
- `grade7_photosynthesis_3_lesson_booklet.pdf` — target booklet furniture, page numbers, practice and answer key.
- `Lessons · Lectio.pdf` — concrete current defects: app chrome, labels, cards, repeated headings, dead space, controls and placeholders.
- `0b878c0f-...-student.pdf` — closest current student output, useful for preserving working cover/contents/page-number furniture.
- `0b878c0f-...-teacher.pdf` — corresponding teacher edition.
- `Pasted markdown.md` — full architecture prompt and constraints supplied by the founder.

## Repository references inspected

### Lectio — branch `xplore`

- `src/lib/schema/types.ts`
  - current wide component content vocabulary;
  - screen behavior modes mixed into content contracts;
  - evidence for replacement rather than extension.

Key additional paths specified for implementation review:

- `src/lib/teacher/document.ts`
- `src/lib/styles/print-theme.css`
- `src/lib/schema/component-meta.ts`
- one template config such as `src/lib/templates/visual-led/config.ts`

### Textbook generator — branch `xplore`

Inspected:

- `backend/src/planning/models.py`
  - path, lesson, knowledge type, learner group and scheduling concepts are independent of component rendering.
- `backend/src/planning/shapes.py`
  - skeleton selection and teacher-approved shape deviations can be retained.
- `backend/src/v3_execution/models.py`
  - current `GeneratedComponentBlock`, `WriterSectionComponent`, `component_cards`, `component_id`, `section_field`, and position.
- `frontend/src/lib/studio/v3-pack-to-lectio-document.ts`
  - current forced normalization into `SectionContent` and legacy `GenerationDocument`.

Key additional paths specified for implementation review:

- `backend/src/generation/v3_studio/prompts.py`
- `backend/src/v3_execution/prompts/section_writer.py`
- `backend/src/generation/v3_studio/generation_writer.py`

## Evidence used in decisions

1. The margin HTML establishes 112mm main measure plus 56mm float margin.
2. The PDF confirms Chromium survives the recipe.
3. The current Lectio PDF visibly shows component labels, cards, controls, QC counts, duplicated titles and dead space.
4. The Grade 7 booklet demonstrates cover, page furniture, readable practice pages and answer-key design.
5. The current student output proves some booklet furniture already works and should not be casually discarded.
6. The `xplore` backend shows that the higher-level planning architecture can survive the resource-contract change.
