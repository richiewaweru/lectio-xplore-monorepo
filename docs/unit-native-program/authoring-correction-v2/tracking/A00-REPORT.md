# Phase report
Phase: A00
Status: PASS
Base and tested commit / dirty-tree fingerprint: baseline `998e9f36e75f81899a6405a5d199e2f246bcbf9c` on `feat/unit-print-learn`; A00 artifacts added on top. Preserved dirty tree: p05 page-image status, overflow png, `.tmp/`, backend data/logs, p09 scripts (not committed).

Requirements read: README, ARCHITECTURE, SOURCE_MAP, acceptance/POLICY, phases/A00, KNOWN_ANSWER_CASES, COMMAND_MAP, unit-native STATE.

Execution plan: See `tracking/A00-PLAN.md`. Record baseline and call graph; add isolated failing regressions for carried-forward defects; do not implement product fixes in A00.

Changed files and resulting behavior:
- Baseline/map docs under `tracking/A00-*.md`
- Failing regressions in `apps/textbook-agent/backend/tests/authoring_correction/`
- Evidence under `evidence/a00/`
- No product behavior changes (intentional)

Gate IDs and commands:
- A00-G01: baseline docs present (`A00-BASELINE.md`, call graph, dirty work, commands)
- A00-G02: `uv run pytest -q tests/authoring_correction` from `apps/textbook-agent/backend` → 7 failed for intended defect reasons
- A00-G03: `tracking/A00-REQUIREMENT_MAP.md` covers Print+Learn, core eight, generation-enabled content

Regression proof before/after: before = current HEAD defects exposed; after = deferred to A01–A05 fixes.

Mock boundaries: provider boundary mocked only in print table failure test.

Actual normal entrypoints exercised: `write_*_payload` / `ordered_assemble` / `select_learn_deterministically` / `derive_learn_block_candidates` / `dispatch_writer_async` (defect surfaces), not full dual-path yet.

Evidence paths:
- `docs/unit-native-program/authoring-correction-v2/evidence/a00/`
- `docs/unit-native-program/authoring-correction-v2/evidence/a00/pytest-all.txt`

Remaining defects / environment blockers: all five reviewed defect classes remain open by design until later phases.

Readiness and original gates reopened: none yet (A00 is baseline only).

Next phase: A01 package authoring definitions.