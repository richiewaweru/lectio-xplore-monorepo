"""Run the draft SharedLessonDocument through the real Learn and Print adapters (no media bound)."""
import json, sys
from pathlib import Path
sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\apps\textbook-agent\backend\src")
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import SharedDocumentIdentity as LI, realize_shared_document_for_learn
from print.generation.shared_document_adapter import SharedDocumentIdentity as PI, realize_shared_document_for_print
OUT = Path(r"C:\Users\richi\.codex\worktrees\doc36-integration\lectio\docs\doc36-presentation\evidence\phase5\fullrun-photosynthesis")
doc = SharedLessonDocument.model_validate(json.loads((OUT/"shared-document.json").read_text(encoding="utf-8")))
payload = doc.model_dump(mode="json")
stored = StoredSharedLessonDocument(document=doc, path_lesson_id="phase5:photosynthesis", status="ready", storage_hash=content_hash(payload))
ident = {"id": doc.id, "revision": doc.revision, "content_hash": shared_lesson_content_hash(doc)}
learn = realize_shared_document_for_learn(stored, expected_identity=LI(**ident), subject="Science", source_generation_id=None, learn_document_id="phase5:photosynthesis")
(OUT/"learn-v2.json").write_text(json.dumps(learn.document.model_dump(mode="json"), indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
from types import SimpleNamespace
import print.generation.shared_document_adapter as pa
media = [SimpleNamespace(figure_node_id=n.id, asset_url="https://cdn.example.test/figure-placeholder.svg", alt_text=n.accessibility.alt_text or "Figure placeholder", status="ready")
         for sec in doc.sections for n in sec.nodes if getattr(n, "kind", None) == "figure"]
pa.verify_bound_figure_media = lambda m, _d: m  # same bypass Track B's export_shared_lesson_fixture uses
printed = realize_shared_document_for_print(stored, expected_identity=PI(**ident), figure_media=media)
for sec in printed.document.get("sections", []):
    for b in sec.get("blocks", []):
        if b.get("object") == "figure":
            b["content"]["asset"]["src"] = "/phase5-figure-placeholder.svg"
(OUT/"print.json").write_text(json.dumps(printed.document, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
print(ident, "learn nodes", len(learn.document.nodes))
