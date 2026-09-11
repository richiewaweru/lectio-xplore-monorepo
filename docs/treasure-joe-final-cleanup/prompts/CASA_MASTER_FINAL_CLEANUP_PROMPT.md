# CASA / Grok Master Final Cleanup Prompt

Repository: `richiewaweru/lectio-xplore-monorepo`

Start from current tip of `fix/generation-spec-closeout`.
Planning baseline: `6f782e94769d0dfce34b2dd80d1d462a9c38bd04`.

Create a new branch, recommended:

```text
fix/treasure-joe-final-cleanup
```

Record the actual starting SHA.

## Mission

This is NOT a redesign.

Close exactly six issues:

1. close learner-action vocabulary against YAML;
2. make interaction-selection semantics truthful;
3. delete residual v1 Learn salvage;
4. prove exact Unit→Learn interaction flow;
5. prove native Print edit reaches actual PDF;
6. run full repo gates and finalize tracking.

## Read first

- repository AGENTS/project instructions
- `docs/generation-closeout/`
- this final-cleanup pack
- `verification/STRICT_GATE_MATRIX.md`

## Agent rules

A file existing is not completion.
A helper test is not completion.
A seed script is not a substitute for Unit flow.
A UI toast is not proof of final artifact output.
A prompt loaded for hashing is not proof it controls reasoning.
A "non-canonical" legacy path is not deleted.

Use only:

```text
PASS
FAIL
BLOCKED
```

Never `pass with debt`, `mostly pass`, or `deferred`.

Do not proceed past a failed phase.

## Phase A

Make `learner-actions.yaml` authoritative at Teaching Plan validation.

Unknown actions must enter structured planner repair/retry before approval.

Do not duplicate action vocabulary in Python enums.

Resolve `describe-in-own-words` deliberately.

Prove every canonical non-passive action has downstream path support.

## Phase B

Interaction selection:

```text
1 legal candidate
→ deterministic, no LLM

2+ legal candidates
→ structured LLM selector using interaction-selection.md
→ validate result is one of candidates
```

If no meaningful multi-candidate use case exists, keep deterministic behavior and correct the docs/claims instead of faking an LLM stage.

Record selection mode.

## Phase C

Trace and remove:
- `build_closed_learn_production`
- `build_closed_learn_production_async`
- `host_interaction_blocks_for_builder`
- primitive→`explanation-block` v1 remap
- obsolete tests/fixtures supporting that path

Migrate legitimate tests to LearnDocument v2.

Preserve only genuinely historical migration references.

## Phase D

Required proof:

```text
fresh Unit
→ normal Teaching Plan
→ approve
→ Unit Generate Learn
→ canonical realize-learn
→ LearnDocument v2
→ Builder
→ natural interaction
→ submit/evaluate
→ persisted/reloaded attempt
```

Forbidden substitutes:
- hand-injected learner_action
- seed script directly into Builder
- manual DB edits
- failed_terminal Studio fallback

If it fails, fix product path and rerun from a fresh Unit.

## Phase E

Required proof:

```text
native Print artifact
→ edit unique marker
→ save revision
→ reload marker
→ actual PDF export/download
→ open/extract PDF
→ marker present
```

Also prove stale revision 409 and unchanged Learn sibling.

"PDF export started" is not proof.

## Phase F

Run every command in `verification/COMMANDS.md`.

Run negative searches in `verification/SEARCH_GATES.md`.

Commit implementation.

Then update tracking metadata with the REAL SHA. If metadata requires a follow-up commit, record:
- implementation SHA
- final tracking SHA

Do not leave `pending-commit`.

Do not claim GitHub CI passed if there are no remote checks.

## Final report

Return:

A. starting branch/SHA  
B. final branch/SHA(s)  
C. phase A–F ledger  
D. files changed/deleted  
E. learner-action closure proof  
F. interaction selection proof  
G. exact Unit→Learn ids and route trace  
H. interaction submission/evaluation/persistence proof  
I. exact Print generation/revision  
J. actual PDF marker proof  
K. zero-v1 search results  
L. every command/result  
M. tracking SHA values  
N. PASS / FAIL / BLOCKED by phase  
O. READY TO VERIFY / NOT READY / BLOCKED

Do NOT merge. Push branch and stop for independent verification.
