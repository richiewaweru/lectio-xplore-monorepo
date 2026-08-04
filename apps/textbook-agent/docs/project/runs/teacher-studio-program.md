# Teacher Studio Program

**Status**: implemented

## Checklist
- [x] Phase 1 planning contracts and `/api/v1/brief`
- [x] Phase 1 `TeacherStudio` dashboard replacement
- [x] Phase 2 spec-backed `/api/v1/generations`
- [x] Phase 2 planner-skip and section-plan-driven execution
- [x] Phase 3 targeted enhancement requests
- [x] Phase 3 truthful progress and viewer controls
- [x] Full validation and architecture review

## Notes
- This runbook tracks the staged Teacher Studio program end to end.
- The dashboard now launches from a reviewed `GenerationSpec` instead of the legacy dashboard form.
- `POST /api/v1/brief` returns a live-safe reviewed plan using contract metadata, shared profile context, one strict retry, and deterministic fallback behavior.
- `POST /api/v1/generations` accepts an optional `generation_spec` and maps reviewed sections into pipeline `SectionPlan` objects.
- The pipeline now skips the curriculum-planning LLM when section plans are supplied and uses section policy to drive composition, interaction, diagram, and follow-up rerun behavior.
- Generation detail responses now expose `planning_spec`, and enhancement requests support `document`, `section`, and `component` scope.
- The textbook viewer now consumes normalized `progress_update` SSE events and surfaces section-level enhancement actions while preserving progressive rendering.

## Validation
- `python -m py_compile backend/src/textbook_agent/application/dtos/brief.py backend/src/textbook_agent/application/dtos/generation_request.py backend/src/textbook_agent/application/services/brief_planner_service.py backend/src/textbook_agent/interface/api/routes/brief.py backend/src/textbook_agent/interface/api/routes/generation.py backend/src/textbook_agent/interface/api/app.py backend/src/pipeline/providers/registry.py backend/src/pipeline/types/requests.py backend/src/pipeline/nodes/curriculum_planner.py backend/src/pipeline/nodes/composition_planner.py backend/src/pipeline/nodes/content_generator.py backend/src/pipeline/nodes/process_section.py backend/src/pipeline/nodes/interaction_decider.py backend/src/pipeline/prompts/content.py`
- `uv run pytest tests/interface/test_brief.py tests/interface/test_api.py -q`
- `npm test`
- `npm run check`
- `python tools/agent/check_architecture.py --format text`
- `python tools/agent/validate_repo.py --scope all`

## Validation Results
- `uv run pytest tests/interface/test_brief.py tests/interface/test_api.py -q`: pass
- `npm test`: pass
- `npm run check`: pass
- `python tools/agent/check_architecture.py --format text`: pass, no architecture violations found
- `python tools/agent/validate_repo.py --scope all`: pass
