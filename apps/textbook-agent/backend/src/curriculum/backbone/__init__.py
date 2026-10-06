"""Lesson backbone: scenario + exact data + answer + figure specs + variants."""

from .errors import BackboneOutputInvalidError
from .models import (
    BackboneAnchor,
    BackboneFigure,
    BackboneVariant,
    LessonBackbone,
    LessonBackboneDraft,
    backbone_hash,
    materialize_backbone,
)

__all__ = [
    "BackboneAnchor",
    "BackboneFigure",
    "BackboneOutputInvalidError",
    "BackboneVariant",
    "LessonBackbone",
    "LessonBackboneDraft",
    "backbone_hash",
    "materialize_backbone",
]
