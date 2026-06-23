from __future__ import annotations

from v3_blueprint.models import ProductionBlueprint
from v3_execution.models import (
    BookletStatus,
    DraftPack,
    GeneratedAnswerKeyBlock,
    GeneratedVisualBlock,
    SectionAssemblyDiagnostic,
)


class V3PackBuilder:
    def build(
        self,
        *,
        blueprint: ProductionBlueprint,
        generation_id: str,
        blueprint_id: str,
        template_id: str,
        sections: list[dict],
        visual_blocks: list[GeneratedVisualBlock],
        answer_key: GeneratedAnswerKeyBlock | None,
        warnings: list[str],
        booklet_status: BookletStatus,
        section_diagnostics: list[SectionAssemblyDiagnostic] | None = None,
        booklet_issues: list[dict[str, object]] | None = None,
    ) -> DraftPack:
        return DraftPack(
            generation_id=generation_id,
            blueprint_id=blueprint_id,
            template_id=template_id,
            subject=blueprint.metadata.subject,
            status=booklet_status,
            sections=sections,
            visual_blocks=visual_blocks,
            answer_key=answer_key,
            warnings=warnings,
            section_diagnostics=section_diagnostics or [],
            booklet_issues=booklet_issues or [],
        )


__all__ = ["V3PackBuilder"]
