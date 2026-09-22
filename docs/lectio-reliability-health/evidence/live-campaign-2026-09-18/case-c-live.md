# Case C — mathematical procedure

Status: `PASS WITH FOLLOW-UP`

## Durable identities

- Unit: `17f1927c-fca7-42b4-a49d-d8fcc2bb06d1` — Solving One-Step Equations
- Lesson: `569204fb-aaeb-42f6-9cf4-913d319de0ad`
- Preparation: `aaf2fa71-efde-4c99-965f-b2411db3978c`
- Learn realization: `89e6623d-39d6-4fc7-9349-c3bfa26e9fb0`, ready
- Learn output: `learn-out-b40e52771173`
- Learn Teaching Plan revision/hash: `1` / `c5de32db257652dfab5494506821bcc5f008dcded00dfd00fa3b90ce85a8ff8d`
- Print: legacy ready output `aaf2fa71-efde-4c99-965f-b2411db3978c`

## Live result

- The legacy approved snapshot was normalized into a durable approved Teaching
  Plan. Obsolete legacy `variant` fields were stripped before v2 validation.
- Learn creation succeeded through the normal UI with the real provider.
- The Learn builder accepted an edit, showed `Saved`, and retained the marker
  text after reload.
- Preview explicitly showed `PREVIEW — ATTEMPTS ARE NOT SAVED.`
- Learn publishing succeeded. The lesson was assigned to the campaign class.
- Print preview loaded with teacher content and answer key. Teacher and student
  PDF export actions were invoked in the UI.
- Redacted learner instance `f027…` completed after visiting all four sections;
  refresh preserved completed status and section progress.
- This generated document contained no interaction nodes, so no learner
  attempt was created for this case. Completion and persistence were still
  server-side and durable.

## Follow-up

Physical PDF artifacts were not exposed for visual inspection. The live case
also did not exercise an actual mathematical interaction, duplicate submission,
or forged-score rejection. Marked PASS WITH FOLLOW-UP rather than full PASS.
