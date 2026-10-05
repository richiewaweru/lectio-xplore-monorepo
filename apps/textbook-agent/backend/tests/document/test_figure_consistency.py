from __future__ import annotations

from document.shared_lesson.figure_consistency import label_warnings, missing_labels


def test_exact_label_in_text_or_caption_is_not_missing() -> None:
    assert missing_labels(["Chlorophyll"], "Chlorophyll absorbs light.", "") == []
    assert missing_labels(["Chlorophyll"], "", "Chlorophyll in a leaf") == []


def test_case_difference_still_matches() -> None:
    assert missing_labels(["Water vapour"], "the WATER VAPOUR rises", "") == []


def test_whitespace_difference_still_matches() -> None:
    assert missing_labels(["water  vapour"], "Water vapour rises.", "") == []
    assert missing_labels(["Water vapour"], "Water\n  vapour rises.", "") == []


def test_label_missing_from_both_text_and_caption_is_reported() -> None:
    assert missing_labels(["Condensation", "Rain"], "Rain falls.", "A cloud") == ["Condensation"]
    assert label_warnings(["Condensation", "Rain"], "Rain falls.", "A cloud") == [
        "label_missing:Condensation"
    ]


def test_no_labels_means_no_warnings() -> None:
    assert label_warnings([], "anything", "anything") == []
