from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.config import Settings
from generation.pdf_export.service import PDFExportRequest, export_v3_studio_pdf


@pytest.mark.asyncio
async def test_export_v3_studio_pdf_uses_lectio_only_print_route(tmp_path: Path) -> None:
    exported_pdf = tmp_path / "v3.pdf"
    exported_pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

    request = PDFExportRequest(
        school_name="Example School",
        teacher_name="Teacher Example",
        include_toc=True,
        include_answers=True,
    )
    document_json = {
        "kind": "v3_booklet_pack",
        "generation_id": "gen-123",
        "template_id": "guided-concept-path",
        "subject": "Fractions",
        "sections": [{"section_id": "s-1", "header": {"title": "Intro"}}],
    }
    settings = Settings.model_construct(
        PDF_EXPORT_ENABLED=True,
        PDF_RENDER_BASE_URL="http://localhost:5173",
    )

    with patch(
        "generation.pdf_export.service.export_generation_pdf",
        new=AsyncMock(
            return_value=SimpleNamespace(
                pdf_path=exported_pdf,
                filename="fractions.pdf",
                file_size_bytes=exported_pdf.stat().st_size,
                page_count=2,
                generation_time_ms=250,
                cleanup_paths=[exported_pdf],
                print_page_debug={"renderer": "lectio"},
            )
        ),
    ) as mock_export:
        await export_v3_studio_pdf(
            generation_id="gen-123",
            user_id="user-123",
            title="Fractions Lesson",
            subject="Fractions",
            template_id="guided-concept-path",
            document_json=document_json,
            auth_token="token-123",
            request=request,
            settings=settings,
            request_id="req-123",
        )

    assert mock_export.await_count == 1
    assert mock_export.await_args.kwargs["render_path"] == "/studio/print/gen-123"
