"""Compare the single-call and staged teaching planners on local lessons.

For each ``--generation-id`` this script builds the lesson packet and legality
snapshot from the local database (the same way ``run_and_persist_teaching_plan``
does), then runs ``run_lesson_approach_planner`` (single) and
``run_staged_teaching_planner`` (staged) directly and writes both plans plus a
comparison report: wall-clock per mode and per LLM call, attempts, flags,
validation issues, block ids carrying ``visual``, and a section-by-section diff.

It writes NOTHING to the database: no repo writes, no commit (the session is
rolled back), and the planners run with ``generation_id=None`` so no
``llm_calls`` rows are attributed to the generation. It DOES call the real
models, so it costs money.

Run locally::

    cd apps/textbook-agent/backend
    uv run python scripts/compare_teaching_planners.py --generation-id <id>
    uv run python scripts/compare_teaching_planners.py \
        --generation-id <id1> --generation-id <id2> --modes single,staged --repeat 2

Output lands in ``backend/outputs/planner-compare/<id>/`` (``single.json``,
``staged.json``, ``report.md``) plus ``summary.md`` one level up. That folder is
gitignored. The outputs contain real lesson content and generation ids: never
commit them (the repo is public).
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Awaitable, Callable

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR / "src") not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR / "src"))

DEFAULT_OUT = BACKEND_DIR / "outputs" / "planner-compare"
MODES = ("single", "staged")

# Modules that bind ``run_llm`` by name; patched while a planner runs.
_RUN_LLM_MODULES = (
    "application.unit_lesson.teaching_planner",
    "application.unit_lesson.staged_teaching_planner",
    "curriculum.agents",
)


# --------------------------------------------------------------------------- recording


class LlmRecorder:
    """Wrap ``run_llm`` in every importing module and record each call."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._saved: list[tuple[Any, Any]] = []

    @staticmethod
    def _usage(result: Any) -> dict[str, int | None]:
        out: dict[str, int | None] = {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
        }
        try:
            usage = result.usage() if callable(getattr(result, "usage", None)) else None
        except Exception:  # noqa: BLE001 - usage is best effort
            usage = None
        if usage is None:
            return out
        for key, names in (
            ("input_tokens", ("input_tokens", "request_tokens")),
            ("output_tokens", ("output_tokens", "response_tokens")),
            ("total_tokens", ("total_tokens",)),
        ):
            for name in names:
                value = getattr(usage, name, None)
                if isinstance(value, int):
                    out[key] = value
                    break
        if out["total_tokens"] is None and out["input_tokens"] is not None:
            out["total_tokens"] = out["input_tokens"] + (out["output_tokens"] or 0)
        return out

    def wrap(self, real: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        async def recorded(**kwargs: Any) -> Any:
            rec: dict[str, Any] = {
                "caller": kwargs.get("caller"),
                "node": kwargs.get("node") or kwargs.get("caller"),
                "trace_id": kwargs.get("trace_id"),
                "attempt": kwargs.get("attempt_start", 1),
                "latency_s": None,
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
                "error": None,
            }
            started = time.perf_counter()
            try:
                result = await real(**kwargs)
            except BaseException as exc:
                rec["latency_s"] = round(time.perf_counter() - started, 4)
                rec["error"] = f"{type(exc).__name__}: {exc}"[:500]
                self.records.append(rec)
                raise
            rec["latency_s"] = round(time.perf_counter() - started, 4)
            rec.update(self._usage(result))
            self.records.append(rec)
            return result

        return recorded

    def install(self) -> None:
        import importlib

        for name in _RUN_LLM_MODULES:
            module = importlib.import_module(name)
            real = getattr(module, "run_llm", None)
            if real is None:
                continue
            self._saved.append((module, real))
            setattr(module, "run_llm", self.wrap(real))

    def restore(self) -> None:
        for module, real in self._saved:
            setattr(module, "run_llm", real)
        self._saved.clear()

    def __enter__(self) -> "LlmRecorder":
        self.install()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.restore()


# --------------------------------------------------------------------------- inputs


async def load_inputs(generation_id: str) -> tuple[Any, Any]:
    """Build (packet, legality) read-only. Never commits; always rolls back."""
    from core.database.models import GenerationModel
    from core.database.session import async_session_factory
    from application.unit_lesson.teaching_plan_service import build_packet_for_generation
    from print.generation.whole_lesson.legality import (
        build_lesson_legality_snapshot,
        validate_legality_snapshot,
    )

    async with async_session_factory() as session:
        try:
            generation = await session.get(GenerationModel, generation_id)
            if generation is None:
                raise KeyError(generation_id)
            packet = await build_packet_for_generation(session, generation, require_items=True)
            legality = build_lesson_legality_snapshot(packet)
            validate_legality_snapshot(packet, legality)
            return packet, legality
        finally:
            await session.rollback()


# --------------------------------------------------------------------------- running


def _summarize_attempts(attempts: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "attempt": getattr(a, "attempt", None),
            "error": (str(a.error)[:500] if getattr(a, "error", None) else None),
            "assembled": getattr(a, "plan", None) is not None,
        }
        for a in attempts
    ]


