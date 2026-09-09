# A01 Report — Complete package authoring definitions

Status: PASS  
Tested commit: A01 commit at `git HEAD` on `feat/unit-print-learn`

## Summary
- Extended the existing `@lectio/page` `FormWriterRecord` and `@lectio/learn` `LearnWriterRecord` projections with A01 authoring definition fields: definition version, capability id, native path, lane, modes, resolved instructions, schema refs, required inputs, validators, converter/postprocessor refs where applicable, and `definition_hash`.
- Added package-owned instruction resources under each package's `contracts/authoring/instructions/` directory. Print resources reconcile the previous backend prompt files; Learn resources cover the core eight interactions and all package generation-ready content rows, including the native policy's 13 offered content ids.
- Regenerated package contracts and synced the generated writer views into `apps/textbook-agent/backend/contracts`.
- Updated backend Print/Learn work-order hash helpers and request builders so the complete authoring definition, including instructions, reaches writer requests and affects the capability contract hash.
- Added readiness checks so missing instructions, missing schemas/required inputs/modes, or unknown validator refs fail explicitly before generation selection.

## Evidence
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/page-export.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/learn-export.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/page-sync.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/learn-sync.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/page-tests.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/learn-tests.txt`
- `docs/unit-native-program/authoring-correction-v2/evidence/a01/backend-a01-tests.txt`

## Commands
- `pnpm --dir packages/lectio-page export-contracts`
- `pnpm --dir packages/lectio-learn export-contracts`
- `python apps/textbook-agent/tools/update_lectio_page_contracts.py`
- `$env:LECTIO_PACKAGE_DIR='C:\Projects\lectio\packages\lectio-learn'; python apps/textbook-agent/tools/update_lectio_contracts.py`
- `pnpm --dir packages/lectio-page test -- --run src/lib/catalogue/views.test.ts src/lib/catalogue/regeneration.test.ts`
- `pnpm --dir packages/lectio-learn test -- --run src/lib/learn/capabilities/views.test.ts src/lib/learn/capabilities/content.test.ts scripts/export-capabilities.test.ts`
- `cd apps/textbook-agent/backend; uv run pytest -q tests/authoring_correction/test_a01_authoring_definitions.py`

## Gate Results
- A01-G01: PASS. Package and backend tests assert complete authoring definitions for generation-enabled Print forms and Learn capabilities.
- A01-G02: PASS. Resource-only instruction changes propagate into exported writer views and backend writer requests without dispatcher edits.
- A01-G03: PASS. Missing instructions and unknown validators fail readiness explicitly; generated exports and sync commands pass.
- A01-G04: PASS. Instruction and schema changes alter definition hashes. Existing persisted releases remain unchanged because A01 only changes newly exported package definitions and work-order identity; no release migration or persisted document rewrite was performed.

Offline corrective gates passed; live/model-quality verification deferred.
