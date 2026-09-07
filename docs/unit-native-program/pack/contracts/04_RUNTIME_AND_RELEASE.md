# Learn delivery, Print export, and release contracts

## Ordered Learn document
Use existing LessonDocument block_ids ordering as authoritative where possible; extend rather than discard valid documents. Avoid reconstructing into a wide SectionContent object when that collapses repeats or changes sequence.
Each interaction binds stable interaction/block/section IDs to an immutable authored task, capability/evaluator version, concepts, assessment mode, attempts, completion and feedback rules.
Builder edits those fields through package-derived schemas. Invalid references or answer keys are caught before publishing. Preview uses the same renderer but an isolated attempt store and never persists student evidence.

## Publish
Validate full native schema, references, required assets, interaction configs, evaluation readiness and provenance. Unit-sourced drafts use the generation's pinned lesson/teaching revision; do NOT stamp today's PathLesson revision onto an older draft. Confirm ownership of explicit source IDs.
Concurrent publish must allocate unique release numbers transactionally; idempotency prevents duplicate clicks publishing twice. Release snapshots/hashes are immutable. Draft edits create a new release without mutating old assigned instances.
Pin renderer/evaluator versions; compatibility is explicit when package versions change.

## Authenticated runtime
Resolve learner identity from authenticated session and assignment authorization, not a request-supplied learner ID alone. Validate instance/release/interaction/section membership server-side.
Request includes instance_id, interaction_id, submission_id, response and expected release identity. Server loads contract from release, validates response, enforces attempt policy, evaluates and derives concept bindings. Ignore/reject client outcome, score and evidence claims.
For local practice/preview feedback, use equivalent evaluator semantics. Shared executable evaluator or generated implementations with cross-language golden tests are acceptable; hand-maintained divergent scoring is not.
Idempotency key scoped to instance/submission; same key with different response is a conflict. Concurrent submissions cannot bypass max attempts.

## Progress
Separate visit/passive completion from assessed completion. Submitted, correct and score-threshold rules behave as authored; any attempt is not universally completion.
Persist current location and restore interaction states after refresh. Navigation policy is explicit (free or sequential) and enforced where required.
Assessment aggregation has a declared policy (first/latest/best, as supported); repeated attempts must not silently inflate numerator and denominator. Guided practice is tracked separately from graded evidence. Concept bands are descriptive evidence, not a claim of complete mastery.
Class analytics filter assignment recipients and intended release/instances; unrelated self-started instances excluded unless explicitly requested.
Provide teacher-review state for tasks that cannot be automatically evaluated; do not invent a score.

## Print
Use the actual product export route with pinned native document. Student PDF hides answers; teacher PDF includes correct answers and intended explanations. Preserve visual assets, ordering, table splitting/repeated headers and text readability.
Export returns or times out with a persisted actionable error; no hung process reported as successful simply because a temporary PDF exists.
Oversized content should follow declared fragmentation behaviour; do not truncate teaching to fit a page. Inspect rendered pages, not merely file signature.

## Package and app evidence
All interaction evaluators get duplicate/unknown/missing ID and invalid numeric cases. Spatial payloads need asset-coordinate integrity and keyboard-operable responses. No scored runtime capability is activated with an incomplete evaluator or unknown scoring version.