async def run_mode(mode: str, packet: Any, legality: Any, generation_id: str) -> dict[str, Any]:
    """Run one planner and return a JSON-able result dict (errors are captured)."""
    if mode == "single":
        from application.unit_lesson.teaching_planner import run_lesson_approach_planner as run
    elif mode == "staged":
        from application.unit_lesson.staged_teaching_planner import run_staged_teaching_planner as run
    else:
        raise ValueError(f"unknown mode {mode!r}")

    out: dict[str, Any] = {
        "mode": mode,
        "generation_id": generation_id,
        "ok": False,
        "wall_s": None,
        "error": None,
        "plan": None,
        "validation": None,
        "qc": [],
        "flags": [],
        "stage_timings": {},
        "attempts": [],
        "llm_calls": [],
    }
    recorder = LlmRecorder()
    started = time.perf_counter()
    with recorder:
        try:
            result = await run(
                packet,
                legality=legality,
                trace_id=f"planner-compare:{generation_id}:{mode}",
                generation_id=None,
            )
        except Exception as exc:  # noqa: BLE001 - record, do not abort the comparison
            out["error"] = {
                "type": type(exc).__name__,
                "message": str(exc)[:1000],
                "details": [str(d)[:500] for d in (getattr(exc, "details", None) or [])],
                "attempt_count": getattr(exc, "attempt_count", None),
            }
        else:
            out["ok"] = True
            out["plan"] = result.plan.model_dump(mode="json")
            out["validation"] = result.validation.to_dict()
            out["qc"] = result.qc
            out["flags"] = result.flags
            out["stage_timings"] = result.stage_timings
            out["attempts"] = _summarize_attempts(result.attempts)
    out["wall_s"] = round(time.perf_counter() - started, 4)
    out["llm_calls"] = recorder.records
    return out


# --------------------------------------------------------------------------- report (pure)


def _fmt(value: Any) -> str:
    return "-" if value is None else str(value)


