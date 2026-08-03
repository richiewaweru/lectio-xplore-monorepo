import json
from pathlib import Path

root = Path(__file__).resolve().parent
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
report: dict = {"summary": summary, "arms": {}}

for arm in ["with_expander", "skip_expander"]:
    prose = json.loads((root / arm / "prose.json").read_text(encoding="utf-8"))
    briefs = json.loads((root / arm / "briefs.json").read_text(encoding="utf-8"))
    arm_report = {"briefs": [], "sections": {}}
    for brief in briefs:
        arm_report["briefs"].append(
            {
                "section_id": brief["section_id"],
                "intents": [
                    {
                        "component_id": c["component_id"],
                        "content_intent": c["content_intent"],
                    }
                    for c in brief.get("components", [])
                ],
            }
        )
    for sid, sec in prose.items():
        text = json.dumps(sec.get("blocks"), ensure_ascii=False).lower()
        arm_report["sections"][sid] = {
            "role": sec.get("role"),
            "title": sec.get("title"),
            "transition_note": sec.get("transition_note"),
            "anchor_windowsill": ("windowsill" in text) or ("window" in text),
            "mentions_glucose": "glucose" in text,
            "mentions_soil": "soil" in text,
            "mentions_chlorophyll": "chlorophyll" in text,
            "mentions_breath_or_opposite": ("breath" in text) or ("opposite" in text),
            "text_chars": len(text),
            "component_intents": sec.get("components"),
        }
    report["arms"][arm] = arm_report

(root / "factual_compare.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)
print("wrote factual_compare.json")
