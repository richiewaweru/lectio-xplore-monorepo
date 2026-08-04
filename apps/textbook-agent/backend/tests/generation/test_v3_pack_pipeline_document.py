from generation.pdf_export.v3_pack_pipeline_document import build_pipeline_document_for_v3_pdf


def test_build_pipeline_manifest_from_v3_sections() -> None:
    doc = build_pipeline_document_for_v3_pdf(
        generation_id="g-1",
        title="Lesson title",
        subject="Math",
        template_id="guided-concept-path",
        document_json={
            "sections": [
                {
                    "section_id": "a",
                    "template_id": "guided-concept-path",
                    "header": {"title": "First", "subject": "Math", "grade_band": "secondary"},
                },
            ]
        },
    )
    assert len(doc.section_manifest) == 1
    assert doc.section_manifest[0].section_id == "a"
    assert doc.section_manifest[0].title == "First"
    assert doc.section_manifest[0].position == 1
    assert len(doc.sections) == 1
    assert doc.sections[0].section_id == "a"


def test_build_pipeline_skips_invalid_section_but_keeps_manifest() -> None:
    doc = build_pipeline_document_for_v3_pdf(
        generation_id="g-2",
        title="L",
        subject="S",
        template_id="guided-concept-path",
        document_json={"sections": [{"section_id": "bad", "header": {"title": "T"}}]},
    )
    assert len(doc.section_manifest) == 1
    assert doc.section_manifest[0].section_id == "bad"
    assert doc.sections == []
