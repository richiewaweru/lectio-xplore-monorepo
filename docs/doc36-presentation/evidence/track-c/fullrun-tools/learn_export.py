import json
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\apps\textbook-agent\backend\src")
from document.shared_lesson.hashing import shared_lesson_content_hash
from document.shared_lesson.models import SharedLessonDocument
from document.shared_lesson.repository import StoredSharedLessonDocument
from infra.execution.checkpoints import content_hash
from learn.generation.shared_document_adapter import (
    SharedDocumentIdentity as LearnIdentity,
    realize_shared_document_for_learn,
)

OUT = Path(r"C:\Users\richi\.codex\worktrees\doc36-writer\lectio\docs\doc36-presentation\evidence\track-c")
summary = []
for slug, subject in (("photosynthesis", "Science"), ("area", "Mathematics"), ("compare", "Science")):
    raw = json.loads((OUT / f"fullrun-{slug}" / "shared-document.json").read_text(encoding="utf-8"))
    document = SharedLessonDocument.model_validate(raw)
    payload = document.model_dump(mode="json")
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=f"fullrun:{slug}",
        status="ready",
        storage_hash=content_hash(payload),
    )
    identity = {
        "id": document.id,
        "revision": document.revision,
        "content_hash": shared_lesson_content_hash(document),
    }
    learn = realize_shared_document_for_learn(
        stored,
        expected_identity=LearnIdentity(**identity),
        subject=subject,
        source_generation_id=None,
        learn_document_id=f"fullrun:{slug}",
    )
    (OUT / f"fullrun-{slug}" / "learn-v2.json").write_text(
        json.dumps(learn.document.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    summary.append({"run": slug, "shared_hash": identity["content_hash"], "validated": True,
                    "sections": len(document.sections)})
(OUT / "fullrun-format-validation.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(summary)
