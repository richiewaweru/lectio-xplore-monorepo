from v3_execution.config.policy import coherence_repair_enabled, ship_with_holes_enabled


def test_policy_flag_defaults(monkeypatch) -> None:
    monkeypatch.delenv("V3_COHERENCE_REPAIR_ENABLED", raising=False)
    monkeypatch.delenv("V3_SHIP_WITH_HOLES", raising=False)
    assert coherence_repair_enabled() is False
    assert ship_with_holes_enabled() is True


def test_policy_flags_restore_compatibility_values(monkeypatch) -> None:
    monkeypatch.setenv("V3_COHERENCE_REPAIR_ENABLED", "true")
    monkeypatch.setenv("V3_SHIP_WITH_HOLES", "false")
    assert coherence_repair_enabled() is True
    assert ship_with_holes_enabled() is False
