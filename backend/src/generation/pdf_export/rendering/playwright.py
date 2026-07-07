from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any

from core.pdf_export_runtime import pdf_render_semaphore
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from generation.pdf_export.config import PDFExportConfig

logger = logging.getLogger(__name__)


class PDFRenderError(RuntimeError):
    """Raised when the print route cannot be rendered to PDF."""

    def __init__(self, message: str, *, debug: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.debug = debug or {}


def _on_console(msg) -> None:
    text = msg.text
    if len(text) > 1000:
        text = f"{text[:1000]}..."
    logger.warning("PDF print console", extra={"type": msg.type, "text": text})


def _on_request_failed(request) -> None:
    failure = request.failure
    failure_s = str(failure) if failure is not None else None
    logger.warning(
        "PDF print request failed",
        extra={"url": request.url, "method": request.method, "failure": failure_s},
    )


_PRINT_ROOT_SNAPSHOT_JS = """
() => {
  const root = document.querySelector('[data-generation-complete="true"]');
  if (!root) {
    return { found: false };
  }
  const declared = document.querySelectorAll('[data-print-container], [data-print-item]');
  const totalBlocks = document.querySelectorAll('[data-lectio-block]');
  return {
    found: true,
    renderer: root.getAttribute('data-renderer'),
    fetch_status: root.getAttribute('data-fetch-status'),
    section_count: root.getAttribute('data-section-count'),
    template_id: root.getAttribute('data-template-id'),
    image_count: root.getAttribute('data-image-count'),
    images_loaded: root.getAttribute('data-images-loaded'),
    images_failed: root.getAttribute('data-images-failed'),
    images_timed_out: root.getAttribute('data-images-timed-out'),
    failed_image_sources: root.getAttribute('data-failed-image-sources'),
    print_contract_coverage: {
      declared: declared.length,
      total: totalBlocks.length
    }
  };
}
"""


_OVERSIZED_SCAN_JS = """
(maxUsableHeight) => {
  const items = document.querySelectorAll(
    '[data-print-container="atomic"], [data-print-item]'
  );
  const oversized = [];
  for (const el of items) {
    const height = el.getBoundingClientRect().height;
    if (height > maxUsableHeight) {
      el.setAttribute('data-print-oversized', 'true');
      oversized.push({
        type: el.getAttribute('data-print-container')
          || el.getAttribute('data-print-item'),
        block: el.getAttribute('data-lectio-block') || 'unknown',
        height: Math.round(height),
      });
    }
  }
  return {
    scanned: items.length,
    oversized: oversized,
  };
}
"""


_PAGE_MEASURE_JS = """
(usablePageHeight) => {
  const root = document.querySelector('[data-generation-complete="true"]');
  const target = root || document.body;
  const body = document.body;
  const doc = document.documentElement;
  const measuredHeight = Math.max(
    target.scrollHeight || 0,
    body ? body.scrollHeight : 0,
    doc ? doc.scrollHeight : 0,
    target.getBoundingClientRect ? target.getBoundingClientRect().height : 0
  );
  return {
    scroll_height_px: Math.ceil(measuredHeight),
    usable_page_height_px: usablePageHeight,
    page_count_estimate: Math.max(1, Math.ceil(measuredHeight / usablePageHeight)),
  };
}
"""


def _log_print_snapshot(generation_id: str, snapshot: dict[str, Any]) -> None:
    if not snapshot.get("found"):
        return

    layout = snapshot.get("print_layout_report")
    oversized_n = 0
    if isinstance(layout, dict):
        ob = layout.get("oversized_blocks")
        if isinstance(ob, list):
            oversized_n = len(ob)

    logger.info(
        "PDF render diagnostics",
        extra={
            "generation_id": generation_id,
            "renderer": snapshot.get("renderer"),
            "fetch_status": snapshot.get("fetch_status"),
            "section_count": snapshot.get("section_count"),
            "template_id": snapshot.get("template_id"),
            "image_count": snapshot.get("image_count"),
            "images_loaded": snapshot.get("images_loaded"),
            "images_failed": snapshot.get("images_failed"),
            "images_timed_out": snapshot.get("images_timed_out"),
            "print_contract_coverage": snapshot.get("print_contract_coverage"),
            "oversized_block_count": oversized_n,
        },
    )

    if str(snapshot.get("images_failed") or "0") != "0":
        logger.warning(
            "PDF image failures",
            extra={
                "generation_id": generation_id,
                "failed_image_sources": snapshot.get("failed_image_sources"),
            },
        )


async def render_generation_pdf(
    *,
    output_path: Path,
    generation_id: str,
    auth_token: str,
    config: PDFExportConfig,
    render_path: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print_snapshot = await render_generation_print_preflight(
        generation_id=generation_id,
        auth_token=auth_token,
        config=config,
        render_path=render_path,
        output_path=output_path,
    )
    return output_path, print_snapshot


async def render_generation_print_preflight(
    *,
    generation_id: str,
    auth_token: str,
    config: PDFExportConfig,
    render_path: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    path_part = render_path if render_path is not None else f"/textbook/{generation_id}"
    separator = "&" if "?" in path_part else "?"
    render_url = f"{config.render_base_url}{path_part}{separator}print=true&token={auth_token}"

    print_snapshot: dict[str, Any] = {}

    async with pdf_render_semaphore:
        print_snapshot = await _render_print_route(
            generation_id=generation_id,
            render_url=render_url,
            config=config,
            output_path=output_path,
        )
    return print_snapshot


async def _render_print_route(
    *,
    generation_id: str,
    render_url: str,
    config: PDFExportConfig,
    output_path: Path | None,
) -> dict[str, Any]:
    print_snapshot: dict[str, Any] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            page.on("console", _on_console)
            page.on("requestfailed", _on_request_failed)
            try:
                response = await page.goto(
                    render_url,
                    wait_until="domcontentloaded",
                    timeout=config.playwright_timeout_ms,
                )
                logger.info(
                    "PDF print route opened",
                    extra={
                        "render_url": render_url,
                        "status": response.status if response else None,
                        "page_url": page.url,
                        "title": await page.title(),
                    },
                )
                await page.wait_for_selector(
                    '[data-generation-complete="true"]',
                    timeout=config.playwright_timeout_ms,
                )
                logger.info(
                    "PDF print ready selector found",
                    extra={"render_url": render_url, "page_url": page.url},
                )
                try:
                    evaluated = await page.evaluate(_PRINT_ROOT_SNAPSHOT_JS)
                    if isinstance(evaluated, dict):
                        print_snapshot = evaluated
                except Exception:
                    logger.exception("PDF print page evaluate failed")

                oversized_scan: dict[str, Any] = {"scanned": 0, "oversized": []}
                try:
                    raw_oversized = await page.evaluate(
                        _OVERSIZED_SCAN_JS,
                        float(config.usable_page_height_px),
                    )
                    if isinstance(raw_oversized, dict):
                        oversized_scan = raw_oversized
                except Exception:
                    logger.exception("PDF print oversized scan failed")

                if oversized_scan.get("oversized"):
                    await page.add_style_tag(
                        content="""
[data-print-oversized='true'] {
  break-inside: auto !important;
  page-break-inside: auto !important;
}
"""
                    )
                    logger.warning(
                        "Oversized print blocks detected — relaxed fragmentation",
                        extra={
                            "generation_id": generation_id,
                            "oversized": oversized_scan["oversized"],
                        },
                    )

                coverage = print_snapshot.get("print_contract_coverage")
                if not isinstance(coverage, dict):
                    coverage = {"declared": 0, "total": 0}

                page_measure: dict[str, Any] = {}
                try:
                    raw_measure = await page.evaluate(
                        _PAGE_MEASURE_JS,
                        float(config.usable_page_height_px),
                    )
                    if isinstance(raw_measure, dict):
                        page_measure = raw_measure
                except Exception:
                    logger.exception("PDF print page measurement failed")
                page_count_estimate = int(page_measure.get("page_count_estimate") or 1)
                scroll_height_px = int(page_measure.get("scroll_height_px") or 0)
                if scroll_height_px and not page_count_estimate:
                    page_count_estimate = max(
                        1,
                        math.ceil(scroll_height_px / max(1, config.usable_page_height_px)),
                    )

                print_snapshot["print_layout_report"] = {
                    "renderer": print_snapshot.get("renderer"),
                    "section_count": print_snapshot.get("section_count"),
                    "image_count": print_snapshot.get("image_count"),
                    "images_loaded": print_snapshot.get("images_loaded"),
                    "images_failed": print_snapshot.get("images_failed"),
                    "images_timed_out": print_snapshot.get("images_timed_out"),
                    "print_contract_coverage": coverage,
                    "oversized_blocks": oversized_scan.get("oversized", []),
                    "scanned_elements": int(oversized_scan.get("scanned") or 0),
                    "usable_height_px_threshold": config.usable_page_height_px,
                    "page_count_estimate": page_count_estimate,
                    "scroll_height_px": scroll_height_px,
                }
                _log_print_snapshot(generation_id, print_snapshot)

                if output_path is not None:
                    await page.pdf(
                        path=str(output_path),
                        format="A4",
                        print_background=True,
                        prefer_css_page_size=True,
                    )
            except PlaywrightTimeoutError as exc:
                debug: dict[str, Any] = {
                    "render_url": render_url,
                    "page_url": page.url,
                    "title": None,
                    "html_sample": None,
                }
                try:
                    html = await page.content()
                    debug["title"] = await page.title()
                    debug["html_sample"] = html[:4000]
                    logger.error(
                        "PDF print timed out (navigation or ready selector)",
                        extra={
                            "render_url": render_url,
                            "page_url": page.url,
                            "title": debug["title"],
                            "html_sample": debug["html_sample"],
                        },
                    )
                except Exception as capture_exc:
                    debug["capture_error"] = str(capture_exc)[:500]
                    logger.exception("Could not capture failed print page HTML")
                raise PDFRenderError(
                    f"Timed out rendering print view at {render_url}",
                    debug=debug,
                ) from exc
        finally:
            await browser.close()

    return print_snapshot
