"""G4: no task prompt repeats more than one sentence of the context above it.

Context compared per task:
  * live run: the real writer inputs available in the live JSON (the bound
    sourcebook entries' text + the plan block brief/evidence). The live run
    authors tasks only, so no authored paragraph exists in that file.
  * golden/live-composed shared documents (g4-numbering-inputs/*.shared.json):
    the actual paragraph/callout/equation node text immediately above each anchor.
A prompt sentence "repeats" a context sentence when normalized token Jaccard
>= 0.8 or one normalized sentence contains the other. Report: count per task.
Standalone (stdlib only): python g4_prompt_overlap.py
"""
import json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent

def norm(t): return re.findall(r"[a-z0-9]+", t.lower())
def sentences(t): return [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", t)) if len(norm(s)) >= 3]
def repeats(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb: return False
    sa, sb = set(na), set(nb)
    if len(sa & sb) / len(sa | sb) >= 0.8: return True
    ja, jb = " ".join(na), " ".join(nb)
    return ja in jb or jb in ja
def overlap(prompt, ctx_sentences):
    return [s for p in sentences(prompt) for s in ctx_sentences if repeats(p, s)]
def texts(obj):
    if isinstance(obj, str): yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("id", "kind", "type", "teaching_block_id"): continue
            yield from texts(v)
    elif isinstance(obj, list):
        for v in obj: yield from texts(v)

rows = []
live = json.loads((HERE / "g4-d-live-photosynthesis-20261005-1852-json.json").read_text(encoding="utf-8"))
blocks = {b["id"]: b for s in live["teaching_plan"]["sections"] for b in s["blocks"]}
entries = {e["id"]: e for e in live["sourcebook"]["entries"]}
for t in live["tasks"]:
    b = blocks[t["teaching_block_id"]]
    ctx = []
    for ref in t["sourcebook_refs"]:
        for x in texts(entries[ref]["content"]): ctx += sentences(x) or [x]
    for x in (b["brief"], b["evidence"], b["learner_action"]["target"]): ctx += sentences(x) or [x]
    hits = overlap(t["display_prompt"], ctx)
    rows.append({"source": "live-run vs sourcebook+plan", "task": t["id"], "display_prompt": t["display_prompt"],
                 "context_sentences": len(ctx), "repeated_sentences": len(hits), "ok": len(hits) <= 1})

for name in ("golden", "legacy", "live"):
    p = HERE / "g4-numbering-inputs" / f"{name}.shared.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    tasks = {t["id"]: t for t in doc["tasks"]}
    prev = None
    for section in doc["sections"]:
        for node in section["nodes"]:
            kind = node.get("kind", node.get("type"))
            if kind == "task_anchor":
                t = tasks[node["task_spec_id"]]
                ctx = [s for x in texts(prev) for s in (sentences(x) or [x])] if prev else []
                prompt = t.get("display_prompt") or t["prompt"]
                hits = overlap(prompt, ctx)
                rows.append({"source": f"{name} shared doc vs paragraph above", "task": t["id"], "display_prompt": prompt,
                             "context_sentences": len(ctx), "repeated_sentences": len(hits), "ok": len(hits) <= 1})
            else:
                prev = node

(HERE / "g4-prompt-overlap-report.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
for r in rows:
    print(f"{'OK ' if r['ok'] else 'FAIL'} [{r['source']}] {r['task']}: repeated={r['repeated_sentences']}/{r['context_sentences']}  \"{r['display_prompt']}\"")
print("ALL OK" if all(r["ok"] for r in rows) else "FAILURES")
