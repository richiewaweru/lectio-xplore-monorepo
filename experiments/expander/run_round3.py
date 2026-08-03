"""Phase 0C timing repeat: 3 with_expander + 3 skip_expander, interleaved.

Uses the identical shared_plan.json and round-2 writer path (no prompt changes).
Saves under experiments/expander/round3/{arm}/run{n}/.

Run from repo root:
  uv run --directory backend python ../experiments/expander/run_round3.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import statistics
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
OUT_DIR = Path(__file__).resolve().parent
ROUND3 = OUT_DIR / "round3"
sys.path.insert(0, str(BACKEND / "src"))

# Load sibling run_ab.py as a module (not a package).
_spec = importlib.util.spec_from_file_location("run_ab", OUT_DIR / "run_ab.py")
assert _spec is not None and _spec.loader is not None
run_ab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_ab)

SCHEDULE = [
    ("with_expander", False, 1),
    ("skip_expander", True, 1),
    ("with_expander", False, 2),
    ("skip_expander", True, 2),
    ("with_expander", False, 3),
    ("skip_expander", True, 3),
]


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.median(values)), 2)


def _minmax(values: list[float]) -> dict | None:
    if not values:
        return None
    return {"min": round(min(values), 2), "max": round(max(values), 2)}


def _aggregate(runs: list[dict]) -> dict:
    ok = [r for r in runs if r.get("ok")]
    stage2 = [r["stage2_seconds"] for r in ok]
    writers = [r["writers_seconds"] for r in ok]
    totals = [r["total_seconds"] for r in ok]

    section_ids: set[str] = set()
    for r in ok:
        section_ids.update((r.get("section_writer_seconds") or {}).keys())
    per_section: dict[str, dict] = {}
    for sid in sorted(section_ids):
        vals = [
            r["section_writer_seconds"][sid]
            for r in ok
            if sid in (r.get("section_writer_seconds") or {})
        ]
        per_section[sid] = {
            "median": _median(vals),
            **(_minmax(vals) or {}),
            "n": len(vals),
            "values": vals,
        }

    return {
        "n_ok": len(ok),
        "n_failed": len(runs) - len(ok),
        "runs": runs,
        "stage2_seconds": {
            "values": stage2,
            "median": _median(stage2),
            **(_minmax(stage2) or {}),
        },
        "writers_seconds": {
            "values": writers,
            "median": _median(writers),
            **(_minmax(writers) or {}),
        },
        "total_seconds": {
            "values": totals,
            "median": _median(totals),
            **(_minmax(totals) or {}),
        },
        "section_writer_seconds": per_section,
    }


async def main() -> int:
    from v3_blueprint.planning.models import StructuralPlan

    shared_path = OUT_DIR / "shared_plan.json"
    if not shared_path.exists():
        raise FileNotFoundError(
            f"Missing {shared_path}; identical plan required for comparable timing."
        )
    shared = json.loads(shared_path.read_text(encoding="utf-8"))
    plan = StructuralPlan.model_validate(shared["plan"])
    roles = [s.role for s in plan.sections]
    section_ids = [s.id for s in plan.sections]
    expected = ["orient", "explain", "model", "apply", "check"]
    if section_ids != expected:
        raise RuntimeError(
            f"shared_plan section ids {section_ids} != round-2 expected {expected}"
        )

    signals, form, resource_spec = run_ab._lesson_inputs()
    print(
        f"[R3] Loaded shared_plan.json roles={roles} section_ids={section_ids}",
        flush=True,
    )

    by_arm: dict[str, list[dict]] = {"with_expander": [], "skip_expander": []}
    affected: list[str] = []

    for arm, skip, run_n in SCHEDULE:
        label = f"round3/{arm}/run{run_n}"
        started_at = datetime.now(timezone.utc).isoformat()
        print(
            f"[R3] START arm={arm} run={run_n} skip={skip} started_at={started_at}",
            flush=True,
        )
        record: dict = {
            "arm": arm,
            "run": run_n,
            "skip_expander": skip,
            "started_at": started_at,
            "ok": False,
        }
        try:
            timings = await run_ab._run_arm(
                label=label,
                skip=skip,
                plan=plan,
                signals=signals,
                form=form,
                resource_spec=resource_spec,
            )
            record.update(
                {
                    "ok": True,
                    "stage2_seconds": timings["stage2_seconds"],
                    "writers_seconds": timings["writers_seconds"],
                    "total_seconds": timings["total_seconds"],
                    "section_writer_seconds": timings["section_writer_seconds"],
                    "failed_briefs": timings.get("failed_briefs", []),
                }
            )
            print(f"[R3] OK arm={arm} run={run_n} timings={timings}", flush=True)
        except Exception as exc:
            err_path = ROUND3 / arm / f"run{run_n}" / "error.json"
            err_path.parent.mkdir(parents=True, exist_ok=True)
            err_payload = {
                "arm": arm,
                "run": run_n,
                "started_at": started_at,
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
                "traceback": traceback.format_exc(),
            }
            run_ab._write_json(err_path, err_payload)
            record["error"] = err_payload
            affected.append(f"{arm}/run{run_n}")
            print(
                f"[R3] FAIL arm={arm} run={run_n} type={type(exc).__name__}: {exc}",
                flush=True,
            )
            # Do not silently retry — fold into affected list only.
        by_arm[arm].append(record)

    with_agg = _aggregate(by_arm["with_expander"])
    skip_agg = _aggregate(by_arm["skip_expander"])
    with_med = with_agg["total_seconds"]["median"]
    skip_med = skip_agg["total_seconds"]["median"]
    delta = None
    if with_med is not None and skip_med is not None:
        delta = round(skip_med - with_med, 2)

    aggregate = {
        "round": 3,
        "plan_source": "shared_plan.json",
        "schedule": [
            {"arm": a, "skip": s, "run": n} for a, s, n in SCHEDULE
        ],
        "affected_runs": affected,
        "with_expander": with_agg,
        "skip_expander": skip_agg,
        "median_to_median_delta_total_seconds": delta,
        "median_to_median_delta_stage2_seconds": (
            round(
                (skip_agg["stage2_seconds"]["median"] or 0)
                - (with_agg["stage2_seconds"]["median"] or 0),
                2,
            )
            if with_agg["stage2_seconds"]["median"] is not None
            and skip_agg["stage2_seconds"]["median"] is not None
            else None
        ),
        "median_to_median_delta_writers_seconds": (
            round(
                (skip_agg["writers_seconds"]["median"] or 0)
                - (with_agg["writers_seconds"]["median"] or 0),
                2,
            )
            if with_agg["writers_seconds"]["median"] is not None
            and skip_agg["writers_seconds"]["median"] is not None
            else None
        ),
        "reading_note": (
            "delta = skip_median - with_median. "
            "Within ~15s -> (a) noise. "
            "Skip slower by more than each arm's own min-max spread -> (b) real. "
            "Skip median faster -> round-2 skip slowdown was outlier."
        ),
    }
    run_ab._write_json(ROUND3 / "timings.json", aggregate)
    print(json.dumps(aggregate, indent=2), flush=True)
    return 1 if affected else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
