"""Fallback: assemble the text-only draft from the run's durably accepted composer/writer outputs.

Used only because required-figure media failed (provider_http_401) and doc 35 blocks the Run before
document QA/finalization. Calls the pipeline's own loader and assembler, mutates nothing.
"""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\src")
from core.database.session import async_session_factory
from document.shared_lesson import post_section_pipeline as p
from document.shared_lesson.assembly import assemble_shared_lesson_document
OUT = Path(r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\docs\doc36-presentation\evidence\phase5\fullrun-photosynthesis")
RUN, OWNER, LESSON, GEN = sys.argv[1:5]
async def main():
    loaded = await p._load_post_section_inputs(async_session_factory, run_id=RUN, owner_user_id=OWNER, path_lesson_id=LESSON, preparation_generation_id=GEN)
    run, source, tasks, comps_raw, sections_raw, section_warnings, composition_warnings = loaded
    comps = {c.section_slot_id: c for c in comps_raw}; sections = {s.id: s for s in sections_raw}
    draft = assemble_shared_lesson_document(document_id=f"shared-document:{run.id}:revision:1", revision=1, source=source,
        accepted_sections=sections, tasks=tasks, created_at=p._created_at(run), expected_shapes=p._expected_shapes(comps),
        approved_source_ids=p._source_ids(source), required_media_by_section={}, available_media_ids=())
    (OUT / "shared-document.json").write_text(json.dumps(draft.document.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    rep = {"run_id": run.id, "document_id": draft.document.id, "content_hash": draft.document.content_hash, "deterministic_qa_ready": draft.qa.ready,
           "status": draft.status, "qa": draft.qa.model_dump(mode="json"),
           "section_writer_warnings": {k: [w if isinstance(w, str) else (w.model_dump(mode="json") if hasattr(w, "model_dump") else str(w)) for w in v] for k, v in section_warnings.items()},
           "composition_warnings": {k: [w if isinstance(w, str) else (w.model_dump(mode="json") if hasattr(w, "model_dump") else str(w)) for w in v] for k, v in composition_warnings.items()}}
    (OUT / "draft-assembly.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
    print(draft.status, draft.document.content_hash, len(draft.document.sections))
asyncio.run(main())
