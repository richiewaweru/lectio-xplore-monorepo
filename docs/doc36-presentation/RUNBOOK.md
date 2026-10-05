# Doc 36 — Lesson presentation revamp

Classification: major. Lead owns orchestration and gate review; Luna executors own implementation.

## Progress

- [x] Read doc 36 in full, doc 35, applicable project rules, design HTML, and sampled recordings.
- [x] Section 9 verified; start from committed `fix/media-truth-execution` (`901cce27`), preserve ongoing edits in its separate worktree.
- [ ] Phase 0: optional contracts, legacy-safe serialization, parsers and shared vectors, golden/legacy/overlong fixtures, dev-only preview/export entrypoints.
- [ ] G0: authentic stored legacy hash unchanged; golden validates; parsers pass identical vectors; existing suites green.
- [ ] A/G1: Learn renderer and desktop/mobile/keyboard/legacy/overlong evidence.
- [ ] B/G2: Print renderer and golden/legacy/overlong/greyscale/answer-separation evidence.
- [ ] D/G4: task authoring/behaviour, legacy compatibility and numbering evidence.
- [ ] C/G3: composer/writer and three live generation/advisory-log evidence.
- [ ] Phase 5: merge order 0, A, B, D, C; real photosynthesis generation, word parity, repo and architecture validation.
- [ ] Track PRs created with gate evidence; final acceptance and visual differences recorded.

## Locked decisions

- Doc 36 wins over the artboards. Print must not abbreviate shared ordinary content. Use existing app display serif and prescribed Atkinson/palette.
- Figure decisions remain doc 35-owned; no renderer/writer invents a figure.
- Length and shape targets are advisory only: never fail, repair, regenerate, pad, truncate, or change READY because of them.
- Preserve stored lessons and hashes; omit only newly introduced absent defaults from canonical serialization, retaining previous null fields.
- The supplied payload is LearnDocument v2, not SharedLessonDocument. Preserve the raw input and obtain the matching stored shared snapshot independently.
- Normal Print blocks stay together. Owner selected safe continuation for blocks taller than an A4 content area, preserving every word.
- Phase 0 freezes shared declarations. A owns task markup/styles; D owns task behaviour and data. B owns the necessary `lectio-page` rendering/contract changes.
- Three execution workers can run alongside the lead in this session; queue the fourth track. Isolate each branch/worktree, no pushes to main.

## Evidence

Gate evidence will be recorded under `evidence/` and linked from each PR. An unchecked item is not satisfied by intent.

### Phase 0 review so far

- Authentic owner lesson retrieved read-only from production. Stored source id is `shared-document:7ea5d498-3550-4259-a9b8-66da3a3f9fdb:revision:1`, hash `44ab7dbe3e048881eda5d6fd15062b82a7a13394b87c66a9a63e2a4706fd3b6b`. Updated models preserve both its hash and serialized payload exactly.
- Local legacy scan: 49 of 51 stored documents validate with unchanged hashes and payloads (`evidence/legacy-bulk-hashes.json`). Two local rows were already invalid on unchanged main, verified in a separate Python process against `C:/Projects/lectio`: `63bfd8ce-af34-4058-a539-3f833e1c5837` has a pre-existing stored hash mismatch; `6c0bc034-3d99-4935-85df-827a6c10c6ec` has a pre-existing missing wrong-option feedback entry. No stored row was edited or re-hashed.
- Page suite: 64 passed (`evidence/g0-page-tests-recheck.log`); shared vocabulary suite: 20 passed (`evidence/g0-contracts-tests.log`). Initial package tests lacked built `@lectio/contracts` output and hit CPU-contention timeouts; building the existing package and limiting workers resolved them without source changes.
- Frontend type check: 0 errors, 5 existing warnings (`evidence/g0-frontend-check.log`). Initial full frontend suite passed 279 tests and exposed two new inline-parser regressions, which were sent back for correction; the final run is still required.
- Golden and overlong fixture review initially rejected abbreviated/generic content. Correcting to the reference's four sections and block sequence is required before G0 acceptance.
