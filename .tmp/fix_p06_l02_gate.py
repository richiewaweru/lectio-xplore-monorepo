from pathlib import Path

p = Path("docs/unit-native-program/GATE_RESULTS.csv")
text = p.read_text(encoding="utf-8")
lines = text.splitlines()
new_line = (
    '"P06","P06-L02","PASS",'
    '"uv run pytest -q tests/print_learn/test_p06_learn_authoring_gates.py'
    '::test_p06_l02_repeated_and_interleaved_order_survives_assemble",'
    '"Repeated same-type blocks and content\u2192activity\u2192content order '
    'survive assemble/Builder/reload/render.",'
    '"1 passed, exit 0",'
    '"docs/unit-native-program/evidence/mocks/p06/l02-ordered-blocks.txt",'
    '"pending"'
)
out = []
for line in lines:
    if line.startswith('"P06","P06-L02"'):
        out.append(new_line)
    else:
        out.append(line)
payload = "\n".join(out) + "\n"
p.write_text(payload, encoding="utf-8")
Path("docs/unit-native-program/pack/tracking/GATE_RESULTS.csv").write_text(payload, encoding="utf-8")
print("fixed L02")
