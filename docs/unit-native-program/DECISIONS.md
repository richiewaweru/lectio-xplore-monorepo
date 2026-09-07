# Decision log — Unit Print/Learn program

Record implementation choices without rewriting pack intent.

| ID | Date | Question | Decision | Evidence / rationale | Affected contracts / gates |
|---|---|---|---|---|---|
| D-001 | 2026-09-07 | Where to host campaign tracking? | `docs/unit-native-program/` with pack copy under `pack/` | Pack master prompt proposes this location | P00 |
| D-002 | 2026-09-07 | FE-001 fix strategy? | Retarget imports to `$lib/print/...` / `$lib/learn/...` / `$lib/shared/...` owners; narrow domain-guard needle that wrongly banned `$lib/print/studio` | Matches CURRENT_SYSTEM and FE-001 acceptance; Vite `$lib` alias precedence blocked public `$lib/studio` remaps | P00-B01 / P00-B03 |
| D-003 | 2026-09-07 | QuizCheck role vs LEARN-009? | Remove conflicting `role=radio` on `<button>`; use button + `aria-pressed` for click-to-answer | Immediate-submit MCQ is not a radio group; restores accessible name for tests and correct UX | P00-B02 |
| D-004 | 2026-09-07 | Stale agents/project.md? | Rewrite to Unit-path curriculum/print/learn/infra ownership | Pack 02_SOURCE_REVIEW; CURRENT_SYSTEM is authoritative | P00-B03 |
