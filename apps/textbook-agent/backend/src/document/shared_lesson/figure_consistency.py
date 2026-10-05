"""Deterministic, non-blocking consistency checks between a plan visual spec and prose.

The Teaching Plan's ``VisualSpec.labels_required`` names the exact label text a
figure must carry. The section writer is told to use that wording in the prose
and caption; this module records (never blocks on) any required label that
appears in neither.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

LABEL_MISSING_PREFIX = "label_missing:"
_WHITESPACE = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    """Case-fold and collapse whitespace so wording matches are formatting-insensitive."""
    return _WHITESPACE.sub(" ", value).strip().casefold()


def missing_labels(
    labels_required: Sequence[str],
    section_text: str,
    caption: str,
) -> list[str]:
    """Return required labels found in neither the section text nor the caption."""
    haystack = normalize_text(f"{section_text} {caption}")
    missing: list[str] = []
    for label in labels_required:
        needle = normalize_text(label)
        if needle and needle not in haystack and label not in missing:
            missing.append(label)
    return missing


def label_warnings(
    labels_required: Sequence[str],
    section_text: str,
    caption: str,
) -> list[str]:
    """Non-blocking ``label_missing:<label>`` warnings for ``missing_labels``."""
    return [
        f"{LABEL_MISSING_PREFIX}{label}"
        for label in missing_labels(labels_required, section_text, caption)
    ]


__all__ = ["LABEL_MISSING_PREFIX", "label_warnings", "missing_labels", "normalize_text"]
