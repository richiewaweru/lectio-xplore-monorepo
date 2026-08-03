# CURSOR_GOAL.md — Restructure implementation, end to end

You are running a long, unattended implementation session on the `xplore` branch of `text-book-generator`. Your single source of truth is [`handoff/RESTRUCTURE_HANDOFF.md`](handoff/RESTRUCTURE_HANDOFF.md). Read it fully before writing any code. Where this file and the handoff conflict, the handoff wins. Where the handoff and existing code conflict, the handoff wins — that is the point of the restructure.

The user will not be watching. Do not stop to ask questions unless you hit a **stop condition** (§7). Work carefully rather than fast: every workstream ends with verification before the next begins.

Keep [`RESTRUCTURE_PROGRESS.md`](RESTRUCTURE_PROGRESS.md) updated after every commit.

---

## 1. Ground rules

- **Never touch:** the stage 1 structural planner (prompt content, reasoning level, slot, schema), item generation logic reading anything beyond concept-card fields (the wall), any auto-approval shortcut (the halt), path planner prompt content, pack immutability. If a change you're making seems to require touching these, stop and record it as a stop condition instead.
- **Prompt extraction is verbatim.** When moving prompt text from Python f-strings to `.md` files, the static text must be byte-identical after accounting for interpolation seams. Diff the assembled prompt before/after extraction to prove it.
- **Every commit is one coherent change** with a message referencing the handoff section (e.g. `A1: fan out all expander sections in one wave`). No mixed commits.
- **Tests are updated in the same commit as the behavior change**, per the breakage checklist in handoff §8. Never delete a failing test to make the suite green; rewrite it to assert the new intended behavior.
- Keep a running `RESTRUCTURE_PROGRESS.md` at repo root: one line per completed item — what changed, files, test evidence, anything deferred. Update it after every commit. This is the user's window into the session.
- Do not refactor, rename, or "clean up" anything outside the handoff's scope, however tempting.

## 2. Order of work

Follow handoff §9 exactly:

1. **Baseline.** Before any change, run one full lesson generation locally (or against the dev stack) and save the `[STAGE2 ...]` / `elapsed=` log lines to `RESTRUCTURE_PROGRESS.md`. If you cannot run a generation locally, record why and use test-level timing instead — but say so explicitly.
2. Workstream A (speed): A1, A4 first (pure structure), then A2 + A3 together (reasoning drop + brief cap), then §6.1 slot changes **one node per commit**.
3. Workstream B (nominated-pairs critic).
4. Workstream C (prompt packaging: files, manifest, loader, overlay table + migration, hash stamping, settings page).
5. Workstream D (constructor node, readback screen, chat plan editing, screens 1–5 language rebuild).
6. Final sweep: handoff §8 checklist item by item, checking each box in `RESTRUCTURE_PROGRESS.md`.

## 3. Environment variables — verify, don't assume

The user has already set the new values **on Railway**:

```
V3_STAGE2_PARALLEL=true
V3_TIMEOUT_STAGE2_SECTION_SECONDS=100
V3_CONCURRENCY_SECTION_MAX=5
V3_CONCURRENCY_QUESTION_MAX=5
```

Your jobs regarding these:

1. Update `backend/.env.example` (and any local `.env` template / docker-compose defaults) to match, so local dev mirrors production — this is a standing project rule.
2. Grep the codebase to confirm each variable is actually read where the handoff says (`config/timeouts.py`, `config/concurrency.py`, `retry.py`) and that no other code path hardcodes the old values (search for `240`, `Semaphore(3` near these modules).
3. **Prove they take effect at runtime:** add (or use) log lines that print the resolved timeout and semaphore sizes at generation start, run a generation, and confirm the logs show 100 / 5 / 5. An env var that is set but never read is the classic silent failure here — do not mark this done on grep evidence alone.
4. Remember reasoning levels and slot assignments have **no env vars** — those are your code changes in `models.py`. Do not "implement" them by inventing new env vars unless the handoff's structure makes one natural; if you do add one, document it in `.env.example` and `RESTRUCTURE_PROGRESS.md`.

## 4. Verification per workstream (mandatory before moving on)

**A (speed):**

- New/updated `test_stage2_parallel.py` green: one-wave dispatch, exception isolation, plan-derived continuity in user messages.
- Word-cap validator test green with an over-long fixture.
- Run the **same lesson as the baseline**; save new `elapsed=` lines next to the old ones. Target: total under 5 minutes. If not met, profile which phase still dominates and record it — do not silently proceed.
- For A2 specifically: save the expander briefs from baseline and post-change runs side by side in `RESTRUCTURE_PROGRESS.md` (or a `briefs_compare/` folder) so the user can judge quality. You may note obvious regressions (missing misconception coverage, lost anchor references) but the quality call is the user's.

**B (critic):**

- Tests: critic called exactly once per nominated pair; zero calls when nominations empty.
- Run the path planner on a real topic and log actual call count vs nominations.

**C (prompts):**

- Assembled-prompt diff proves extraction is verbatim (empty diff for static text).
- Overlay round-trip test: save override → generation uses it → reset → default restored. Locked prompts reject edits at the API (test the 4xx).
- A generated lesson's record contains prompt hashes; changing a prompt changes the hash on the next generation.
- Settings page renders `.md` as formatted markdown, not raw text; modified badge appears after an edit.

**D (constructor/screens):**

- Route test: create unit with only subject + grade + free text succeeds; old three fields absent from the form; backend still accepts them if posted (transition tolerance).
- Constructor returns at most one clarifying question (prompt rule + a test with an ambiguous fixture).
- Banned-words check: grep built frontend user-visible strings for `concept path|variant|canonical|skeleton|delta|support level|merge critic|forward verified|prerequisite risk|lesson_mode|knowledge type|structural plan` — zero hits in rendered copy (TypeScript type names are exempt).
- Chat plan edit → `validate_path_plan` still runs → approval lock conditions unchanged (test that an unresolvable plan cannot be locked).

**Wall check (last, always):** re-run a grep audit that item-generation prompts consume only card fields; record the command and output.

## 5. Full-suite discipline

Run the entire backend and frontend test suites at the end of each workstream, not just the touched files. A green targeted test with a red suite means stop and fix before continuing. Record suite results (counts) in `RESTRUCTURE_PROGRESS.md` per workstream.

## 6. Definition of done

All eight acceptance checks in handoff §9 pass, each with recorded evidence in `RESTRUCTURE_PROGRESS.md`; the §8 checklist is fully ticked; both test suites green; `.env.example` matches Railway; superseded handoff docs (`11`, `07` UI portions, `14`) carry a pointer note to `RESTRUCTURE_HANDOFF.md`. Finish with a summary section in `RESTRUCTURE_PROGRESS.md`: what shipped, what was deferred and why, and the before/after timing numbers.

## 7. Stop conditions — pause and leave a clear note instead of guessing

- A change appears to require modifying stage 1, the wall, or the halt.
- Removing anchor-serial breaks resume (`persistence.py`) in a way the handoff's mirror-fix doesn't cover.
- Expander output at low reasoning is drastically degraded (not subtly — e.g. empty or off-card briefs) even after the brief cap.
- A migration would destroy existing data (path versions, generations).
- The verbatim-extraction diff cannot be made empty for a prompt.

For any stop: write the situation, the options you see, and your recommendation into `RESTRUCTURE_PROGRESS.md` under a `## BLOCKED` heading, commit, and halt that workstream — continue with an independent one if any remains.
