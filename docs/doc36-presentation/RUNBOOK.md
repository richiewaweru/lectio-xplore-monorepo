# Doc 36 — Lesson presentation revamp

Classification: major. Lead owns orchestration and gate review; Luna executors own implementation.

## Progress

- [x] Read doc 36 in full, doc 35, applicable project rules, design HTML, and sampled recordings.
- [x] Section 9 verified; start from committed `fix/media-truth-execution` (`901cce27`), preserve ongoing edits in its separate worktree.
- [x] Phase 0: optional contracts, legacy-safe serialization, parsers and shared vectors, golden/legacy/overlong fixtures, dev-only preview/export entrypoints.
- [x] G0: authentic stored legacy hash unchanged; golden validates; parsers pass identical vectors; existing suites green.
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
- Owner confirmed equation input/output and comparison-card upper bounds are advisory too; preserve every term/card. Meaningful structural minimums remain schema requirements.
- Preserve stored lessons and hashes; omit only newly introduced absent defaults from canonical serialization, retaining previous null fields.
- The supplied payload is LearnDocument v2, not SharedLessonDocument. Preserve the raw input and obtain the matching stored shared snapshot independently.
- Normal Print blocks stay together. Owner selected safe continuation for blocks taller than an A4 content area, preserving every word.
- Phase 0 freezes shared declarations. A owns task markup/styles; D owns task behaviour and data. B owns the necessary `lectio-page` rendering/contract changes.
- Three execution workers can run alongside the lead in this session; queue the fourth track. Isolate each branch/worktree, no pushes to main.

## Evidence

Gate evidence will be recorded under `evidence/` and linked from each PR. An unchecked item is not satisfied by intent.

### G0 accepted

- Implementation commits: `ab4452df`, `7b7a473e`, `83d94780`. Shared declarations are frozen; subsequent semantic changes require lead review.
- Authentic stored legacy source validates with hash `44ab7dbe3e048881eda5d6fd15062b82a7a13394b87c66a9a63e2a4706fd3b6b`; newly absent defaults stay omitted while existing null serialization is retained. Focused fixture/adapter/parser tests: 9 passed (`evidence/g0-final-backend-focused.log`). Golden schema and preservation of extra equation terms/comparison cards are covered.
- Both parsers use identical shared vectors, including empty, malformed delimiters and HTML. Frontend parser: 8 passed (`evidence/g0-final-frontend-parser.log`). Rendering boundaries escape text.
- Full backend: 2,015 passed, 5 skipped, 7 deselected, exit 0 (`evidence/g0-backend-tests.log`). Final frontend: 281 passed (`evidence/g0-final-app-test.log`). Page: 64 passed (`evidence/g0-final-page-test.log`). Shared vocabulary: 20 passed (`evidence/g0-contracts-tests.log`). Frontend check: 0 errors, 5 existing warnings (`evidence/g0-final-app-check.log`). Architecture: no violations (`evidence/g0-architecture.log`).
- Development previews return 200 for all three fixtures and the supplied SVG; unknown names return 404 (`evidence/g0-final-dev-route-smoke.log`). Server routes and asset endpoint explicitly return 404 outside development. Legacy fixture exports through the existing Svelte/Playwright PDF pipeline (`evidence/g0-legacy-print.pdf`, six pages). Golden/overlong PDF projection awaits Track B's new-kind mappings.
- Local stored-data audit: 49 of 51 rows retain identical payloads and hashes (`evidence/legacy-bulk-hashes.json`). Two rows already invalid on unchanged main: `63bfd8ce-af34-4058-a539-3f833e1c5837` has a stored hash mismatch; `6c0bc034-3d99-4935-85df-827a6c10c6ec` lacks wrong-option feedback. No stored row was edited or re-hashed.
- Golden follows the four-section reference and block order. The added note "Leaf area can be measured in m^2^." supplies the mandatory superscript coverage absent from the artboard. The seedling SVG paths match the supplied artwork. Record these provenance details in the final visual-difference list.
- Repository-wide lint has 30 pre-existing errors (`evidence/g0-backend-lint.log`): intentional compatibility imports/setup ordering and unused imports. Phase 5 must resolve these narrowly before final repository validation; they do not represent new Phase 0 failures. The five existing Svelte warnings also remain recorded.
