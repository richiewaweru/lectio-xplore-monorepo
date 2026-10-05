"""Script-check one full-lesson run against doc 36 gate G3.

Usage: python g3_eval.py fullrun-<topic>   (run from this directory, with the
backend src on PYTHONPATH so the frozen inline parser can be imported).
Writes fullrun-<topic>/g3-report.json and prints a summary.
"""
import json
import re
import sys
from pathlib import Path

from document.shared_lesson.inline import parse_inline_markup

d = Path(sys.argv[1])
doc = json.loads((d / "shared-document.json").read_text(encoding="utf-8"))
items = json.loads((d / "work-items.json").read_text(encoding="utf-8"))
events = json.loads((d / "events.json").read_text(encoding="utf-8"))
run_id = doc["id"].split(":")[1]  # shared-document:<run>:revision:N
run_items = [w for w in items if w["run_id"] == run_id]
run_events_all = [e for e in events if e["run_id"] == run_id]

PROSE = {"paragraph", "list", "table", "equation", "compare", "quote", "callout"}
BLOCKY = {"equation", "compare", "table", "figure"}


def plain(nodes):
    out = []
    for n in nodes:
        out.append(n["value"] if n["type"] == "text" else plain(n["children"]))
    return "".join(out)


def walk(nodes):
    for n in nodes:
        yield n
        if n["type"] != "text":
            yield from walk(n["children"])


def strings(node):
    """(field path, string) for every learner-facing string in a node."""
    disp = node.get("display") or {}
    res = []
    for key, v in disp.items():
        if isinstance(v, str):
            res.append((key, v))
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, str):
                    res.append((f"{key}[{i}]", x))
                elif isinstance(x, list):
                    for j, y in enumerate(x):
                        if isinstance(y, str):
                            res.append((f"{key}[{i}][{j}]", y))
                elif isinstance(x, dict):
                    for kk, y in x.items():
                        if isinstance(y, str):
                            res.append((f"{key}[{i}].{kk}", y))
    return res


UNI = re.compile("[₀-₉⁰ⁱ⁴-⁹²³¹]")
BARE = re.compile(r"\b(CO2|H2O|O2|C6H12O6|N2)\b|\b(?:mm|cm|km|m)[23]\b")

