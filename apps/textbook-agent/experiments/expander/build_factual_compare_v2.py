"""Build factual_compare_v2.json: round1 with_expander + round2 both arms."""

from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parent

SECTION_ORDER = ["orient", "explain", "model", "apply", "check"]


def _arm_report(prose: dict, briefs: list, timings: dict | None) -> dict:
    arm: dict = {
        "briefs": [],
        "sections": {},
        "timings": timings,
        "anchor_hit_count": 0,
        "role_order": [],
        "failed_briefs": [],
    }
    for brief in briefs:
        arm["briefs"].append(
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
        if brief.get("_failed"):
            arm["failed_briefs"].append(brief["section_id"])

    for sid in SECTION_ORDER:
        sec = prose.get(sid)
        if sec is None:
            continue
        text = json.dumps(sec.get("blocks"), ensure_ascii=False).lower()
        anchor_hit = ("windowsill" in text) or ("window" in text)
        if anchor_hit:
            arm["anchor_hit_count"] += 1
        m1 = "soil" in text
        m2 = ("breath" in text) or ("opposite" in text)
        arm["sections"][sid] = {
            "role": sec.get("role"),
            "title": sec.get("title"),
            "transition_note": sec.get("transition_note"),
            "anchor_hit": anchor_hit,
            "misconception_M1_soil": m1,
            "misconception_M2_breath_or_opposite": m2,
            "exclusion_violations": [],  # none declared on this plan
            "text_chars": len(text),
        }
        arm["role_order"].append(sec.get("role"))
    arm["roles_match_plan"] = arm["role_order"] == [
        "orient",
        "explain",
        "model",
        "apply",
        "check",
    ]
    return arm


def _load_arm(name: str) -> dict:
    prose = json.loads((root / name / "prose.json").read_text(encoding="utf-8"))
    briefs = json.loads((root / name / "briefs.json").read_text(encoding="utf-8"))
    timings_path = root / name / "timings.json"
    timings = (
        json.loads(timings_path.read_text(encoding="utf-8"))
        if timings_path.exists()
        else None
    )
    return _arm_report(prose, briefs, timings)


def main() -> None:
    summary_v2 = {}
    summary_v2_path = root / "summary_v2.json"
    if summary_v2_path.exists():
        summary_v2 = json.loads(summary_v2_path.read_text(encoding="utf-8"))

    report = {
        "round": 2,
        "plan_source": "shared_plan.json",
        "exclusions_declared": [],
        "note": (
            "Exclusions list empty on this fixed plan (repair_focus null). "
            "No exclusion-violation checks apply."
        ),
        "summary_v2": summary_v2,
        "arms": {
            "with_expander": _load_arm("with_expander"),
            "with_expander_v2": _load_arm("with_expander_v2"),
            "skip_expander_v2": _load_arm("skip_expander_v2"),
        },
    }

    # Headline table for progress file consumers
    report["anchor_counts"] = {
        name: data["anchor_hit_count"] for name, data in report["arms"].items()
    }
    report["apply_misconception"] = {
        name: {
            "M1_soil": data["sections"].get("apply", {}).get("misconception_M1_soil"),
            "M2_breath_or_opposite": data["sections"]
            .get("apply", {})
            .get("misconception_M2_breath_or_opposite"),
        }
        for name, data in report["arms"].items()
    }

    out = root / "factual_compare_v2.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out}")
    print("anchor_counts", report["anchor_counts"])
    print("apply_misconception", report["apply_misconception"])


if __name__ == "__main__":
    main()
