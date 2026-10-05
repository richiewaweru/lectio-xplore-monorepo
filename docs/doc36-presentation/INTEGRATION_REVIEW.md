# Lead integration review

Integration remains on hold until G0–G4 pass. This records reviewed conflicts and edge cases; it does not authorize skipping gates.

## A and D

Expect conflicts in `frontend/src/lib/learn/interactions/InteractionShell.svelte`, `frontend/src/lib/learn/document/DocumentCanvas.svelte`, and `frontend/src/lib/learn/document/renderers/InteractionNodeRenderer.svelte`.

Keep A's accepted markup, block structure, typography and styles. Choice options remain native buttons with `aria-pressed` in an accessible group; do not restore D's Phase 0 radio-role markup. Transplant D's role-aware prompt selection, saved prediction state, suppression of graded server feedback and submit behaviour. Keep one running question counter and one task header. Repeat meaningful interaction and keyboard checks after conflict resolution.

Prediction runtime uses the existing `pending-review` representation with zero earned/possible scores and submitted completion. Predictions may count as attempted/selected work but do not contribute to score totals. Replay must remain neutral even when re-evaluation fails. V2 outer presentation fields must survive a nested-contract fallback. These are narrow runtime compatibility fixes, with no public enum or shared-contract change.

## B and D

B owns ordinary Print mappings, block assembly, Page contracts, frozen parser lowering and styles. D owns task response projection data. Keep teacher answers, feedback and wrong-option notes out of learner pages. Running question numbers must agree in Learn, learner Print and the separate teacher page.

The proposed helper boundary is a task projection returning label, learner block, answer entry and metadata, taking the existing task, index, anchor and inline-lowering callback. Do not introduce new shared task fields to resolve this boundary.

## C

Accepted fresh outputs are retained as authored. Formula has no key idea; all three lack subscript/superscript and misconception nodes. Golden renderer coverage does not clear fresh-generation gate items. Do not rewrite or regenerate accepted content to clear advisory shape findings.

## Phase 5

After accepted merge order 0 → A → B → D → C, one executor runs full integration acceptance. Resolve the documented pre-existing lint errors narrowly, validate repository and architecture, generate the complete photosynthesis lesson end to end, then collect Learn screenshots, learner/teacher PDFs, ordered ordinary-word parity, unchanged legacy hashes and metadata/task results. Every difference against the five supplied artboards receives an acceptable/to-fix decision with evidence.
