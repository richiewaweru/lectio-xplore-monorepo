# Track C Learn visual evidence

Captured 2026-10-05T15:04Z from commit `c34645b2` plus the named preview wiring in this follow-up. The three LearnDocument v2 payloads were copied verbatim from C's accepted exports:

- `C:/Users/richi/.codex/worktrees/doc36-writer/lectio/docs/doc36-presentation/evidence/track-c/photosynthesis-learn-v2.json` -> `g3-photosynthesis`
- `C:/Users/richi/.codex/worktrees/doc36-writer/lectio/docs/doc36-presentation/evidence/track-c/formula-learn-v2.json` -> `g3-formula`
- `C:/Users/richi/.codex/worktrees/doc36-writer/lectio/docs/doc36-presentation/evidence/track-c/comparison-learn-v2.json` -> `g3-comparison`

The dev-only routes are:

- `http://127.0.0.1:5181/dev/shared-lesson/g3-photosynthesis`
- `http://127.0.0.1:5181/dev/shared-lesson/g3-formula`
- `http://127.0.0.1:5181/dev/shared-lesson/g3-comparison`

Each route returned HTTP 200 in the dev server and was captured at 1280px and 390px widths. The screenshot pairs are:

- `g3-photosynthesis-learn-desktop.png`, `g3-photosynthesis-learn-mobile.png`
- `g3-formula-learn-desktop.png`, `g3-formula-learn-mobile.png`
- `g3-comparison-learn-desktop.png`, `g3-comparison-learn-mobile.png`

`g3-learn-dom.json` records route status, responsive widths, block classes, inline element counts, and the absence of literal valid markup delimiters. The fresh previews visibly exercise the equation, key-idea callout, compare cards, and authored bold text. The three fresh C outputs do **not** contain a subscript, superscript, table, or misconception node, so those G3 shapes are explicitly unexercised by the fresh provider outputs. The frozen golden Learn preview supplies separate renderer coverage only: `g3-coverage-dom.json` records 14 strong, 1 emphasis, 1 subscript, 1 superscript, equation, table, compare, and both misconception cards; its `literalMarkup` check is false. The corresponding golden/legacy/overlong screenshots remain unchanged.

Actual quality misses recorded from C's accepted outputs: `g3-formula` has no key-idea block; C's `format-validation.json` reports the advisory `shape_missing` at `section/key_idea`. In the Learn rendering, the photosynthesis and comparison key-idea callouts follow their equation/compare blocks rather than opening the section, which is an advisory presentation difference. The accepted words are preserved without repair; no provider call or content edit was made.

The route remains development-only. Existing auth and production guard evidence is retained in `g1-fixture-setup.md` and `g3-learn-dom.json` only covers the dev capture.

