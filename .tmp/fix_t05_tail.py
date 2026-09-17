from pathlib import Path

p = Path(
    r"C:\Projects\lectio\apps\textbook-agent\backend\tests\reliability\test_correction_pass.py"
)
text = p.read_text(encoding="utf-8")
t05 = text.find("async def test_t05_renewals_keep_ownership_past_short_lease")
if t05 < 0:
    raise SystemExit("t05 not found")
needle = (
    '    assert learn_execution_from_generation(row)["lease_seconds"] == 1\n'
    '    assert learn_execution_from_generation(row)["heartbeat_at"] is not None\n'
)
idx = text.find(needle, t05)
if idx < 0:
    raise SystemExit("needle not found")
end = idx + len(needle)
tail = """
    # Without renewals the original 1s lease would be dead; takeover must fail.
    again = await claim_learn_execution(
        db_session,
        generation_id=gen.id,
        worker_id=\"t05-takeover\",
    )
    assert again is None
"""
p.write_text(text[:end] + tail, encoding="utf-8")
print("ok", end)
