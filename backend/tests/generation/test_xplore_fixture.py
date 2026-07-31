from __future__ import annotations

import hashlib
import json
from pathlib import Path


def test_photosynthesis_fixture_has_valid_cross_pack_contracts() -> None:
    fixture_path = (
        Path(__file__).parents[1] / "fixtures" / "xplore_photosynthesis_pack.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    cards = {card["slug"]: card for card in fixture["cards"]}

    assert fixture["contract_version"] == "0.6.0"
    assert len(fixture["variants"]) == 2
    assert len({variant["label"] for variant in fixture["variants"]}) == 2
    for item in fixture["items"]:
        card = cards[item["card_slug"]]
        misconceptions = {
            misconception["id"] for misconception in card["misconceptions"]
        }
        correct = [
            option for option in item["options"] if option["correct"] is True
        ]
        assert len(correct) == 1
        assert correct[0]["key"] == item["correct_key"]
        assert correct[0]["diagnoses"] is None
        assert all(
            option["diagnoses"] in misconceptions
            for option in item["options"]
            if option["diagnoses"] is not None
        )


def test_phase0_generation_snapshot_is_byte_for_byte_unchanged() -> None:
    fixture_path = (
        Path(__file__).parents[1] / "fixtures" / "xplore_v2_phase0_generation.json"
    )

    assert hashlib.sha256(fixture_path.read_bytes()).hexdigest() == (
        "91e0bcb220bf9e2532b13aef9fe7447ad822ab109d9d226dc032d5adb4540fd2"
    )
