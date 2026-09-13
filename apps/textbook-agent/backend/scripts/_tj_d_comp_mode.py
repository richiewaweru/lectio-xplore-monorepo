"""Lookup composition_mode for Treasure Joe Phase D Learn output."""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import text

from core.database.session import async_session_factory
from core.policies.loader import is_known_learner_action


async def main() -> int:
    learn_id = sys.argv[1] if len(sys.argv) > 1 else "learn-out-c39225773acd"
    actions = json.loads(sys.argv[2]) if len(sys.argv) > 2 else []
    unknown = [a for a in actions if a and not is_known_learner_action(a)]
    async with async_session_factory() as session:
        row = (
            await session.execute(
                text(
                    "SELECT id, status, chunked_state_json FROM generations WHERE id = :id"
                ),
                {"id": learn_id},
            )
        ).first()
        if row is None:
            # EditableLesson / learn outputs may live elsewhere
            print(json.dumps({"found": False, "unknown": unknown, "actions": actions}))
            return 0
        state = row[2] or {}
        if isinstance(state, str):
            state = json.loads(state)
        mode = state.get("composition_mode")
        plan = state.get("composition_plan") or {}
        if not mode and isinstance(plan, dict):
            mode = plan.get("composition_mode")
        if not mode:
            trace = state.get("selection_trace") or {}
            if isinstance(trace, dict):
                nested = trace.get("composition_plan") or {}
                if isinstance(nested, dict):
                    mode = nested.get("composition_mode")
                    plan = nested
        print(
            json.dumps(
                {
                    "found": True,
                    "id": row[0],
                    "status": row[1],
                    "composition_mode": mode,
                    "state_keys": sorted(state.keys())[:40],
                    "unknown": unknown,
                    "actions": actions,
                    "selection_modes": [
                        d.get("selection_mode")
                        for d in (plan.get("decisions") or [])
                        if isinstance(d, dict)
                    ][:20]
                    if isinstance(plan, dict)
                    else [],
                },
                default=str,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
