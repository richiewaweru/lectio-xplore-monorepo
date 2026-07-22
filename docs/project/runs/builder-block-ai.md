# Builder Block-Level AI Runbook

## Automated fixture

The fixed regression state is `frontend/src/lib/builder/fixtures/block-ai-regression.json`.
It contains empty and populated text blocks, a repairable practice flag, an advisory-only
flag, and a flagged diagram. Backend planning/work-order tests continue to use the fixed
`gen_5aed3804` fixtures.

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
