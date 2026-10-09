"""Live figure-prompt evaluation harness.

Renders a set of figure probes through the real shared-lesson figure path so
prompt changes can be compared before/after.

  uv run python scripts/eval_figure_prompts.py --specs docs/figure-representation/probes.json \
      --out out/figeval/baseline --env-file .env --path gemini
  uv run python scripts/eval_figure_prompts.py --compare out/figeval/baseline out/figeval/after \
      --out out/figeval/compare

Probe orders are built by calling the production ``_figure_order_from`` in
``document.shared_lesson.media`` (so visual_style etc. always track production).
Gemini path: ``execute_visual`` with IMAGE_PROVIDER=gemini, visual QC and the
image cache forced off, local filesystem image store (no GCS).
Render path: ``render_figure`` + ``LlmSpecBuilder`` (what RoutingFigureExecutor
does when LECTIO_RENDER_FIGURES=auto); needs the V3_FIGURE_SPEC model key.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Evaluate figure prompts against live providers.")
    p.add_argument("--specs", type=Path, help="Probe JSON array.")
    p.add_argument("--out", type=Path, required=True, help="Output directory.")
    p.add_argument("--env-file", type=Path, default=None, help="Env file to preload (never printed).")
    p.add_argument("--path", choices=("gemini", "render"), default="gemini")
    p.add_argument("--only", default="", help="Comma-separated probe ids.")
    p.add_argument("--force-mode", choices=("image", "diagram"), default=None)
    p.add_argument("--concurrency", type=int, default=3)
    p.add_argument("--compare", nargs=2, type=Path, metavar=("DIR_A", "DIR_B"))
    return p.parse_args()


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def build_order(probe: dict[str, Any], mode: str) -> Any:
    """Build the work order via production ``_figure_order_from``."""
    from curriculum.teaching_plan.models import VisualSpec
    from document.shared_lesson.media import _figure_order_from
    from document.shared_lesson.models import (
        FigureAccessibility,
        FigureDisplay,
        FigureNode,
        ParagraphDisplay,
        ParagraphNode,
        SharedSection,
    )
    from infra.generation_runtime.contracts import SourceIdentity

    pid = str(probe["id"])
    spec = VisualSpec(
        mode=mode,  # type: ignore[arg-type]
        purpose=probe["purpose"],
        must_show=list(probe.get("must_show") or []),
        labels_required=list(probe.get("labels_required") or []),
        must_not_show=list(probe.get("must_not_show") or []),
        required=True,
    )
    node = FigureNode(
        id=f"fig-{pid}",
        teaching_block_id=f"blk-{pid}",
        display=FigureDisplay(caption=str(probe.get("caption") or probe["purpose"])),
        accessibility=FigureAccessibility(),
    )
    para = ParagraphNode(
        id=f"p-{pid}",
        display=ParagraphDisplay(text=str(probe.get("source") or probe["purpose"])),
    )
    section = SharedSection(id=f"sec-{pid}", title=pid, position=0, nodes=(para, node))
    identity = SourceIdentity(
        source_artifact_type="teaching_plan",
        source_artifact_id=f"eval-{pid}",
        source_revision=1,
        source_hash="0" * 64,
    )
    return _figure_order_from(
        identity=identity, section=section, node=node, spec=spec, facts=()
    ).work_order


def _setup_env(args: argparse.Namespace) -> None:
    if args.env_file is not None:
        load_dotenv(_resolve(args.env_file), override=True)
    os.environ["V3_VISUAL_QC_ENABLED"] = "false"
    os.environ["V3_IMAGE_CACHE_ENABLED"] = "false"
    if args.path == "gemini":
        os.environ["IMAGE_PROVIDER"] = "gemini"
        os.environ.pop("PIPELINE_IMAGE_PROVIDER", None)
    from core.config import settings

    settings.app_env = "development"  # local filesystem image store, no GCS


async def _run_gemini(order: Any, out: Path, pid: str, meta: dict[str, Any]) -> None:
    from media.generation.executor import execute_visual
    from media.generation.prompt import build_visual_prompt
    from media.providers.registry import load_image_provider_spec
    from media.storage.image_store import get_image_store

    pspec = load_image_provider_spec()
    meta.update(provider=pspec.provider, model=pspec.model_name)
    shown = order
    if pspec.provider == "gemini" and order.visual.visual_style == "diagram_numbered":
        # Mirror execute_visual: Gemini runs numbered orders as labelled diagrams.
        shown = order.model_copy(deep=True)
        shown.visual.visual_style = None
    prompt = build_visual_prompt(shown, provider_renders_labels=pspec.provider == "gemini")
    (out / f"{pid}.prompt.txt").write_text(prompt, encoding="utf-8")

    async def _noop(_e: str, _p: dict[str, Any]) -> None:
        return None

    gid = f"figeval-{uuid.uuid4().hex[:12]}"
    blocks = await execute_visual(order, _noop, trace_id=gid, generation_id=gid)
    block = blocks[0]
    if block.status == "failed" or not block.image_url:
        raise RuntimeError(f"{block.error_code}: {block.error_message}")
    key = f"{gid}/{order.visual.attaches_to or 'visuals'}/{block.visual_id}.png"
    data = await get_image_store().read_image_key(key=key)
    (out / f"{pid}.png").write_bytes(data)
    # The local store keeps a copy under data/images; the out/ copy is the record.
    shutil.rmtree(PROJECT_ROOT / "data" / "images" / gid, ignore_errors=True)
    meta["provider_text"] = getattr(block, "provider_text", None)


async def _run_render(order: Any, out: Path, pid: str, meta: dict[str, Any]) -> None:
    from media.render.pipeline import Fallback, Rendered, Unavailable, render_figure
    from media.render.spec_builder import LlmSpecBuilder

    gid = f"figeval-{uuid.uuid4().hex[:12]}"
    outcome = await render_figure(order, builder=LlmSpecBuilder(trace_id=gid, generation_id=gid))
    if isinstance(outcome, Fallback):
        meta["family"] = "none"
        meta["reason"] = outcome.reason
    elif isinstance(outcome, Unavailable):
        meta["family"] = "error"
        raise RuntimeError(f"{outcome.code}: {outcome.errors[:2]}")
    else:
        assert isinstance(outcome, Rendered)
        meta["family"] = outcome.figure.family
        meta["warnings"] = list(outcome.warnings)
        (out / f"{pid}.png").write_bytes(outcome.figure.png)
        (out / f"{pid}.svg").write_bytes(outcome.figure.svg)


async def _run_probe(
    probe: dict[str, Any], args: argparse.Namespace, out: Path, sem: asyncio.Semaphore
) -> dict[str, Any]:
    pid = str(probe["id"])
    mode = args.force_mode or probe.get("mode", "diagram")
    meta: dict[str, Any] = {
        "id": pid, "kind": probe.get("kind"), "mode": mode, "path": args.path,
        "probe": probe, "error": None,
    }
    async with sem:
        started = time.perf_counter()
        try:
            order = build_order(probe, mode)
            meta["visual_style"] = order.visual.visual_style
            meta["labels_required"] = list(order.visual.labels_required)
            if args.path == "gemini":
                await _run_gemini(order, out, pid, meta)
            else:
                await _run_render(order, out, pid, meta)
        except Exception as exc:  # noqa: BLE001
            meta["error"] = f"{type(exc).__name__}: {str(exc)[:400]}"
        meta["elapsed_s"] = round(time.perf_counter() - started, 1)
    (out / f"{pid}.meta.json").write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
    status = "ERR " + meta["error"][:90] if meta["error"] else (meta.get("family") or "ok")
    print(f"[{pid}] {mode:7} style={meta.get('visual_style')} {meta['elapsed_s']}s {status}", flush=True)
    return meta


def _load_metas(directory: Path) -> dict[str, dict[str, Any]]:
    metas: dict[str, dict[str, Any]] = {}
    for f in sorted(directory.glob("*.meta.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        metas[m["id"]] = m
    return metas


def _cell(directory: Path, rel_to: Path, m: dict[str, Any] | None) -> str:
    if m is None:
        return "<div class='cell'><em>missing</em></div>"
    pid = m["id"]
    png = directory / f"{pid}.png"
    rel = os.path.relpath(png, rel_to).replace("\\", "/")
    img = f"<img src='{html.escape(rel)}'>" if png.exists() else "<em>no image</em>"
    err = f"<p class='err'>{html.escape(str(m['error']))}</p>" if m.get("error") else ""
    pf = directory / f"{pid}.prompt.txt"
    prompt = pf.read_text(encoding="utf-8") if pf.exists() else ""
    labels = html.escape(json.dumps(m.get("labels_required") or []))
    details = (
        f"<details><summary>prompt / labels</summary><p>labels_required: {labels}</p>"
        f"<pre>{html.escape(prompt)}</pre></details>"
    )
    info = (
        f"<small>style={m.get('visual_style')} family={m.get('family', '')} "
        f"{m.get('provider', '')} {m.get('model', '')} {m.get('elapsed_s')}s</small>"
    )
    return f"<div class='cell'>{img}{err}{info}{details}</div>"


def write_index(out: Path, dirs: list[Path]) -> Path:
    all_metas = [_load_metas(d) for d in dirs]
    ids = list(dict.fromkeys(i for metas in all_metas for i in metas))
    cards = []
    for pid in ids:
        first = next(metas[pid] for metas in all_metas if pid in metas)
        head = (
            f"<h3>{html.escape(pid)}</h3><small>kind={html.escape(str(first.get('kind')))} "
            f"mode={first.get('mode')}</small>"
        )
        cells = "".join(_cell(d, out, metas.get(pid)) for d, metas in zip(dirs, all_metas))
        cards.append(
            f"<section class='card'>{head}<div class='row' style='--cols:{len(dirs)}'>"
            f"{cells}</div></section>"
        )
    page = (
        "<!doctype html><meta charset='utf-8'><title>Figure eval</title><style>"
        "body{font:14px system-ui;margin:16px;background:#f6f6f6}"
        ".card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px;margin:0 0 16px}"
        ".row{display:grid;grid-template-columns:repeat(var(--cols),1fr);gap:12px}"
        "img{max-width:100%;border:1px solid #ccc}pre{white-space:pre-wrap;font-size:12px}"
        ".err{color:#b00}h3{margin:0}</style>"
        f"<h1>Figure eval: {html.escape(' | '.join(d.name for d in dirs))}</h1>" + "".join(cards)
    )
    target = out / "index.html"
    target.write_text(page, encoding="utf-8")
    return target


async def _main() -> int:
    args = _parse_args()
    out = _resolve(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.compare:
        print(f"wrote {write_index(out, [_resolve(d) for d in args.compare])}")
        return 0
    if args.specs is None:
        print("--specs is required unless --compare is used", file=sys.stderr)
        return 2
    probes = json.loads(_resolve(args.specs).read_text(encoding="utf-8"))
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        probes = [p for p in probes if p["id"] in wanted]
    if args.path == "render" and not args.force_mode:
        skipped = [p["id"] for p in probes if p.get("mode", "diagram") != "diagram"]
        probes = [p for p in probes if p.get("mode", "diagram") == "diagram"]
        if skipped:
            print(f"render path: skipping image-mode probes {skipped}")
    _setup_env(args)
    sem = asyncio.Semaphore(max(1, args.concurrency))
    metas = await asyncio.gather(*(_run_probe(p, args, out, sem) for p in probes))
    write_index(out, [out])
    failed = [m["id"] for m in metas if m["error"]]
    print(f"done: {len(metas) - len(failed)}/{len(metas)} ok; failed={failed}; index={out / 'index.html'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
