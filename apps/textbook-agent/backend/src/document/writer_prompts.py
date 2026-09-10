"""Short prompt templates for ordinary document composition and writing.

Interaction authoring stays in ``learn.generation.interaction_writer``.
Figure assets use the existing figure pipeline — composers only place a
``figure`` primitive with caption/alt placeholders when needed.
"""

from __future__ import annotations

from pathlib import Path

DOCUMENT_COMPOSER_PROMPT_NAME = "document-composer-v1.txt"
DOCUMENT_WRITER_PROMPT_NAME = "document-writer-v1.txt"

DOCUMENT_PRIMITIVES = (
    "paragraph",
    "heading",
    "list",
    "figure",
    "table",
    "callout",
)

COMPOSITION_TEMPLATE = """Compose an ordered sequence of ordinary document primitives.

Allowed kinds only: paragraph, heading, list, figure, table, callout.
Do not emit component_id, template_id, page_break, ruled_lines, or media blobs.
Interactions are authored separately — never invent interaction nodes here.
Figure nodes may include caption/alt; asset generation uses the existing figure pipeline.
"""

GENERIC_WRITER_TEMPLATE = """Write content for one ordinary document primitive.

Supported kinds: paragraph, heading, list, table, callout.
Fill only fields for that kind. No component schemas or unrelated fields.
Do not author interactions. Figure content is handled by the figure pipeline.
"""

FIGURE_PIPELINE_NOTE = (
    "Figure uses the existing figure pipeline; composers/writers only place a "
    "figure primitive (caption/alt) and do not invent binary assets."
)


def _prompts_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "resources" / "prompts"


def document_composer_prompt() -> str:
    """Load the packaged document composition prompt body."""
    return (_prompts_dir() / DOCUMENT_COMPOSER_PROMPT_NAME).read_text(encoding="utf-8")


def document_writer_prompt() -> str:
    """Load the packaged generic document writer prompt body."""
    return (_prompts_dir() / DOCUMENT_WRITER_PROMPT_NAME).read_text(encoding="utf-8")


__all__ = [
    "COMPOSITION_TEMPLATE",
    "DOCUMENT_COMPOSER_PROMPT_NAME",
    "DOCUMENT_PRIMITIVES",
    "DOCUMENT_WRITER_PROMPT_NAME",
    "FIGURE_PIPELINE_NOTE",
    "GENERIC_WRITER_TEMPLATE",
    "document_composer_prompt",
    "document_writer_prompt",
]
