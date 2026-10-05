"""G4 acceptance harness: Q numbers agree across Learn, learner Print, teacher page.

Tracks A/B/D are intentionally not merged, so this harness runs the two real
adapters in separate processes, each against its own track's source tree, over
the SAME stored shared-lesson documents, and compares the numbering they emit.

  Learn side  : this branch (codex/doc36-tasks) -> realize_shared_document_for_learn,
                then the DocumentCanvas.svelte rule (one running counter over
                every top-level `interaction` node in document order).
  Print side  : codex/doc36-print (read-only `git archive` extract) ->
                realize_shared_document_for_print; learner numbers are the
                `Q<n>` block ids / question item ids in section order, teacher
                numbers are the answer_key `question_id`s.  Track B files are
                never modified.

Documents compared: the golden fixture, the legacy fixture (role-absent), and a
"live" document that anchors the three topical live DeepSeek tasks from
g4-d-live-photosynthesis-20261005-1852-json.json into the golden lesson skeleton
(the live run authors tasks only, so the surrounding paragraphs are the golden
fixture's; the tasks, roles and order are the real live output).

Usage (from repo root of the track-d worktree):
  python g4_numbering_harness.py run --print-tree <dir with archived apps/ tree>
Internal modes: build / learn / print (driven by `run`).
Needs JWT_SECRET_KEY set to any 32+ char dummy string (settings import guard).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BACKEND = REPO / "apps" / "textbook-agent" / "backend"
LIVE_JSON = HERE / "g4-d-live-photosynthesis-20261005-1852-json.json"


def _identity(document):
    from document.shared_lesson.hashing import shared_lesson_content_hash

    return {
        "id": document.id,
        "revision": document.revision,
        "content_hash": shared_lesson_content_hash(document),
    }


def build(out_dir: Path) -> None:
    """Write the three shared documents (as stored JSON) the sides will consume."""
    from document.shared_lesson.fixtures import load_shared_lesson_fixture
    from document.shared_lesson.hashing import shared_lesson_content_hash
    from document.shared_lesson.models import SharedLessonDocument

    out_dir.mkdir(parents=True, exist_ok=True)
    docs = {}
    for name in ("golden", "legacy"):
        docs[name] = load_shared_lesson_fixture(name).model_dump(mode="json")
        # Print admission requires produced figure media; figures carry no task
        # numbering, so drop them from the harness copy (hash recomputed below).
        for section in docs[name]["sections"]:
            section["nodes"] = [n for n in section["nodes"] if n.get("kind", n.get("type")) != "figure"]
        docs[name]["content_hash"] = "0" * 64
        probe = SharedLessonDocument.model_validate(docs[name], context={"skip_content_hash_validation": True})
        docs[name]["content_hash"] = shared_lesson_content_hash(probe)

    live = json.loads(LIVE_JSON.read_text(encoding="utf-8"))
    golden = json.loads(json.dumps(docs["golden"]))
    paragraphs = [
        node
        for section in golden["sections"]
        for node in section["nodes"]
        if node.get("kind", node.get("type")) == "paragraph"
    ]
    # Rebuild: keep golden's non-task nodes, drop its anchors/tasks, then place one
    # live anchor after each of three successive paragraphs (live order preserved).
    live_tasks = live["tasks"]
    for section in golden["sections"]:
        section["nodes"] = [n for n in section["nodes"] if n.get("kind", n.get("type")) != "task_anchor"]
    targets = [paragraphs[0], paragraphs[3], paragraphs[-1]]
    for task, target in zip(live_tasks, targets):
        for section in golden["sections"]:
            for i, node in enumerate(section["nodes"]):
                if node["id"] == target["id"]:
                    anchor = {
                        "kind": "task_anchor",
                        "id": f"anchor-{task['id']}",
                        "task_spec_id": task["id"],
                        "teaching_block_id": task["teaching_block_id"],
                    }
                    section["nodes"].insert(i + 1, anchor)
                    break
            else:
                continue
            break
    golden["id"] = "shared-document:g4-live-photosynthesis:revision:1"
    golden["tasks"] = live_tasks
    golden["teaching_plan_id"] = live["teaching_plan"]["teaching_plan_id"]
    golden["teaching_plan_revision"] = live["teaching_plan"]["revision"]
    golden["teaching_plan_hash"] = live_tasks[0]["teaching_plan_hash"]
    golden["content_hash"] = "0" * 64
    probe = SharedLessonDocument.model_validate(golden, context={"skip_content_hash_validation": True})
    golden["content_hash"] = shared_lesson_content_hash(probe)
    docs["live"] = SharedLessonDocument.model_validate(golden).model_dump(mode="json")
    for name, payload in docs.items():
        (out_dir / f"{name}.shared.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")


def _load_stored(path: Path):
    from document.shared_lesson.models import SharedLessonDocument
    from document.shared_lesson.repository import StoredSharedLessonDocument
    from infra.execution.checkpoints import content_hash

    document = SharedLessonDocument.model_validate_json(path.read_text(encoding="utf-8"))
    stored = StoredSharedLessonDocument(
        document=document,
        path_lesson_id=f"g4:{path.stem}",
        status="ready",
        storage_hash=content_hash(document.model_dump(mode="json")),
    )
    return document, stored


def learn_side(in_dir: Path) -> dict:
    from learn.generation.shared_document_adapter import (
        SharedDocumentIdentity,
        realize_shared_document_for_learn,
    )

    result = {}
    for path in sorted(in_dir.glob("*.shared.json")):
        document, stored = _load_stored(path)
        learn = realize_shared_document_for_learn(
            stored,
            expected_identity=SharedDocumentIdentity(**_identity(document)),
            subject="Science",
            source_generation_id=None,
            learn_document_id=f"g4:{path.stem}",
        ).document.model_dump(mode="json")
        counter = 0
        rows = []
        # DocumentCanvas.svelte: questionNumbers = running ++number over interaction nodes.
        for node in learn["nodes"]:
            if node["kind"] == "interaction":
                counter += 1
                rows.append({"q": counter, "node_id": node["id"], "interaction": node.get("interaction_kind") or node.get("interaction", {}).get("kind")})
        result[path.name.split(".")[0]] = rows
    return result


def print_side(in_dir: Path) -> dict:
    from print.generation.shared_document_adapter import (
        SharedDocumentIdentity,
        realize_shared_document_for_print,
    )

    result = {}
    for path in sorted(in_dir.glob("*.shared.json")):
        document, stored = _load_stored(path)
        printed = realize_shared_document_for_print(
            stored, expected_identity=SharedDocumentIdentity(**_identity(document))
        ).document
        learner = []
        for section in printed["sections"]:
            for block in section["blocks"]:
                if block.get("object") == "questions" or block.get("object_id") in {"questions", "choices"} or str(block.get("id", "")).startswith("Q"):
                    learner.append(block["id"])
        teacher = [
            e["question_id"]
            for g in ((printed.get("answer_key") or {}).get("content", {}).get("groups", []))
            for e in g.get("entries", [])
        ]
        meta = [m["label"] for m in printed["metadata"].get("shared_tasks", [])]
        anchors = [m["anchor_id"] for m in printed["metadata"].get("shared_tasks", [])]
        result[path.name.split(".")[0]] = {"learner": learner, "teacher": teacher, "metadata_labels": meta, "anchor_ids": anchors, "answer_key_keys": list((printed.get("answer_key") or {}).keys())}
    return result


def run(print_tree: Path, out_dir: Path) -> int:
    work = out_dir / "g4-numbering-inputs"
    env_base = {**os.environ, "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY") or "x" * 64}
    me = [sys.executable, str(Path(__file__).resolve())]
    learn_env = {**env_base, "PYTHONPATH": str(BACKEND / "src")}
    print_env = {**env_base, "PYTHONPATH": str(print_tree / "apps" / "textbook-agent" / "backend" / "src")}
    subprocess.run([*me, "build", "--dir", str(work)], check=True, env=learn_env)
    learn = json.loads(subprocess.run([*me, "learn", "--dir", str(work)], check=True, env=learn_env, capture_output=True, text=True).stdout)
    printed = json.loads(subprocess.run([*me, "print", "--dir", str(work)], check=True, env=print_env, capture_output=True, text=True).stdout)
    report = {"documents": {}, "all_match": True}
    for name in sorted(learn):
        learn_q = [f"Q{row['q']}" for row in learn[name]]
        p = printed[name]
        # Same label sequence AND the same task behind each label (Learn node id == anchor id).
        same_tasks = [row["node_id"] for row in learn[name]] == p["anchor_ids"]
        match = learn_q == p["learner"] == p["teacher"] == p["metadata_labels"] and same_tasks
        report["documents"][name] = {
            "learn": learn_q,
            "print_learner": p["learner"],
            "print_teacher_answer_key": p["teacher"],
            "print_task_metadata": p["metadata_labels"],
            "learn_detail": learn[name],
            "print_anchor_ids": p["anchor_ids"],
            "match": match,
        }
        report["all_match"] = report["all_match"] and match
    (out_dir / "g4-numbering-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for name, row in report["documents"].items():
        print(f"{name:7s} learn={row['learn']} print={row['print_learner']} teacher={row['print_teacher_answer_key']} match={row['match']}")
    print("ALL MATCH" if report["all_match"] else "MISMATCH")
    return 0 if report["all_match"] else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "build", "learn", "print"])
    ap.add_argument("--dir", type=Path)
    ap.add_argument("--print-tree", type=Path)
    args = ap.parse_args()
    if args.mode == "run":
        sys.exit(run(args.print_tree, HERE))
    if args.mode == "build":
        build(args.dir)
    elif args.mode == "learn":
        print(json.dumps(learn_side(args.dir)))
    else:
        print(json.dumps(print_side(args.dir)))
