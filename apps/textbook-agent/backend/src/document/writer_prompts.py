"""Prompt bodies for ordinary document composition and writing.

Production text comes from the canonical prompt manifest/loader. Interaction
authoring stays in ``learn.generation.interaction_writer``. Figure assets use
the figure pipeline — composers only place a figure primitive with caption/alt.
"""

from __future__ import annotations

from core.prompts.loader import effective_prompt_text, hash_prompt

DOCUMENT_COMPOSER_PROMPT_ID = "document-composer"
DOCUMENT_WRITER_PROMPT_ID = "document-writer"
DOCUMENT_COMPOSER_PROMPT_NAME = "document-composer.md"
DOCUMENT_WRITER_PROMPT_NAME = "document-writer.md"

DOCUMENT_PRIMITIVES = (
    "paragraph",
    "heading",
    "list",
    "figure",
    "table",
    "callout",
)

FIGURE_PIPELINE_NOTE = (
    "Figure uses the existing figure pipeline; composers/writers only place a "
    "figure primitive (caption/alt) and do not invent binary assets."
)


def document_composer_prompt() -> str:
    """Effective document composition prompt (manifest-backed)."""
    return effective_prompt_text(DOCUMENT_COMPOSER_PROMPT_ID)


def document_writer_prompt() -> str:
    """Effective ordinary document writer prompt (manifest-backed)."""
    return effective_prompt_text(DOCUMENT_WRITER_PROMPT_ID)


def document_composer_prompt_hash() -> str:
    return hash_prompt(document_composer_prompt())


def document_writer_prompt_hash() -> str:
    return hash_prompt(document_writer_prompt())


def composition_template() -> str:
    return document_composer_prompt()


def generic_writer_template() -> str:
    return document_writer_prompt()


# Import-time aliases for existing exporters. These read the manifest files.
COMPOSITION_TEMPLATE = document_composer_prompt()
GENERIC_WRITER_TEMPLATE = document_writer_prompt()


__all__ = [
    "COMPOSITION_TEMPLATE",
    "DOCUMENT_COMPOSER_PROMPT_ID",
    "DOCUMENT_COMPOSER_PROMPT_NAME",
    "DOCUMENT_PRIMITIVES",
    "DOCUMENT_WRITER_PROMPT_ID",
    "DOCUMENT_WRITER_PROMPT_NAME",
    "FIGURE_PIPELINE_NOTE",
    "GENERIC_WRITER_TEMPLATE",
    "composition_template",
    "document_composer_prompt",
    "document_composer_prompt_hash",
    "document_writer_prompt",
    "document_writer_prompt_hash",
    "generic_writer_template",
]
