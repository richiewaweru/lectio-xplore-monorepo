from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def merge_pdfs(*, source_paths: list[Path], output_path: Path) -> Path:
    writer = PdfWriter()
    for path in source_paths:
        reader = PdfReader(str(path))
        for page in reader.pages:
            writer.add_page(page)

    with output_path.open("wb") as handle:
        writer.write(handle)
    return output_path


def add_page_numbers(*, pdf_path: Path, skip_pages: int) -> tuple[Path, int]:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    total_pages = len(reader.pages)

    for index, page in enumerate(reader.pages):
        if index >= skip_pages:
            overlay = _page_number_overlay(index - skip_pages + 1)
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with pdf_path.open("wb") as handle:
        writer.write(handle)
    return pdf_path, total_pages


def add_metadata(*, pdf_path: Path, title: str, subject: str, author: str) -> Path:
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata(
        {
            "/Title": title,
            "/Subject": subject,
            "/Author": author,
            "/Creator": "Textbook Agent",
        }
    )
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    return pdf_path


def _page_number_overlay(page_number: int) -> PdfReader:
    packet = BytesIO()
    page = canvas.Canvas(packet, pagesize=A4)
    page.setFont("Helvetica", 10)
    page.drawCentredString(A4[0] / 2, 12 * mm, f"{page_number}")
    page.save()
    packet.seek(0)
    return PdfReader(packet)
