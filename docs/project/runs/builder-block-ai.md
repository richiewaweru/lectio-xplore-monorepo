# Builder Block-Level AI Runbook

## AI assistance suite baseline — 2026-07-24

Phase 0 was completed before implementation.

### Reproduction environment

- The repository frontend and backend were started on isolated local ports because
  ports 5173, 8000, and 8001 belonged to another project.
- The local browser session was signed out. A signed-in production Builder lesson
  was therefore used for the live visual-quality baseline.
- The sampled production generations did not contain a `visual_mismatch` issue with
  `repair_target_id: "questions:..."`. The deterministic review fixture and the
  checked-in Builder regression fixture were used for that path, as allowed by the
  handoff.

### Captured issue payloads

Deterministic `visual_mismatch` payload:

```json
{
  "issue_id": "7f2334ab-10cf-4515-8871-bd6af86fa44a",
  "severity": "minor",
  "category": "visual_mismatch",
  "message": "Question references a visual without a planned diagram: 'Look at' at practice.practice.problems[0].question.",
  "blueprint_ref": "question_plan:practice",
  "generated_ref": "practice.practice.problems[0].question",
  "suggested_repair_executor": "question_writer",
  "repair_target_id": "questions:practice"
}
```

Live-equivalent `visual_quality_flagged` payload:

```json
{
  "issue_id": "d3b599ba-97f9-4456-a3b4-79595f2ba628",
  "severity": "minor",
  "category": "visual_quality_flagged",
  "message": "image flagged by quality review: Labels are incomplete",
  "blueprint_ref": null,
  "generated_ref": "practice",
  "suggested_repair_executor": "visual_executor",
  "repair_target_id": "visual:vis-phase0"
}
```

### Current UI behavior

- A production `visual_quality_flagged` nudge was captured in section
  “Chlorophyll: the light catcher.” The row showed `Swap image` and `Dismiss`.
  Clicking `Swap image` selected the diagram and opened manual media editing; no
  regeneration hint or AI action opened.
- The current regression fixture routes `questions:{sid}` to the first
  question-capable block. Clicking `Fix with AI` opens `AiBlockAssist` in custom
  mode with `Fix this issue in the block: <issue.message>`. This is the guessing
  behavior being replaced.
- The production nudge row and the resulting manual diagram editor were captured
  in the browser-run evidence for this task.

## Automated fixture

The fixed regression state is `frontend/src/lib/builder/fixtures/block-ai-regression.json`.
It contains empty and populated text blocks, a repairable practice flag, an advisory-only
flag, and a flagged diagram. Backend planning/work-order tests continue to use the fixed
`gen_5aed3804` fixtures.

## Automated evidence — 2026-07-24

- `npm run check`: passed with 0 errors and 0 warnings.
- `npm run build`: passed; only the existing Rollup annotation and chunk-size warnings were emitted.
- `npm test`: 59 test files passed, 243 tests passed.
- Builder AI targeted coverage: 13 tests passed across payload, fixture,
  canvas repair, and visual regeneration behavior.
- Backend validation: Ruff passed and 409 tests passed.
- Tooling validation: 8 tests passed.
- Architecture guard: no violations found.
- Real-provider acceptance was not performed in this workspace, so every live
  checklist item below remains intentionally unchecked.

## Real-provider acceptance

Prerequisites: configure the backend provider/model environment, `PUBLIC_API_URL`, image
storage, and a signed-in teacher account. Open a generated lesson in Builder so its saved
lesson has a `source_generation_id`.

- [ ] Select an empty text block and generate with FAST; content appears and one undo restores it.
- [ ] Improve a populated text block with Higher quality enabled; STANDARD is used and hidden fields remain unchanged.
- [ ] Run Custom with an edited teacher instruction; ordinary custom does not send existing content.
- [ ] Click Fix with AI on a practice issue; the issue message is prefilled, editable, and current content is supplied.
- [ ] Generate the repair; merged content appears and the issue clears only after success.
- [ ] Confirm section/document advisory issues have no Fix with AI button.
- [ ] Regenerate a flagged visual with a correction; the returned URL reaches the block and the issue remains resolved after refresh.
- [ ] Confirm image-block and video-embed cards have no sparkle action.

Record provider/model IDs, lesson/generation IDs, and observed failures in `PROGRESS.md`.
