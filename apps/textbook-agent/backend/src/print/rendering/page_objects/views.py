"""Student/teacher document projections and simple HTML/PDF renders."""

from __future__ import annotations

import html
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

Audience = Literal["student", "teacher"]


def student_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the document without answer_key."""
    out = deepcopy(doc)
    out.pop("answer_key", None)
    return out


def teacher_document(doc: dict[str, Any]) -> dict[str, Any]:
    """Return a full teacher copy (includes answer_key when present)."""
    return deepcopy(doc)


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _figure_placeholder(content: dict[str, Any]) -> str:
    alt = str(content.get("alt_text") or "").strip()
    caption = str(content.get("caption") or "").strip()
    asset = content.get("asset") if isinstance(content.get("asset"), dict) else {}
    status = str(asset.get("status") or "")
    if status == "pending" or not asset.get("src"):
        parts = [p for p in (alt, caption) if p]
        label = " — ".join(parts) if parts else "Figure pending"
        return f"[Figure pending: {label}]"
    return caption or alt or "[Figure]"


def _block_html(block: dict[str, Any]) -> str:
    object_id = str(block.get("object") or "")
    content = block.get("content") if isinstance(block.get("content"), dict) else {}
    bid = _esc(block.get("id"))

    if object_id == "prose":
        paras = "".join(f"<p>{_esc(p)}</p>" for p in content.get("paragraphs") or [])
        return f'<article data-block="{bid}" data-object="prose">{paras}</article>'

    if object_id == "list":
        style = str(content.get("style") or "unordered")
        tag = "ol" if style in {"ordered", "steps"} else "ul"
        lead = content.get("lead_in")
        lead_html = f"<p class=\"lead\">{_esc(lead)}</p>" if lead else ""
        items = "".join(
            f"<li>{_esc(item.get('text') if isinstance(item, dict) else item)}</li>"
            for item in content.get("items") or []
        )
        return (
            f'<section data-block="{bid}" data-object="list">{lead_html}'
            f"<{tag}>{items}</{tag}></section>"
        )

    if object_id == "table":
        columns = list(content.get("columns") or [])
        col_ids = [str(c.get("id")) for c in columns if isinstance(c, dict)]
        head = "".join(
            f"<th>{_esc(c.get('label') if isinstance(c, dict) else c)}</th>"
            for c in columns
        )
        body_rows = []
        for row in content.get("rows") or []:
            cells = row.get("cells") if isinstance(row, dict) else {}
            tds = "".join(f"<td>{_esc((cells or {}).get(cid, ''))}</td>" for cid in col_ids)
            body_rows.append(f"<tr>{tds}</tr>")
        caption = content.get("caption")
        cap = f"<caption>{_esc(caption)}</caption>" if caption else ""
        return (
            f'<table data-block="{bid}" data-object="table">{cap}'
            f"<thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
        )

    if object_id == "figure":
        placeholder = _esc(_figure_placeholder(content))
        return (
            f'<figure data-block="{bid}" data-object="figure">'
            f"<p class=\"figure-placeholder\">{placeholder}</p></figure>"
        )

    if object_id == "aside":
        label = content.get("label")
        label_html = f"<strong>{_esc(label)}</strong> " if label else ""
        return (
            f'<aside data-block="{bid}" data-object="aside">'
            f"{label_html}<p>{_esc(content.get('body'))}</p></aside>"
        )

    if object_id == "worked-example":
        steps = "".join(
            f"<li>{_esc(step.get('text') if isinstance(step, dict) else step)}</li>"
            for step in content.get("steps") or []
        )
        title = content.get("title")
        title_html = f"<h4>{_esc(title)}</h4>" if title else ""
        return (
            f'<section data-block="{bid}" data-object="worked-example">{title_html}'
            f"<p><strong>Problem:</strong> {_esc(content.get('problem'))}</p>"
            f"<ol>{steps}</ol>"
            f"<p><strong>Answer:</strong> {_esc(content.get('answer'))}</p></section>"
        )

    if object_id == "questions":
        instructions = content.get("instructions")
        instr = f"<p>{_esc(instructions)}</p>" if instructions else ""
        items = "".join(
            f"<li id=\"{_esc(item.get('id'))}\">{_esc(item.get('prompt'))}</li>"
            for item in content.get("items") or []
            if isinstance(item, dict)
        )
        return (
            f'<section data-block="{bid}" data-object="questions">{instr}'
            f"<ol>{items}</ol></section>"
        )

    if object_id == "choices":
        options = "".join(
            f"<li><strong>{_esc(opt.get('letter'))}.</strong> {_esc(opt.get('text'))}</li>"
            for opt in content.get("options") or []
            if isinstance(opt, dict)
        )
        return (
            f'<section data-block="{bid}" data-object="choices">'
            f"<p>{_esc(content.get('stem'))}</p><ul>{options}</ul></section>"
        )

    if object_id == "answer-key":
        groups = []
        for group in content.get("groups") or []:
            if not isinstance(group, dict):
                continue
            title = group.get("title")
            title_html = f"<h4>{_esc(title)}</h4>" if title else ""
            entries = "".join(
                f"<li><code>{_esc(e.get('question_id'))}</code>: {_esc(e.get('answer'))}</li>"
                for e in group.get("entries") or []
                if isinstance(e, dict)
            )
            groups.append(f"{title_html}<ul>{entries}</ul>")
        return (
            f'<section data-block="{bid}" data-object="answer-key" class="answer-key">'
            f"<h3>Answer key</h3>{''.join(groups)}</section>"
        )

    return f'<div data-block="{bid}" data-object="{_esc(object_id)}"></div>'


def render_document_html(doc: dict[str, Any], *, audience: Audience) -> str:
    projected = student_document(doc) if audience == "student" else teacher_document(doc)
    sections_html: list[str] = []
    for section in projected.get("sections") or []:
        if not isinstance(section, dict):
            continue
        blocks = "".join(
            _block_html(block)
            for block in section.get("blocks") or []
            if isinstance(block, dict)
        )
        sections_html.append(
            f'<section id="{_esc(section.get("id"))}">'
            f"<h2>{_esc(section.get('title'))}</h2>{blocks}</section>"
        )

    answer_key_html = ""
    if audience == "teacher" and isinstance(projected.get("answer_key"), dict):
        answer_key_html = _block_html(projected["answer_key"])

    title = _esc(projected.get("title") or "Lesson")
    return (
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\"/>"
        f"<title>{title} ({audience})</title></head><body>"
        f"<header><h1>{title}</h1>"
        f"<p class=\"audience\">Audience: {_esc(audience)}</p></header>"
        f"{''.join(sections_html)}{answer_key_html}</body></html>\n"
    )


def _wrap(text: str, width: int = 95) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    for paragraph in str(text).split("\n"):
        if paragraph.strip():
            lines.extend(textwrap.wrap(paragraph, width=width) or [""])
        else:
            lines.append("")
    return lines or [""]


def _pdf_draw_lines(pdf: canvas.Canvas, lines: list[str], *, x: float, y: float, height: float) -> float:
    line_height = 4.2 * mm
    for line in lines:
        if y < 20 * mm:
            pdf.showPage()
            y = height - 20 * mm
            pdf.setFont("Helvetica", 10)
        pdf.drawString(x, y, line)
        y -= line_height
    return y


def render_document_pdf(doc: dict[str, Any], path: str | Path, *, audience: Audience) -> Path:
    """Write a simple valid PDF for student or teacher audience."""
    projected = student_document(doc) if audience == "student" else teacher_document(doc)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    pdf = canvas.Canvas(str(output), pagesize=A4)
    width, height = A4
    y = height - 24 * mm
    margin = 18 * mm

    title = str(projected.get("title") or "Lesson")
    pdf.setTitle(f"{title} ({audience})")
    pdf.setFont("Helvetica-Bold", 16)
    y = _pdf_draw_lines(pdf, _wrap(title, 70), x=margin, y=y, height=height)
    pdf.setFont("Helvetica", 10)
    y = _pdf_draw_lines(
        pdf,
        [f"Audience: {audience}"],
        x=margin,
        y=y - 2 * mm,
        height=height,
    )
    y -= 4 * mm

    for section in projected.get("sections") or []:
        if not isinstance(section, dict):
            continue
        pdf.setFont("Helvetica-Bold", 12)
        y = _pdf_draw_lines(
            pdf,
            _wrap(str(section.get("title") or section.get("id") or "Section"), 80),
            x=margin,
            y=y,
            height=height,
        )
        pdf.setFont("Helvetica", 10)
        for block in section.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            object_id = str(block.get("object") or "")
            content = block.get("content") if isinstance(block.get("content"), dict) else {}
            chunk_lines: list[str] = []
            if object_id == "prose":
                chunk_lines.extend(str(p) for p in content.get("paragraphs") or [])
            elif object_id == "list":
                if content.get("lead_in"):
                    chunk_lines.append(str(content["lead_in"]))
                for item in content.get("items") or []:
                    text = item.get("text") if isinstance(item, dict) else item
                    chunk_lines.append(f"• {text}")
            elif object_id == "table":
                if content.get("caption"):
                    chunk_lines.append(str(content["caption"]))
                for row in content.get("rows") or []:
                    cells = row.get("cells") if isinstance(row, dict) else {}
                    if isinstance(cells, dict):
                        chunk_lines.append(" | ".join(str(v) for v in cells.values()))
            elif object_id == "figure":
                chunk_lines.append(_figure_placeholder(content))
            elif object_id == "aside":
                label = content.get("label")
                prefix = f"{label}: " if label else ""
                chunk_lines.append(f"{prefix}{content.get('body') or ''}")
            elif object_id == "worked-example":
                chunk_lines.append(f"Problem: {content.get('problem') or ''}")
                for step in content.get("steps") or []:
                    text = step.get("text") if isinstance(step, dict) else step
                    chunk_lines.append(f"- {text}")
                chunk_lines.append(f"Answer: {content.get('answer') or ''}")
            elif object_id == "questions":
                if content.get("instructions"):
                    chunk_lines.append(str(content["instructions"]))
                for item in content.get("items") or []:
                    if isinstance(item, dict):
                        chunk_lines.append(f"{item.get('id')}: {item.get('prompt')}")
            elif object_id == "choices":
                chunk_lines.append(str(content.get("stem") or ""))
                for opt in content.get("options") or []:
                    if isinstance(opt, dict):
                        chunk_lines.append(f"{opt.get('letter')}. {opt.get('text')}")
            else:
                chunk_lines.append(f"[{object_id}]")

            for raw in chunk_lines:
                y = _pdf_draw_lines(pdf, _wrap(str(raw), 95), x=margin, y=y, height=height)
            y -= 2 * mm

    if audience == "teacher" and isinstance(projected.get("answer_key"), dict):
        pdf.setFont("Helvetica-Bold", 12)
        y = _pdf_draw_lines(pdf, ["Answer key"], x=margin, y=y - 2 * mm, height=height)
        pdf.setFont("Helvetica", 10)
        ak = projected["answer_key"]
        ak_content = ak.get("content") if isinstance(ak.get("content"), dict) else {}
        for group in ak_content.get("groups") or []:
            if not isinstance(group, dict):
                continue
            if group.get("title"):
                y = _pdf_draw_lines(
                    pdf, _wrap(str(group["title"]), 90), x=margin, y=y, height=height
                )
            for entry in group.get("entries") or []:
                if not isinstance(entry, dict):
                    continue
                line = f"{entry.get('question_id')}: {entry.get('answer')}"
                y = _pdf_draw_lines(pdf, _wrap(line, 95), x=margin, y=y, height=height)

    pdf.save()
    return output


__all__ = [
    "render_document_html",
    "render_document_pdf",
    "student_document",
    "teacher_document",
]
