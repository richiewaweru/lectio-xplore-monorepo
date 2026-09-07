# Component and Template Harmonisation Handoff

**Date:** 2026-03-27
**PR:** #1 — `feat(templates): harmonise component vocabulary and template contracts`

---

## Scope

Component vocabulary expansion + template contract restructuring. Merged to master. All quality gates passed.

---

## What Changed

### 7 New Components

All stable. Each adds a `SectionContent` field, registry entry, Svelte component, and type export.

| Component | `SectionContent` field | Content type |
|---|---|---|
| `CalloutBlock` | `callout` | `CalloutBlockContent` (variants: `info`, `tip`, `warning`, `exam-tip`, `remember`) |
| `SummaryBlock` | `summary` | `SummaryBlockContent` (items array + closing) |
| `SectionDivider` | `divider` | `SectionDividerContent` (label) |
| `KeyFact` | `key_fact` | `KeyFactContent` (fact + context + source) |
| `StudentTextbox` | `student_textbox` | `StudentTextboxContent` (prompt + lines) |
| `ShortAnswerQuestion` | `short_answer` | `ShortAnswerContent` (question + marks + mark_scheme) |
| `FillInTheBlank` | `fill_in_blank` | `FillInBlankContent` (segments + word_bank) |

Registry groups: CalloutBlock, SummaryBlock, SectionDivider → Group 1 (Foundation); KeyFact → Group 2; StudentTextbox, ShortAnswerQuestion, FillInTheBlank → Group 4 (Assessment).

### 7 Template Renames

| Old ID / folder | New ID / folder |
|---|---|
| `figure-first` | `visual-led` |
| `focus-flow` | `low-load` |
| `guided-concept-compact` | `concept-compact` |
| `diagram-led-lesson` | `diagram-led` |
| `distinction-grid` | `classification` |
| `process-trainer` | `procedure` |
| `timeline-narrative` | `timeline` |

Renames used `git mv` to preserve history. All internal imports, export variables, preview IDs, and test assertions updated.

### New 13th Template: `open-canvas`

Location: `src/lib/templates/open-canvas/`

A free-compose fallback template with uniform `signal_affinity` (0.5 across all axes) and all components in `available_components`. Intended for content that doesn't fit a structured template. All 5 base presets allowed.

### TemplateContract Restructuring

The `TemplateContract` interface in `src/lib/template-types.ts` was rewritten:

**Removed:**
- `lessonFlow: string[]`
- `requiredComponents: string[]`
- `optionalComponents: string[]`

**Added:**
- `always_present: string[]` — components that must appear in every section (replaces `requiredComponents`)
- `available_components: string[]` — optional components the template supports (replaces `optionalComponents`)
- `component_budget: Partial<Record<string, number>>` — lesson-level caps per component type
- `max_per_section: Partial<Record<string, number>>` — per-section caps (default 1 when not specified)
- `signal_affinity` — scoring map (0.0–1.0) across `topic_type`, `learning_outcome`, `class_style`, `format`
- `section_role_defaults: Partial<Record<SectionRole, string[]>>` — default components per role
- `SectionRole` type: `'intro' | 'explain' | 'practice' | 'summary' | 'process' | 'compare' | 'timeline' | 'visual' | 'discover'`

### Other Type Changes

- `SectionHeaderContent.objective?: string` → `objectives?: string[]`
- `ExplanationCallout.type`: added `'warning'` and `'exam-tip'` to the union
- `QuizContent`: added `quiz_type?: 'multiple-choice' | 'true-false'`
- `PracticeProblem`: added `problem_type?: 'structured' | 'open'`

### Export Contracts

Contracts regenerated at `agents/contracts/`. Now 13 template JSONs. Old JSON files for renamed templates removed. Shape change mirrors TemplateContract above — no `lesson_flow`, `required_components`, or `optional_components` fields.

---

## Python Mirror (Pending — separate repo)

`backend/src/pipeline/types/section_content.py` needs these changes to stay in sync:

1. `SectionHeaderContent`: rename `objective: Optional[str]` → `objectives: Optional[list[str]] = None`
2. `ExplanationCallout.type` Literal: add `'warning'`, `'exam-tip'`
3. `QuizContent`: add `quiz_type: Optional[Literal['multiple-choice', 'true-false']] = None`
4. `PracticeProblem`: add `problem_type: Optional[Literal['structured', 'open']] = 'structured'`
5. New model `CalloutBlockContent` with `variant: Literal['info','tip','warning','exam-tip','remember']`, `heading: Optional[str]`, `body: str`
6. New models `SummaryItem` (text, bold) and `SummaryBlockContent` (title, items, closing)
7. New model `SectionDividerContent` with `label: Optional[str]`
8. New model `KeyFactContent` with `fact: str`, `context: Optional[str]`, `source: Optional[str]`
9. New model `StudentTextboxContent` with `prompt: str`, `lines: int`
10. New model `ShortAnswerContent` with `question: str`, `marks: Optional[int]`, `mark_scheme: Optional[list[str]]`
11. New models `FillInBlankSegment` (text, is_blank, answer) and `FillInBlankContent` (segments, word_bank)
12. Add all 7 new fields on `SectionContent` as `Optional[X] = None`: `callout`, `summary`, `divider`, `key_fact`, `student_textbox`, `short_answer`, `fill_in_blank`

---

## Validation

- `npm run check` — 0 errors, 0 warnings
- `npm run build` — clean
- `npm run test` — 36/36 pass (4 test files)
- `npm run export-contracts` — 13 contracts exported

---

## Where To Start Next Time

- Adding a component: `src/lib/registry.ts` (entry) + `src/lib/types.ts` (content type) + `src/lib/components/lectio/` (Svelte file) + `src/lib/components/lectio/index.ts` + `src/lib/index.ts`
- Changing a template contract: `src/lib/templates/{id}/config.ts`, then `npm run export-contracts`
- Template contract interface: `src/lib/template-types.ts`
- All 13 templates: `src/lib/template-registry.ts`
