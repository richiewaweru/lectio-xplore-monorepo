"""Dry-run helper for whole-lesson guidance (no paid LLM)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from planning.catalogue_projections import project_teaching_guidance
from resource_specs.candidates import assemble_lesson_guidance
from resource_specs.loader import get_spec, load_all_specs
from contracts.lectio_page import get_intent_catalogue, get_object_catalogue
from v3_blueprint.skeletons import load_skeleton_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    load_all_specs()
    spec = get_spec("lesson")
    catalog = load_skeleton_catalog()
    slots = {
        slot_id: {**dict(catalog.slots[slot_id]), "slot_id": slot_id}
        for slot_id in ("orient", "explain", "confront", "check")
        if slot_id in catalog.slots
    }
    guidance = assemble_lesson_guidance(
        resource_spec=spec,
        skeleton_slots=slots,
        intent_catalogue=get_intent_catalogue()["intents"],
        object_catalogue=get_object_catalogue()["objects"],
    )
    teaching = project_teaching_guidance(
        permitted_intent_ids=set(guidance.permitted_intent_ids),
        excluded_intents=guidance.excluded_intents,
    )
    payload = {
        "slots": {
            slot.slot_id: {
                "typical_intents": list(slot.typical_intents),
                "permitted_intent_ids": [item.id for item in slot.permitted_intents],
            }
            for slot in guidance.slots
        },
        "teaching_projection_hash": teaching.projection_hash,
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
