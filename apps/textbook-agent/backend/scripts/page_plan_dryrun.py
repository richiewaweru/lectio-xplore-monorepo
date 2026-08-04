"""Fixture dry-run for native page-block planning (no paid LLM by default)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from planning.page_blocks import plan_conceptual_first_exposure_blocks


async def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--paid",
        action="store_true",
        help="Allow paid planner (requires ALLOW_PAID_LLM_TESTS=1 and a wired agent).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    args = parser.parse_args()
    allow_paid = args.paid and os.environ.get("ALLOW_PAID_LLM_TESTS") == "1"
    plans = await plan_conceptual_first_exposure_blocks(allow_paid=allow_paid)
    payload = {
        slot_id: plan.model_dump(mode="json") for slot_id, plan in plans.items()
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"planned_sections={len(plans)} paid={allow_paid}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