def _escape(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _sections(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    return list(((result or {}).get("plan") or {}).get("sections") or [])


def visual_blocks(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Blocks carrying ``visual`` as ``{slot_id, block_id, figure_ref}``."""
    found = []
    for section in _sections(result):
        for block in section.get("blocks") or []:
            visual = block.get("visual")
            if visual:
                found.append(
                    {
                        "slot_id": section.get("slot_id"),
                        "block_id": block.get("id"),
                        "figure_ref": visual.get("figure_ref") if isinstance(visual, dict) else None,
                    }
                )
    return found


def _section_summary(section: dict[str, Any] | None) -> dict[str, Any]:
    if section is None:
        return {
            "display_title": None,
            "block_count": 0,
            "intents": [],
            "source_question_ids": [],
            "visual_block_ids": [],
        }
    blocks = section.get("blocks") or []
    sources: list[str] = []
    for block in blocks:
        for qid in block.get("source_question_ids") or []:
            if qid not in sources:
                sources.append(qid)
    return {
        "display_title": section.get("display_title"),
        "block_count": len(blocks),
        "intents": [b.get("intent") for b in blocks],
        "source_question_ids": sources,
        "visual_block_ids": [b.get("id") for b in blocks if b.get("visual")],
    }


def _trimmed_section_json(section: dict[str, Any] | None, limit: int = 160) -> list[str]:
    def trim(value: Any) -> Any:
        if isinstance(value, str):
            return value if len(value) <= limit else value[:limit] + "..."
        if isinstance(value, list):
            return [trim(v) for v in value]
        if isinstance(value, dict):
            return {k: trim(v) for k, v in value.items()}
        return value

    if section is None:
        return []
    return json.dumps(trim(section), indent=2, sort_keys=True).splitlines()


def section_diff(single: dict[str, Any] | None, staged: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Per-slot side-by-side summary plus a trimmed unified diff of section JSON."""
    by_slot_single = {s.get("slot_id"): s for s in _sections(single)}
    by_slot_staged = {s.get("slot_id"): s for s in _sections(staged)}
    order: list[str] = []
    for source in (_sections(single), _sections(staged)):
        for section in source:
            slot = section.get("slot_id")
            if slot not in order:
                order.append(slot)
    rows = []
    for slot in order:
        a, b = by_slot_single.get(slot), by_slot_staged.get(slot)
        diff = list(
            difflib.unified_diff(
                _trimmed_section_json(a),
                _trimmed_section_json(b),
                fromfile=f"single/{slot}",
                tofile=f"staged/{slot}",
                lineterm="",
                n=1,
            )
        )
        rows.append(
            {
                "slot_id": slot,
                "single": _section_summary(a),
                "staged": _section_summary(b),
                "diff": diff,
            }
        )
    return rows


def _mode_section(result: dict[str, Any] | None, label: str) -> list[str]:
    lines = [f"## {label}", ""]
    if result is None:
        return lines + ["Not run.", ""]
    status = "ok" if result.get("ok") else "FAILED"
    lines.append(f"- Status: {status}")
    lines.append(f"- Wall-clock: {_fmt(result.get('wall_s'))} s")
    err = result.get("error")
    if err:
        lines.append(f"- Error: {err.get('type')}: {_escape(err.get('message'))}")
        for detail in err.get("details") or []:
            lines.append(f"  - {_escape(detail)}")
    calls = result.get("llm_calls") or []
    total_tokens = sum(c.get("total_tokens") or 0 for c in calls)
    lines.append(f"- LLM calls: {len(calls)} (total tokens {total_tokens or '-'})")
    lines.append("")
    lines += [
        "### LLM calls",
        "",
        "| caller | attempt | latency_s | in tokens | out tokens | total | error |",
        "|---|---|---|---|---|---|---|",
    ]
    for c in calls:
        lines.append(
            f"| {_escape(_fmt(c.get('caller')))} | {_fmt(c.get('attempt'))} | {_fmt(c.get('latency_s'))} "
            f"| {_fmt(c.get('input_tokens'))} | {_fmt(c.get('output_tokens'))} "
            f"| {_fmt(c.get('total_tokens'))} | {_escape(_fmt(c.get('error')))} |"
        )
    if not calls:
        lines.append("| (none recorded) | | | | | | |")
    lines.append("")

    attempts = result.get("attempts") or []
    lines.append("### Attempts and failures")
    lines.append("")
    if attempts:
        for a in attempts:
            tail = f" - error: {_escape(a['error'])}" if a.get("error") else ""
            kind = " (assembled plan)" if a.get("assembled") else ""
            lines.append(f"- attempt {a.get('attempt')}{kind}{tail}")
    else:
        lines.append("- none recorded")
    timings = result.get("stage_timings") or {}
    if timings:
        lines += ["", "Stage timings:", "", "```json", json.dumps(timings, indent=2, sort_keys=True), "```"]
    lines.append("")

    flags = result.get("flags") or []
    counts = Counter(str(f.get("code")) for f in flags)
    lines += ["### Flags by code", ""]
    if counts:
        lines += ["| code | count |", "|---|---|"]
        lines += [f"| {_escape(code)} | {n} |" for code, n in sorted(counts.items())]
    else:
        lines.append("No flags.")
    lines.append("")

    issues = (result.get("validation") or {}).get("issues") or []
    lines += ["### Validation issues", ""]
    if issues:
        lines += ["| code | path | blocking |", "|---|---|---|"]
        for i in issues:
            lines.append(
                f"| {_escape(_fmt(i.get('code')))} | {_escape(_fmt(i.get('path')))} | {i.get('blocking')} |"
            )
    else:
        lines.append("No validation issues.")
    lines.append("")

    vis = visual_blocks(result)
    lines += ["### Blocks with `visual`", ""]
    if vis:
        lines += ["| slot | block id | figure_ref |", "|---|---|---|"]
        lines += [
            f"| {_escape(_fmt(v['slot_id']))} | {_escape(_fmt(v['block_id']))} | {_escape(_fmt(v['figure_ref']))} |"
            for v in vis
        ]
    else:
        lines.append("None.")
    lines.append("")
    return lines


def build_report(single: dict[str, Any] | None, staged: dict[str, Any] | None) -> str:
    """Markdown comparison report for one generation (pure; no I/O)."""
    gen = (single or staged or {}).get("generation_id", "?")
    lines = [f"# Planner comparison: {gen}", ""]
    lines += ["## Wall-clock", "", "| mode | status | wall_s | llm calls |", "|---|---|---|---|"]
    for label, r in (("single", single), ("staged", staged)):
        if r is None:
            lines.append(f"| {label} | not run | - | - |")
        else:
            lines.append(
                f"| {label} | {'ok' if r.get('ok') else 'FAILED'} | {_fmt(r.get('wall_s'))} "
                f"| {len(r.get('llm_calls') or [])} |"
            )
    lines.append("")
    lines += _mode_section(single, "Single")
    lines += _mode_section(staged, "Staged")

    rows = section_diff(single, staged)
    lines += ["## Section-by-section diff", ""]
    if not rows:
        lines += ["No plan to compare (neither mode produced a plan).", ""]
    for row in rows:
        lines += [f"### Slot `{row['slot_id']}`", ""]
        lines += ["| field | single | staged |", "|---|---|---|"]
        for field, key in (
            ("display_title", "display_title"),
            ("blocks", "block_count"),
            ("intents", "intents"),
            ("source_question_ids", "source_question_ids"),
            ("visual block ids", "visual_block_ids"),
        ):
            def cell(side: dict[str, Any]) -> str:
                value = side[key]
                if isinstance(value, list):
                    value = ", ".join(str(v) for v in value) or "-"
                return _escape(_fmt(value))

            lines.append(f"| {field} | {cell(row['single'])} | {cell(row['staged'])} |")
        lines.append("")
        if row["diff"]:
            lines += ["```diff", *row["diff"], "```", ""]
    return "\n".join(lines).rstrip() + "\n"


def build_summary(entries: list[dict[str, Any]]) -> str:
    """Cross-generation summary table from ``{generation_id, single, staged}`` entries."""
    lines = [
        "# Planner comparison summary",
        "",
        "| generation | mode | run | status | wall_s | calls | flags | blocking issues | visual blocks |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        for mode in MODES:
            for index, r in enumerate(entry.get(mode) or [], start=1):
                issues = (r.get("validation") or {}).get("issues") or []
                blocking = sum(1 for i in issues if i.get("blocking"))
                lines.append(
                    f"| {_escape(entry['generation_id'])} | {mode} | {index} "
                    f"| {'ok' if r.get('ok') else 'FAILED'} | {_fmt(r.get('wall_s'))} "
                    f"| {len(r.get('llm_calls') or [])} | {len(r.get('flags') or [])} "
                    f"| {blocking} | {len(visual_blocks(r))} |"
                )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- orchestration


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


async def compare_generation(
    generation_id: str,
    out_dir: Path,
    modes: tuple[str, ...],
    repeat: int,
    loader: Callable[[str], Awaitable[tuple[Any, Any]]] | None = None,
) -> dict[str, Any]:
    load = loader or load_inputs
    packet, legality = await load(generation_id)
    gen_dir = out_dir / generation_id
    gen_dir.mkdir(parents=True, exist_ok=True)
    runs: dict[str, list[dict[str, Any]]] = {m: [] for m in MODES}
    for run_index in range(1, repeat + 1):
        for mode in modes:
            result = await run_mode(mode, packet, legality, generation_id)
            runs[mode].append(result)
            suffix = "" if run_index == 1 else f"-r{run_index}"
            _write_json(gen_dir / f"{mode}{suffix}.json", result)
    first_single = runs["single"][0] if runs["single"] else None
    first_staged = runs["staged"][0] if runs["staged"] else None
    (gen_dir / "report.md").write_text(build_report(first_single, first_staged), encoding="utf-8")
    return {"generation_id": generation_id, **runs}


async def run_compare(
    generation_ids: list[str],
    out_dir: Path,
    modes: tuple[str, ...] = MODES,
    repeat: int = 1,
    loader: Callable[[str], Awaitable[tuple[Any, Any]]] | None = None,
) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for generation_id in generation_ids:
        try:
            entries.append(await compare_generation(generation_id, out_dir, modes, repeat, loader))
        except Exception as exc:  # noqa: BLE001 - one bad id must not stop the rest
            print(f"{generation_id}: failed to load or run: {type(exc).__name__}: {exc}", file=sys.stderr)
            entries.append({"generation_id": generation_id, "single": [], "staged": []})
    (out_dir / "summary.md").write_text(build_summary(entries), encoding="utf-8")
    return entries


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--generation-id", action="append", required=True, dest="generation_ids")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--modes", default="single,staged", help="comma list of: single, staged")
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    modes = tuple(m.strip() for m in args.modes.split(",") if m.strip())
    bad = [m for m in modes if m not in MODES]
    if bad or not modes:
        parser.error(f"--modes must be a subset of {','.join(MODES)}")
    if args.repeat < 1:
        parser.error("--repeat must be >= 1")
    args.modes = modes
    return args


async def amain(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    await run_compare(args.generation_ids, Path(args.out), args.modes, args.repeat)
    print(f"Wrote comparison to {Path(args.out)} (do not commit it).")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
