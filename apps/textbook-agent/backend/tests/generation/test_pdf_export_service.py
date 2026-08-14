from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core.config import Settings
from generation.pdf_export.service import (
    NativeDocumentContractError,
    PDFExportRequest,
    export_v3_studio_pdf,
)


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
    assert mock_export.await_args.kwargs["render_path"] == "/studio/print/gen-123?edition=teacher"


def _native_document() -> dict:
    return {
        "document_version": 2,
        "contract_version": "1.0.0",
        "id": "doc-native",
        "title": "Native lesson",
        "language": "en",
        "metadata": {"catalogue_version": "1.1.0", "resource_type": "lesson"},
        "sections": [
            {
                "id": "explain",
                "title": "Explain",
                "blocks": [
                    {
                        "id": "p-1",
                        "object": "prose",
                        "intent": "explain",
                        "position": 0,
                        "content": {"paragraphs": ["Native content"]},
                        "layout": {"placement": "main"},
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_native_v2_bypasses_legacy_adapter_and_duplicate_answer_pdf(tmp_path: Path) -> None:
    exported_pdf = tmp_path / "native.pdf"
    exported_pdf.write_bytes(b"%PDF-1.4\n")
    request = PDFExportRequest(
        school_name="Example School",
        teacher_name="Teacher Example",
        include_answers=True,
        edition="teacher",
    )
    envelope = {"document_version": 2, "lectio_document": _native_document()}
    settings = Settings.model_construct(PDF_EXPORT_ENABLED=True, PDF_RENDER_BASE_URL="http://localhost:5173")
    with patch(
        "generation.pdf_export.service.build_pipeline_document_for_v3_pdf",
        side_effect=AssertionError("native document entered legacy adapter"),
    ), patch(
        "generation.pdf_export.service.export_generation_pdf",
        new=AsyncMock(
            return_value=SimpleNamespace(
                pdf_path=exported_pdf,
                filename="native.pdf",
                file_size_bytes=exported_pdf.stat().st_size,
                page_count=1,
                generation_time_ms=1,
                cleanup_paths=[exported_pdf],
                print_page_debug={},
            )
        ),
    ) as mock_export:
        await export_v3_studio_pdf(
            generation_id="gen-native",
            user_id="user-1",
            title="Native lesson",
            subject="Science",
            template_id="guided-concept-path",
            document_json=envelope,
            auth_token="token",
            request=request,
            settings=settings,
        )

    forwarded = mock_export.await_args.kwargs["request"]
    assert forwarded.include_answers is False
    assert forwarded.edition == "teacher"
    assert mock_export.await_args.kwargs["document"].sections == []
    assert mock_export.await_args.kwargs["render_path"] == "/studio/print/gen-native?edition=teacher"


@pytest.mark.asyncio
async def test_native_v2_malformed_document_fails_closed_without_legacy_fallback() -> None:
    request = PDFExportRequest(school_name="School", teacher_name="Teacher")
    settings = Settings.model_construct(PDF_EXPORT_ENABLED=True, PDF_RENDER_BASE_URL="http://localhost:5173")
    with patch(
        "generation.pdf_export.service.build_pipeline_document_for_v3_pdf",
        side_effect=AssertionError("malformed native document entered legacy adapter"),
    ):
        with pytest.raises(NativeDocumentContractError, match="LectioDocumentV2"):
            await export_v3_studio_pdf(
                generation_id="gen-native-bad",
                user_id="user-1",
                title="Native lesson",
                subject="Science",
                template_id="guided-concept-path",
                document_json={"document_version": 2, "lectio_document": {"title": "Missing sections"}},
                auth_token="token",
                request=request,
                settings=settings,
                native_whole_lesson=True,
            )
