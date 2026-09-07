"""Build a `PipelineDocument` from a saved V3 booklet pack for PDF assembly (TOC, answer key)."""

from __future__ import annotations

import logging
from typing import Any

from contracts.document import PipelineDocument, PipelineSectionManifestItem
from contracts.section_content import SectionContent

logger = logging.getLogger(__name__)


def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _title_from_section_id(section_id: str) -> str:
    return section_id.replace("_", " ").replace("-", " ").title()


def build_pipeline_document_for_v3_pdf(
    *,
    generation_id: str,
    title: str,
    subject: str,
    template_id: str,
    document_json: dict[str, Any],
) -> PipelineDocument:
    raw = document_json.get("sections")
    raw_sections: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                raw_sections.append(item)

    manifest: list[PipelineSectionManifestItem] = []
    validated_sections: list[SectionContent] = []

    for index, item in enumerate(raw_sections):
        sid = _safe_str(item.get("section_id")) or f"section-{index + 1}"
        header = item.get("header") if isinstance(item.get("header"), dict) else {}
        title_text = _safe_str(header.get("title")) if isinstance(header, dict) else ""
        if not title_text:
            title_text = _title_from_section_id(sid)
        manifest.append(
            PipelineSectionManifestItem(section_id=sid, title=title_text, position=index + 1)
        )
        try:
            keys = SectionContent.model_fields.keys()
            filtered = {k: v for k, v in item.items() if k in keys}
            validated_sections.append(SectionContent.model_validate(filtered))
        except Exception as exc:
            logger.warning(
                "Skipping invalid V3 section for PDF assembly section_id=%s generation_id=%s: %s",
                sid,
                generation_id,
                exc,
            )

    subj = title or "Lesson"
    ctx = subject or ""

    return PipelineDocument(
        generation_id=generation_id,
        subject=subj,
        context=ctx,
        mode="v3",
        template_id=template_id,
        preset_id="blue-classroom",
        status="completed",
        section_manifest=manifest,
        sections=validated_sections,
    )

