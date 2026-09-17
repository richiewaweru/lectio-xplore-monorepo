#!/usr/bin/env python3
"""Scan sources for P00-B05 capability inventory facts."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"c:\Projects\lectio")
LEARN_COMP = ROOT / "packages/lectio-learn/src/lib/lectio/components"
LEARN_SHELLS = ROOT / "packages/lectio-learn/src/lib/learn"
EDIT_SCHEMAS = ROOT / "packages/lectio-learn/src/lib/teacher/edit-schemas.ts"
CONTENT_CONTRACT = ROOT / "apps/textbook-agent/backend/contracts/lectio-content-contract.json"
OBJECT_CAT = ROOT / "packages/lectio-page/contracts/object-catalogue.v1.json"
LECTIO_PY = ROOT / "apps/textbook-agent/backend/src/learn/contracts/lectio.py"
BUILD_CC = ROOT / "packages/lectio-learn/src/lib/lectio/build-content-contract.ts"
INDEX_TS = ROOT / "packages/lectio-learn/src/lib/index.ts"


def edit_schema_ids() -> set[str]:
    text = EDIT_SCHEMAS.read_text(encoding="utf-8")
    return set(re.findall(r"component_id:\s*'([a-z0-9-]+)'", text))


def main() -> None:
    cc = json.loads(CONTENT_CONTRACT.read_text(encoding="utf-8"))
    planner = set(cc.get("planner_index", {}).get("component_ids", []))
    cards = cc.get("component_cards", {})
    print("=== CONTENT CONTRACT ===")
    print("top keys", list(cc.keys()))
    print("planner", sorted(planner))
    print("card count", len(cards) if isinstance(cards, dict) else type(cards))
    if isinstance(cards, dict):
        for cid, card in sorted(cards.items()):
            print(
                f"  {cid}: writer_excluded={card.get('writer_excluded')} "
                f"keys={list(card.keys())[:12]}"
            )

    es = edit_schema_ids()
    print("\n=== EDIT SCHEMAS ===")
    print(sorted(es))

    print("\n=== LEARN COMPONENTS ===")
    for d in sorted(LEARN_COMP.iterdir()):
        if not d.is_dir():
            continue
        files = {p.name for p in d.iterdir() if p.is_file()}
        meta = {}
        mp = d / "metadata.ts"
        if mp.exists():
            mt = mp.read_text(encoding="utf-8")
            mid = re.search(r"id:\s*'([^']+)'", mt)
            mjob = re.search(r"cognitive_job:\s*'([^']+)'", mt)
            mtype = re.search(r"type:\s*'([^']+)'", mt)
            mis_media = "isMedia: true" in mt or "isMedia:true" in mt
            meta = {
                "id": mid.group(1) if mid else None,
                "cognitive_job": mjob.group(1) if mjob else None,
                "type": mtype.group(1) if mtype else None,
                "isMedia": mis_media,
            }
        print(
            f"{d.name}: schema={'schema.ts' in files} examples={'examples.ts' in files} "
            f"cc={'content-contract.ts' in files} renderer={'Component.svelte' in files} "
            f"in_planner={d.name in planner} edit={d.name in es} "
            f"card={d.name in cards if isinstance(cards, dict) else False} meta={meta}"
        )

    print("\n=== INTERACTION SHELLS ===")
    for p in sorted(LEARN_SHELLS.glob("*Interaction.svelte")):
        text = p.read_text(encoding="utf-8")
        print(
            f"{p.name}: lines={len(text.splitlines())} "
            f"evaluate={'evaluate' in text} button={'<button' in text} "
            f"select={'<select' in text} input={'<input' in text} "
            f"aria={'aria-' in text}"
        )

    print("\n=== INDEX EXPORTS mention interaction-contract ===")
    idx = INDEX_TS.read_text(encoding="utf-8")
    for name in [
        "evaluateChoice",
        "evaluateMultiSelect",
        "evaluateFillBlank",
        "evaluateNumeric",
        "evaluateMatchPairs",
        "evaluateSequence",
        "evaluateInteraction",
        "LearnInteractionContract",
        "quizContentToInteractionContract",
        "fillBlankContentToInteractionContract",
    ]:
        print(f"  {name}: {name in idx}")

    print("\n=== MANUAL_ONLY from lectio.py ===")
    py = LECTIO_PY.read_text(encoding="utf-8")
    m = re.search(r"MANUAL_ONLY_COMPONENT_IDS\s*=\s*\{([^}]+)\}", py)
    print(m.group(0) if m else "not found")

    print("\n=== OBJECT CATALOGUE / page forms ===")
    obj = json.loads(OBJECT_CAT.read_text(encoding="utf-8"))
    for oid in obj["objects"]:
        print(oid)

    # page renderers
    views = list((ROOT / "packages/lectio-page/src/lib/render/objects").glob("*View.svelte"))
    print("views", sorted(v.stem for v in views))

    # examples for page?
    fixtures = list((ROOT / "packages/lectio-page/fixtures").glob("*.json"))
    print("fixtures", [f.name for f in fixtures])


if __name__ == "__main__":
    main()
