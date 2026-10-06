"""Lesson backbone: the structured anchor a lesson's questions are written against.

The backbone is generated after the teacher approves the lesson structure and
before the approved questions are written.  It pins ONE concrete scenario with
exact data and its correct answer, the figure specs a learner must look at, and
up to two practice variants (same idea, changed data).

Identity split (same pattern as ``LessonSourcebookDraft`` vs ``LessonSourcebook``):
the provider fills :class:`LessonBackboneDraft`, which carries NO anchor/variant
ids; code assigns ``anchor-1`` / ``v1`` / ``v2`` while materializing
:class:`LessonBackbone`.  Figure ids stay provider-owned because anchor and
variants reference them, and the validator proves every reference resolves.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

ANCHOR_ID = "anchor-1"
MAX_VARIANTS = 2
_VARIANT_ID = re.compile(r"^v[1-9][0-9]*$")


class BackboneFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    must_show: list[str] = Field(default_factory=list)
    labels_required: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class BackboneAnchor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ANCHOR_ID
    story: str
    data: dict[str, Any]
    answer: str | None = None
    figure_ids: list[str] = Field(default_factory=list)


class BackboneVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    change: str
    data: dict[str, Any]
    answer: str | None = None
    figure_ids: list[str] = Field(default_factory=list)


class LessonBackbone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: BackboneAnchor
    variants: list[BackboneVariant] = Field(default_factory=list, max_length=MAX_VARIANTS)
    figures: list[BackboneFigure] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> LessonBackbone:
        if not self.anchor.story.strip():
            raise ValueError("anchor.story must not be empty")
        ids = [self.anchor.id, *(v.id for v in self.variants), *(f.id for f in self.figures)]
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise ValueError(f"ids must be unique across anchor, variants and figures: {duplicates}")
        for variant in self.variants:
            if not _VARIANT_ID.match(variant.id):
                raise ValueError(f"variant id '{variant.id}' must look like v1, v2")
        figure_ids = {f.id for f in self.figures}
        owners: list[tuple[str, list[str]]] = [(self.anchor.id, self.anchor.figure_ids)]
        owners.extend((v.id, v.figure_ids) for v in self.variants)
        for owner, refs in owners:
            missing = [ref for ref in refs if ref not in figure_ids]
            if missing:
                raise ValueError(f"{owner}.figure_ids references unknown figures: {missing}")
        return self


class BackboneAnchorDraft(BaseModel):
    """Provider-owned anchor content; the id is assigned by code."""

    model_config = ConfigDict(extra="forbid")

    story: str = Field(min_length=1)
    data: dict[str, Any]
    answer: str | None = None
    figure_ids: list[str] = Field(default_factory=list)


class BackboneVariantDraft(BaseModel):
    """Provider-owned variant content; ids (v1, v2) are assigned by code."""

    model_config = ConfigDict(extra="forbid")

    change: str = Field(min_length=1)
    data: dict[str, Any]
    answer: str | None = None
    figure_ids: list[str] = Field(default_factory=list)


class LessonBackboneDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anchor: BackboneAnchorDraft
    variants: list[BackboneVariantDraft] = Field(default_factory=list, max_length=MAX_VARIANTS)
    figures: list[BackboneFigure] = Field(default_factory=list)


def materialize_backbone(draft: LessonBackboneDraft) -> LessonBackbone:
    """Assign code-owned ids and run the cross-reference validator."""
    return LessonBackbone(
        anchor=BackboneAnchor(id=ANCHOR_ID, **draft.anchor.model_dump()),
        variants=[
            BackboneVariant(id=f"v{index}", **variant.model_dump())
            for index, variant in enumerate(draft.variants, start=1)
        ],
        figures=list(draft.figures),
    )


def backbone_hash(backbone: LessonBackbone) -> str:
    """sha256 over canonical JSON (sorted keys, compact separators)."""
    canonical = json.dumps(
        backbone.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "ANCHOR_ID",
    "BackboneAnchor",
    "BackboneAnchorDraft",
    "BackboneFigure",
    "BackboneVariant",
    "BackboneVariantDraft",
    "LessonBackbone",
    "LessonBackboneDraft",
    "backbone_hash",
    "materialize_backbone",
]
