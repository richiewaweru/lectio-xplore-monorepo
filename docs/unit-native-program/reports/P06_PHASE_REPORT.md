# Phase report

Phase: P06 — Complete Learn generation, ordered rendering and publishing
Status: PASS
Starting commit: `e22d50a` (P05 STATE head on branch) / ending code commit: see implementation commits below — last gate suite run against the working tree that includes writer/assemble/publish/render changes. This report is committed on top and changes no product code.
Dirty files preserved: `.tmp/**`, `apps/textbook-agent/backend/.tmp/*.log`, `apps/textbook-agent/backend/data/` — none committed.

Contract/spec/prompt versions:

| Artefact | Version / note |
|---|---|
| Learn interaction writer | `learn/generation/interaction_writer.py` (Sequence deterministic writer) |
| Ordered assemble | `learn/generation/ordered_assemble.py` (`block_ids` authority) |
| Publish validation | `learn/publishing/publish_validation.py` |
| Release routes | `learn/publishing/release_routes.py` (pinned provenance, idempotent + locked numbers) |
| Sequence readiness | `@lectio/learn` catalogue — Sequence `generation-ready` / `available` |
| Spatial | `image-hotspot` / `drag-label` remain unavailable |

Dependencies verified: P04 PASS (`0a30c1b` / report `cf209bf`); P05 PASS preserved in STATE (`abf1e97` / `e22d50a`).

## Changes and purpose

### Learn generation

- Deterministic Sequence writer consumes scoped `build_learn_writer_request` output and emits a validated `LearnInteractionContract` with concept/assessment/feedback/completion metadata and work-order provenance (not a hand-injected lesson payload).
- Ordered assembler walks teaching decisions and writes content then interaction blocks into authoritative `block_ids`, preserving repeats and interleaving.

### Publishing

- Full publish validation: shape, missing/duplicate block refs, interaction contracts, dangling sequence/media/concept refs.
- Unit-sourced drafts pin `LessonProvenanceModel.path_lesson_revision` / `objective_hash`; never stamp live PathLesson revision onto an older draft.
- Release allocation uses `SELECT … FOR UPDATE` on the editable lesson, IntegrityError retry, and same-hash idempotent replay.

### Package / Builder / student shell

- `BlockInstance.learn_interaction`, ordered-block helpers, and explicit lossy contract on `toSectionContents`.
- Package-derived Sequence Builder edit schema; document store persists interaction field edits.
- `StudentLessonShell` renders via `OrderedBlockList` (block_ids), not SectionContent reconstruction.
- Preview attempt store API marks `persists_production_attempts: false`; Sequence remains the activated interaction (spatial still unavailable).

## Gate evidence

All backend commands from `apps/textbook-agent/backend` with `uv run`. Evidence under `docs/unit-native-program/evidence/mocks/p06/`.

| Gate ID | Test or command | Expected | Actual | Status | Evidence |
|---|---|---|---|---|---|
| P06-L01 | `uv run pytest -q tests/print_learn/test_p06_learn_authoring_gates.py::test_p06_l01_sequence_via_selector_writer_not_injected` | Sequence via selector→work order→writer→assemble with provenance linkage | 1 passed, exit 0 | PASS | `l01-selector-writer.txt` |
| P06-L02 | `...::test_p06_l02_repeated_and_interleaved_order_survives_assemble` | Repeated explanations + content→activity→content survive assemble/reload | 1 passed, exit 0 | PASS | `l02-ordered-blocks.txt` |
| P06-L03 | `...::test_p06_l03_builder_edit_persists_and_malformed_blocks_publish` (+ spatial reject) | Valid edit persists; malformed/dangling block publish; spatial writer unavailable | 2 passed, exit 0 | PASS | `l03-builder-publish-validation.txt` |
| P06-L04 | `...::test_p06_l04_preview_*` | Preview store non-persisting; draft edit leaves release hash unchanged; zero LearnerAttempt rows | 2 passed, exit 0 | PASS | `l04-preview-isolation.txt` |
| P06-L05 | `...::test_p06_l05_publish_v1_immutable_v2_and_idempotent_concurrent` | v1 immutable after edit/v2; same-hash idempotent; concurrent same-hash converges | 1 passed, exit 0 | PASS | `l05-publish-immutable-idempotent.txt` |
| P06-L06 | `...::test_p06_l06_old_draft_keeps_pinned_provenance` | After PathLesson revision bump, publish stamps pinned revision not live | 1 passed, exit 0 | PASS | `l06-pinned-provenance.txt` |

Supporting: `l01-l06-pytest.txt` (8 passed); `learn-releases-regression.txt`; `sequence-readiness-vitest.txt` (24 passed); `export-contracts.txt`.

## Failure attribution and repairs

- Snapshot field name is `snapshot_hash` (not `selection_hash`) — fixed in assembler metadata.
- Concurrent SQLite FOR UPDATE + expired ORM after rollback: build response before rollback; concurrent gather uses same-hash idempotency.

## Migration and compatibility

- No DB migration. Additive modules and optional `learn_interaction` on blocks.
- `toSectionContents` remains for legacy templates with documented lossy behaviour; student shell no longer uses it for authoritative order.
- Existing manual PathLesson attach (no generation pin) still uses live PathLesson identity.

## Decisions or deviations

- D-023: Sequence flips to `generation-ready` after Builder editor + writer/assemble path (closes D-007/D-018 for Sequence only).
- D-024: Publish idempotency is same-document-hash replay (duplicate click), not a separate idempotency-key table.
- Spatial stays unavailable (D-010); L01 uses Sequence honestly.

## Remaining risk / blocked access

- Other text interactions (choice, numeric, …) remain `planned` until Builder editors + writers exist.
- P07 still owns authenticated attempt persistence / evidence.
- Concurrent unique-number races are covered under same-hash idempotency; Postgres FOR UPDATE is the intended production serializer.

## Next phase

P07 (Learn runtime) is eligible. P08 integration may wait for P07 if runtime evidence is required.

Next command: read `docs/unit-native-program/pack/phases/P07_LEARN_RUNTIME.md`.
