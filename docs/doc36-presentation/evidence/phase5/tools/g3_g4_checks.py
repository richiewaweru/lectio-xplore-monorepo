import json, re, sys, io, difflib
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = Path(__file__).resolve().parents[1]
doc = json.loads((H/"fullrun-photosynthesis/shared-document.json").read_text(encoding="utf-8"))
plan = json.loads((H/"fullrun-photosynthesis/05-teaching-plan.json").read_text(encoding="utf-8"))
tasks = {t["id"]: t for t in doc["tasks"]}
EXPL = {"explain","explain-cause","trace-flow","show-structure","demonstrate","derive","define","name-parts","model-thinking"}
# section intents from teaching plan
secs = (plan.get("teaching_plan") or plan.get("plan") or plan).get("sections") if isinstance(plan, dict) else None
def find_sections(o):
    if isinstance(o, dict):
        if "sections" in o and isinstance(o["sections"], list) and o["sections"] and isinstance(o["sections"][0], dict) and "blocks" in o["sections"][0]: return o["sections"]
        for v in o.values():
            r = find_sections(v)
            if r: return r
    if isinstance(o, list):
        for v in o:
            r = find_sections(v)
            if r: return r
secs = find_sections(plan) or []
intents = {s.get("id") or s.get("slot_id"): sorted({b.get("intent") for b in s["blocks"]}) for s in secs}
def txt(v):
    if isinstance(v, str): return v
    if isinstance(v, dict): return " ".join(txt(x) for x in v.values())
    if isinstance(v, list): return " ".join(txt(x) for x in v)
    return ""
def plain(s): return re.sub(r"\*\*|(?<=\w)[~^]|[~^](?=\w)", "", s)
def sentences(s): return [x.strip() for x in re.split(r"(?<=[.!?])\s+", plain(s)) if x.strip()]
norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()
out = {"key_idea": [], "task_overlap": [], "section_intents": intents}
for s in doc["sections"]:
    first = s["nodes"][0] if s["nodes"] else {}
    d = first.get("display", {})
    opens = first.get("kind") == "callout" and d.get("variant") == "key_idea"
    filled = opens and bool((d.get("body") or "").strip())
    explaining = bool(EXPL & set(intents.get(s["id"], [])))
    # words in key idea
    body = d.get("body") or ""
    out["key_idea"].append({"section": s["id"], "title": s.get("title"), "explaining": explaining, "intents": intents.get(s["id"]), "opens_with_key_idea_callout": opens, "filled": filled,
        "key_idea_words": len(plain(body).split()) if opens else None,
        "first_node": first.get("kind"), "other_key_ideas": sum(1 for n in s["nodes"][1:] if n["kind"]=="callout" and n["display"].get("variant")=="key_idea")})
for s in doc["sections"]:
    prev_para = None
    for n in s["nodes"]:
        if n["kind"] == "paragraph": prev_para = n["display"]["text"]
        if n["kind"] == "task_anchor":
            t = tasks[n["task_spec_id"]]
            dp = t.get("display_prompt") or t["prompt"]
            psents = {norm(x) for x in sentences(prev_para or "")}
            rep = [x for x in sentences(dp) if norm(x) in psents]
            # fuzzy: sentence ratio >= .9
            fuzzy = [x for x in sentences(dp) if any(difflib.SequenceMatcher(None, norm(x), p).ratio() >= .9 for p in psents)]
            out["task_overlap"].append({"task": t["id"], "role": t.get("role"), "display_prompt_words": len(dp.split()), "prompt_sentences": len(sentences(dp)), "sentences_repeating_prior_paragraph_exact": len(rep), "fuzzy_repeats": len(fuzzy), "prior_paragraph_present": prev_para is not None, "display_prompt": dp})
# G4 feedback strings
bad = []
for t in doc["tasks"]:
    fb = t.get("feedback") or {}
    for k, v in fb.items():
        if isinstance(v, str) and v.strip() in {"Correct.", "Not yet — try again.", "Not yet - try again."}: bad.append((t["id"], k, v))
out["generic_feedback"] = bad
out["task_roles"] = {t["id"]: t.get("role") for t in doc["tasks"]}
(H/"g3_g4_checks.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(out, indent=1, ensure_ascii=False))
