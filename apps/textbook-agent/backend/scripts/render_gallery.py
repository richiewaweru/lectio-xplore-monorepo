"""Render every gallery spec into one HTML page for visual review.

    uv run python scripts/render_gallery.py [--out outputs/render_gallery]

SVGs are inlined so the page opens from disk without a server.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydantic import TypeAdapter  # noqa: E402

from media.render.contracts import RenderSpec  # noqa: E402
from media.render.export import render_spec  # noqa: E402
from media.render.gallery import GALLERY  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="outputs/render_gallery")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    adapter = TypeAdapter(RenderSpec)
    cards: list[str] = []
    for name, raw in GALLERY.items():
        rendered = render_spec(adapter.validate_python(raw))
        (out / f"{name}.svg").write_bytes(rendered.svg)
        (out / f"{name}.png").write_bytes(rendered.png)
        svg = rendered.svg.decode("utf-8")
        svg = svg[svg.index("<svg") :]
        cards.append(
            f'<figure><div class="art">{svg}</div><figcaption><b>{html.escape(name)}</b>'
            f" · {html.escape(rendered.family)}<br>{html.escape(rendered.alt_text)}</figcaption></figure>"
        )
    page = (
        "<!doctype html><meta charset=utf-8><title>Render gallery</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#f4f6f8;margin:24px}"
        "main{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:20px}"
        "figure{background:#fff;margin:0;padding:16px;border:1px solid #d9dee4;border-radius:8px}"
        ".art svg{width:100%;height:auto}figcaption{font-size:13px;color:#52606d;margin-top:8px}</style>"
        f"<h1>Render gallery ({len(cards)})</h1><main>{''.join(cards)}</main>"
    )
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"wrote {len(cards)} figures to {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