report = {"run": d.name, "document_id": doc["id"], "sections": [], "totals": {}}
tot = dict(
    paragraph_nodes=0, paragraph_over80_segments=0, strong_spans=0, sub_spans=0, sup_spans=0,
    unicode_subsup=0, bare_formula_or_unit=0, literal_fallbacks=0, equations=0, tables=0, compares=0,
    lists=0, misconception_callouts=0, misconceptions_three_part=0, key_idea_callouts=0, figures=0,
)
literal = []
bare = []
lists_out = []
for s in doc["sections"]:
    nodes = s["nodes"]
    seq = [
        n["kind"] + (":" + n["display"].get("variant", "") if n["kind"] == "callout" else "")
        for n in nodes
    ]
    ki = [i for i, n in enumerate(nodes)
          if n["kind"] == "callout" and n["display"].get("variant") == "key_idea"]
    content_idx = [i for i, n in enumerate(nodes) if n["kind"] in PROSE | {"figure"}]
    first_blocky = next((i for i, n in enumerate(nodes) if n["kind"] in BLOCKY), None)
    first_content = next((i for i, n in enumerate(nodes) if n["kind"] not in {"heading", "task_anchor"}), None)
    sec = {
        "id": s["id"], "title": s["title"], "node_sequence": seq,
        "has_content": bool(content_idx),
        "key_idea_count": len(ki),
        "key_idea_index": ki[0] if ki else None,
        "key_idea_opens_section": bool(ki) and ki[0] == first_content,
        "key_idea_before_blocky": bool(ki) and (first_blocky is None or ki[0] < first_blocky),
        "paragraphs": [],
    }
    for n in nodes:
        k = n["kind"]
        disp = n.get("display") or {}
        if k == "paragraph":
            tot["paragraph_nodes"] += 1
            segs = [x for x in re.split(r"\n\s*\n", disp["text"]) if x.strip()]
            words = [len(plain(parse_inline_markup(x)).split()) for x in segs]
            sec["paragraphs"].append({"id": n["id"], "segments": len(segs),
                                      "words_per_segment": words, "total_words": sum(words)})
            tot["paragraph_over80_segments"] += sum(1 for w in words if w > 80)
        if k == "equation":
            tot["equations"] += 1
        if k == "table":
            tot["tables"] += 1
        if k == "compare":
            tot["compares"] += 1
        if k == "figure":
            tot["figures"] += 1
        if k == "list":
            tot["lists"] += 1
            lists_out.append({"section": s["id"], "node": n["id"], "items": disp.get("items")})
        if k == "callout":
            v = disp.get("variant")
            if v == "key_idea":
                tot["key_idea_callouts"] += 1
            if v == "misconception":
                tot["misconception_callouts"] += 1
                if all((disp.get(x) or "").strip() for x in ("belief", "evidence", "conclusion")):
                    tot["misconceptions_three_part"] += 1
        for path, text in strings(n):
            tree = parse_inline_markup(text)
            for sp in walk(tree):
                if sp["type"] == "strong":
                    tot["strong_spans"] += 1
                if sp["type"] == "subscript":
                    tot["sub_spans"] += 1
                if sp["type"] == "superscript":
                    tot["sup_spans"] += 1
                if sp["type"] == "text" and re.search(r"\*|~|\^", sp["value"]):
                    tot["literal_fallbacks"] += 1
                    literal.append({"node": n["id"], "path": path, "text": sp["value"][:160]})
            pt = plain(tree)
            if UNI.search(text):
                tot["unicode_subsup"] += 1
            for m in BARE.finditer(text):  # raw text: markup-free digits only
                tot["bare_formula_or_unit"] += 1
                bare.append({"node": n["id"], "path": path, "match": m.group(0)})
    report["sections"].append(sec)

summary_markers = re.compile(
    r"^\s*(in summary|to summari[sz]e|overall|remember|so,|key takeaway|in short|to sum up)", re.I)
report["list_items_review"] = lists_out
report["list_summary_marker_hits"] = [
    {**lst, "hits": [i for i in (lst["items"] or []) if summary_markers.search(i)]}
    for lst in lists_out if any(summary_markers.search(i) for i in (lst["items"] or []))
]
report["literal_markup_fallbacks"] = literal
report["bare_formulas_or_units"] = bare
report["totals"] = tot

codes = {}
for e in run_events_all:
    p = e["safe_payload_json"] or {}
    for c in p.get("warning_codes", []) or p.get("codes", []):
        codes.setdefault(e["event_type"], {}).setdefault(c, 0)
        codes[e["event_type"]][c] += 1
report["advisory_event_codes"] = codes
report["diagnostics_in_document"] = doc.get("diagnostics")
report["retried_work_items"] = [
    {"item": w["item_key"], "attempt": w["attempt"]} for w in run_items if int(w["attempt"]) > 1
]
report["failure_events"] = [
    {"seq": e["seq"], "type": e["event_type"], "stage": e["stage"], "code": e["error_code"],
     "payload": e["safe_payload_json"]}
    for e in run_events_all
    if "fail" in e["event_type"] or "retry" in e["event_type"] or "repair" in e["event_type"]
]
(d / "g3-report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(json.dumps({"totals": tot, "retried": report["retried_work_items"],
                  "failure_events": [(f["type"], f["stage"], f["code"]) for f in report["failure_events"]]},
                 indent=1))
for sc in report["sections"]:
    print(sc["id"], sc["node_sequence"], "KI@", sc["key_idea_index"], "opens", sc["key_idea_opens_section"],
          "beforeblocky", sc["key_idea_before_blocky"])
