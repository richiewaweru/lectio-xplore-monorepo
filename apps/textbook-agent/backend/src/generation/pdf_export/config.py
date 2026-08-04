from __future__ import annotations

from pathlib import Path

from core.config import Settings


class PDFExportConfig:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @property
    def enabled(self) -> bool:
        return self._settings.pdf_export_enabled

    @property
    def render_base_url(self) -> str:
        return self._settings.pdf_render_base_url.rstrip("/")

    @property
    def export_timeout_ms(self) -> int:
        return self._settings.pdf_export_timeout_ms

    @property
    def playwright_timeout_ms(self) -> int:
        return self._settings.playwright_timeout_ms

    @property
    def temp_dir(self) -> Path:
        return Path(self._settings.pdf_temp_dir).resolve()

    @property
    def max_file_size_bytes(self) -> int:
        return self._settings.pdf_max_file_size_mb * 1024 * 1024

    @property
    def max_page_count(self) -> int:
        return self._settings.pdf_max_page_count

    @property
    def usable_page_height_px(self) -> int:
        """Max block height for print preflight (A4 usable column; tunable via settings)."""
        return self._settings.pdf_usable_page_height_px
