from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from contracts.document import PipelineSectionManifestItem


def generate_toc_pdf(
    *,
    output_path: Path,
    manifest: list[PipelineSectionManifestItem],
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    pdf.setTitle("Table of Contents")
    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawString(20 * mm, height - 28 * mm, "Table of Contents")

    y = height - 44 * mm
    pdf.setFont("Helvetica", 12)
    for item in manifest:
        if y < 24 * mm:
            pdf.showPage()
            y = height - 24 * mm
            pdf.setFont("Helvetica", 12)
        pdf.drawString(24 * mm, y, f"{item.position}. {item.title}")
        y -= 10 * mm

    pdf.showPage()
    pdf.save()
    return output_path

