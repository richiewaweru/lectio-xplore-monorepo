# Acceptance Checklist

## Runtime

- [ ] New generations are native-only.
- [ ] No v1 conversion, builder, stage2, or blueprint execution is called.
- [ ] Native state transitions are explicit and tested.
- [ ] Terminal states always have non-null structured errors.

## Forms

- [ ] Prose works.
- [ ] List works.
- [ ] Table works.
- [ ] Figure pending placeholder works.
- [ ] Aside works.
- [ ] Worked example works.
- [ ] Open-response questions work.
- [ ] Choices/MCQ works.
- [ ] Section title provides normal heading behavior.
- [ ] Document-level answer key works.
- [ ] Explicit heading object remains valid in Lectio tests.

## Writers

- [ ] One general engine uses form-specific typed output models.
- [ ] Unknown forms fail immediately.
- [ ] Extra properties fail.
- [ ] Writer cannot alter object, intent, ID, or position.
- [ ] Content validates before persistence.
- [ ] Invalid content is never marked ready.
- [ ] Repair includes previous output and exact errors.
- [ ] Repair is limited and separately counted from transport retries.

## Assessments

- [ ] `questions` contains no options or correct-key fields.
- [ ] MCQ content uses `choices`.
- [ ] Questions and answer entries are generated in one logical pass.
- [ ] Stable IDs connect student items to answer entries.
- [ ] Every assessed item has exactly one answer.
- [ ] Every answer points to an existing assessed item.
- [ ] MCQ answer matches an available option.
- [ ] Student output hides answer key.
- [ ] Teacher output shows answer key.

## Parallelism and durability

- [ ] Sections are the primary parallel unit.
- [ ] Maximum concurrency is four.
- [ ] Completion order does not change document order.
- [ ] Completed sections persist independently.
- [ ] Resume skips validated completed sections.
- [ ] One failed section does not delete other results.
- [ ] Lease loss does not overwrite newer work.

## Assembly

- [ ] Assembly makes no LLM calls.
- [ ] Expected and actual IDs are reconciled.
- [ ] Blocks are sorted by planned positions.
- [ ] Answer entries merge mechanically.
- [ ] Full document validates.
- [ ] Persisted document reloads and validates.
- [ ] Canonical ordering/hash is stable.

## Status and UI

- [ ] API reads native state.
- [ ] API returns section and block progress.
- [ ] Recoverable failures identify section/block and validation errors.
- [ ] Frontend stops polling on terminal states.
- [ ] Frontend shows retryable failures clearly.
- [ ] Pending figure displays placeholder.
- [ ] Ready document opens in viewer.

## Outputs

- [ ] Mocked all-forms document JSON.
- [ ] Reloaded document JSON.
- [ ] Student render.
- [ ] Teacher render.
- [ ] Student PDF.
- [ ] Teacher PDF.
- [ ] Status timeline.
- [ ] Mock scenario report.
- [ ] Real LLM smoke report.
- [ ] Exact test logs.
- [ ] Legacy reference audit.

## Final failure threshold

The implementation is incomplete if any of these occur:

- unexplained HTTP 500;
- `failed_terminal` with `error: null`;
- stuck polling;
- invalid content persisted as ready;
- mock full-flow cannot produce a document;
- student/teacher PDF missing;
- real-provider issue cannot be distinguished from application failure.
