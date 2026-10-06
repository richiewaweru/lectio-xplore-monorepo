"""Word parity: Learn rendered DOM text (per block) vs learner Print PDF text (pdftotext -raw), in order."""
import json, re, subprocess, unicodedata, difflib, sys, io
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = Path(__file__).resolve().parents[1]
PB = r"C:\Users\richi\AppData\Local\Microsoft\WinGet\Packages\oschwartz10612.Poppler_Microsoft.Winget.Source_8wekyb3d8bbwe\poppler-25.07.0\Library\bin"
pdf = HERE / "pdf" / "phase5-photosynthesis-print-student.pdf"
raw = subprocess.check_output([PB + r"\pdftotext.exe", "-raw", str(pdf), "-"], text=True, encoding="utf-8")
doc = json.loads((HERE / "fullrun-photosynthesis" / "shared-document.json").read_text(encoding="utf-8"))
learn = json.loads((HERE / "learn" / "learn-dom-report.json").read_text(encoding="utf-8"))["phase5-photosynthesis@1280"]
def toks(s):
    s = unicodedata.normalize("NFKC", s).replace("\u00ad", "")
    s = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", s)
    return [x.lower() for x in re.findall(r"[A-Za-z0-9]+(?:['\u2019][A-Za-z0-9]+)?", s.replace("\u2019", "'"))]
# strip running footer + page numbers from Print stream
title = doc["title"]
lines = [l for l in raw.splitlines() if l.strip() != title and not re.fullmatch(r"\s*Page \d+ of \d+\s*", l)]
lines = [re.sub(r"^(The belief|The evidence|So)\b\s*", "", l) for l in lines]  # misconception row labels are chrome on both sides
pdf_tokens = toks("\n".join(lines))
CHROME = {"key idea": 2, "the belief": 2, "the evidence": 2}
def clean_learn(kind, text):
    t = text
    t = re.sub(r"(?im)^\s*KEY IDEA\s*$", "", t)
    t = re.sub(r"(?im)^\s*THE (BELIEF|EVIDENCE)\s*$", "", t)
    t = re.sub(r"(?im)^\s*SO\s*$", "", t)
    return t
res = {"blocks": [], "tasks": []}
cursor = 0
ordinary = [b for b in learn["blocks"] if b["kind"] != "interaction"]
# Print stream has key-idea label differences; strip known label tokens from the PDF stream at those positions by matching blocks without labels
for i, b in enumerate(learn["blocks"]):
    if b["kind"] == "interaction":
        continue
    lt = toks(clean_learn(b["kind"], b["text"]))
    if not lt:
        res["blocks"].append({"index": i, "kind": b["kind"], "learn_tokens": 0, "status": "learn renders no text", "detail": "figure with no asset: nothing rendered in Learn (A7); Print renders frame + caption"}); continue
    found = None
    for s in range(cursor, len(pdf_tokens) - len(lt) + 1):
        if pdf_tokens[s:s + len(lt)] == lt:
            found = s; break
    if found is not None:
        cursor = found + len(lt)
        res["blocks"].append({"index": i, "kind": b["kind"], "learn_tokens": len(lt), "status": "identical", "pdf_offset": found})
    else:
        # best-effort alignment against the window after the cursor
        window = pdf_tokens[cursor:cursor + len(lt) + 60]
        sm = difflib.SequenceMatcher(None, lt, window, autojunk=False)
        diffs = [(op, lt[a:b_], window[c:d]) for op, a, b_, c, d in sm.get_opcodes() if op != "equal"]
        res["blocks"].append({"index": i, "kind": b["kind"], "learn_tokens": len(lt), "status": "DIFF", "diffs": diffs[:12], "learn_head": " ".join(lt[:12])})
# tasks: display prompt + options in both outputs
ln_all = " ".join(" ".join(toks(b["text"])) for b in learn["blocks"] if b["kind"] == "interaction")
pdf_all = " ".join(pdf_tokens)
tasks = {t["id"]: t for t in doc["tasks"]}
for t in doc["tasks"]:
    parts = [t.get("display_prompt") or t["prompt"]]
    resp = t.get("response", {}) or {}
    for o in (resp.get("options") or []):
        parts.append(o.get("label") or o.get("text") or "")
    for key in ("pairs",):
        for pr in (resp.get(key) or []): parts += [pr.get("left", ""), pr.get("right", "")]
    miss_l = [p for p in parts if p and " ".join(toks(p)) not in ln_all]
    miss_p = [p for p in parts if p and " ".join(toks(p)) not in pdf_all]
    res["tasks"].append({"task": t["id"], "parts": len(parts), "missing_in_learn": miss_l, "missing_in_print": miss_p})
res["summary"] = {"non_task_blocks": len(res["blocks"]), "identical": sum(1 for b in res["blocks"] if b["status"] == "identical"), "diff": [b for b in res["blocks"] if b["status"] == "DIFF"], "no_learn_text": [b for b in res["blocks"] if b["status"].startswith("learn renders")]}
(HERE / "parity.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(res["summary"], indent=1, ensure_ascii=False)[:4000]); print(json.dumps(res["tasks"], indent=1, ensure_ascii=False)[:3000])
