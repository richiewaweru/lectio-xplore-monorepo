import logging

from generation.pdf_export.rendering import playwright as playwright_module
from generation.pdf_export.rendering.playwright import _log_print_snapshot


def _enable_playwright_logging(caplog) -> None:
    playwright_module.logger.disabled = False
    playwright_module.logger.propagate = True
    caplog.set_level(logging.INFO, logger="generation.pdf_export.rendering.playwright")


def test_log_print_snapshot_emits_diagnostics_and_failures(caplog) -> None:
    _enable_playwright_logging(caplog)

    _log_print_snapshot(
        "gen-123",
        {
            "found": True,
            "renderer": "lectio",
            "fetch_status": "response-200",
            "section_count": "4",
            "template_id": "guided-concept-path",
            "image_count": "3",
            "images_loaded": "2",
            "images_failed": "1",
            "images_timed_out": "false",
            "failed_image_sources": '["https://cdn.example/bad.png"]',
            "print_contract_coverage": {"declared": 8, "total": 12},
            "print_layout_report": {
                "oversized_blocks": [{"type": "atomic", "block": "diagram-block", "height": 1200}],
            },
        },
    )

    diagnostic_record = next(
        record for record in caplog.records if record.getMessage() == "PDF render diagnostics"
    )
    assert diagnostic_record.generation_id == "gen-123"
    assert diagnostic_record.renderer == "lectio"
    assert diagnostic_record.fetch_status == "response-200"
    assert diagnostic_record.section_count == "4"
    assert diagnostic_record.image_count == "3"
    assert diagnostic_record.images_loaded == "2"
    assert diagnostic_record.images_failed == "1"
    assert diagnostic_record.images_timed_out == "false"
    assert diagnostic_record.print_contract_coverage == {"declared": 8, "total": 12}
    assert diagnostic_record.oversized_block_count == 1

    failure_record = next(
        record for record in caplog.records if record.getMessage() == "PDF image failures"
    )
    assert failure_record.generation_id == "gen-123"
    assert failure_record.failed_image_sources == '["https://cdn.example/bad.png"]'


def test_log_print_snapshot_skips_missing_root(caplog) -> None:
    _enable_playwright_logging(caplog)

    _log_print_snapshot("gen-123", {"found": False})

    assert caplog.records == []
