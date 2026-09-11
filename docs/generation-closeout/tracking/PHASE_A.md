# Phase A — Externalize generation specs/policies

Status: PASS

## CURRENT
Composer/writer loaded via Path.read_text; action maps hardcoded; no policies/.

## CHANGE
Manifest-backed closeout prompts; YAML action maps; canonical loader used by composer, writer, interaction writer, figure pipeline, and Print authoring adapter.

## CANONICAL CALLER
`document.composer` / `document.writer` → `effective_prompt_text`
`learn.generation.interaction_writer` → `interaction-writer`
`learn.generation.figure_pipeline` → `figure-authoring`
`print.generation.authoring_adapter` → `print-realization`
`learn.interactions.action_map` / `print.generation.task_treatments` → `core.policies.loader`

## TEST
`uv run pytest tests/core/prompts/test_closeout_specs.py tests/core/policies/test_action_maps.py tests/core/prompts/test_loader.py tests/print_learn/test_print_document_align.py tests/authoring_correction/test_a01_authoring_definitions.py -q`
19 passed.

## LIVE PROOF
Offline for A: production call graph + hash proof (Markdown default change alters hash without Python logic). Live Units start in B.

## STATUS
PASS
