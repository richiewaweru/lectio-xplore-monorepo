from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from generation.pdf_export.cleanup import cleanup_files, ensure_temp_dir
from generation.pdf_export.components.answers import (
    extract_answer_entries,
    generate_answer_key_pdf,
)
from generation.pdf_export.components.cover import (
    clean_cover_title,
    format_cover_date,
    generate_cover_pdf,
)
from generation.pdf_export.components.toc import generate_toc_pdf
from contracts.document import PipelineSectionManifestItem
from contracts.section_content import (
    ExplanationContent,
    HookHeroContent,
    PracticeContent,
    PracticeHint,
    PracticeProblem,
    PracticeSolution,
    QuizContent,
    QuizOption,
    SectionContent,
    SectionHeaderContent,
    WhatNextContent,
    WorkedExampleContent,
    WorkedStep,
)


def _section() -> SectionContent:
    return SectionContent(
        section_id="s-01",
        template_id="guided-concept-path",
        header=SectionHeaderContent(
            title="Limits in Motion",
            subject="Calculus",
            grade_band="secondary",
        ),
        hook=HookHeroContent(
            headline="Why a moving graph still tells a stable story",
            body="Limits let us describe what a function is approaching.",
            anchor="limits",
        ),
        explanation=ExplanationContent(
            body="A limit studies nearby behavior.",
            emphasis=["nearby behavior"],
        ),
        practice=PracticeContent(
            problems=[
                PracticeProblem(
                    difficulty="warm",
                    question="Estimate lim x->2 of x^2.",
                    hints=[PracticeHint(level=1, text="Square numbers near 2.")],
                    solution=PracticeSolution(
                        approach="Substitute nearby values or recognize the polynomial is continuous.",
                        answer="4",
                    ),
                )
            ]
        ),
        what_next=WhatNextContent(
            body="Next we connect limits to continuity.",
            next="Continuity",
        ),
        quiz=QuizContent(
            question="Which value is the limit?",
            options=[
                QuizOption(text="3", correct=False, explanation="Too low."),
                QuizOption(text="4", correct=True, explanation="This is the approached value."),
            ],
            feedback_correct="Correct.",
            feedback_incorrect="Try again.",
        ),
        worked_example=WorkedExampleContent(
            title="Worked limit example",
            setup="Evaluate a simple polynomial limit.",
            steps=[WorkedStep(label="1", content="Substitute x = 2.")],
            conclusion="Polynomials are continuous, so direct substitution works.",
            answer="4",
        ),
    )


def test_extract_answer_entries_uses_saved_section_content() -> None:
    entries = extract_answer_entries([_section()])

    prompts = [entry.prompt for entry in entries]
    assert prompts == [
        "Which value is the limit?",
        "Practice 1: Estimate lim x->2 of x^2.",
        "Worked limit example",
    ]
    assert [entry.answer for entry in entries] == ["4", "4", "4"]


def test_generate_cover_pdf_creates_valid_pdf(tmp_path: Path) -> None:
    output = generate_cover_pdf(
        output_path=tmp_path / "cover.pdf",
        title="Calculus",
        school_name="Springfield High",
        teacher_name="Ms. Johnson",
        date_label="2026-04-02",
    )

    reader = PdfReader(str(output))
    assert output.exists()
    assert len(reader.pages) == 1
    assert reader.metadata.title == "Calculus"


def test_generate_cover_pdf_uses_structured_fields_only(tmp_path: Path) -> None:
    output = generate_cover_pdf(
        output_path=tmp_path / "cover.pdf",
        title=(
            "I want to teach my students a visually enhanced lesson about the process "
            "of germination. Audience: Year 6"
        ),
        school_name="Springfield High",
        teacher_name="Ms. Johnson",
        date_label="2026-04-07",
    )

    reader = PdfReader(str(output))
    page_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert reader.metadata.title == "Germination"
    assert "Germination" in page_text
    assert "School:" in page_text
    assert "Springfield High" in page_text
    assert "Teacher:" in page_text
    assert "Ms. Johnson" in page_text
    assert "7 April 2026" in page_text
    assert "I want to teach" not in page_text
    assert "Reviewed lesson plan" not in page_text
    assert "Planning warning" not in page_text


def test_clean_cover_title_extracts_short_topic_from_teacher_prompt() -> None:
    title = clean_cover_title(
        "I want to teach my students a visually enhanced lesson about the process of germination."
    )

    assert title == "Germination"


def test_format_cover_date_localizes_iso_date() -> None:
    assert format_cover_date("2026-04-07") == "7 April 2026"


def test_generate_toc_pdf_builds_from_section_manifest(tmp_path: Path) -> None:
    output = generate_toc_pdf(
        output_path=tmp_path / "toc.pdf",
        manifest=[
            PipelineSectionManifestItem(section_id="s-01", title="Warm-up", position=1),
            PipelineSectionManifestItem(section_id="s-02", title="Worked Example", position=2),
        ],
    )

    reader = PdfReader(str(output))
    page_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert len(reader.pages) == 1
    assert "1. Warm-up" in page_text
    assert "2. Worked Example" in page_text


def test_generate_answer_key_pdf_creates_pdf_when_answers_exist(tmp_path: Path) -> None:
    output = generate_answer_key_pdf(
        output_path=tmp_path / "answers.pdf",
        sections=[_section()],
    )

    assert output is not None
    reader = PdfReader(str(output))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Answer Key" in text
    assert "Practice 1: Estimate lim x->2 of x^2." in text
    assert "Answer: 4" in text


def test_cleanup_files_removes_export_artifacts(tmp_path: Path) -> None:
    target_dir = ensure_temp_dir(tmp_path / "pdf")
    first = target_dir / "first.pdf"
    second = target_dir / "second.pdf"
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    cleanup_files([first, second, target_dir / "missing.pdf"])

    assert not first.exists()
    assert not second.exists()

