from pathlib import Path

COMMIT = "0a30c1b"
paths = [
    Path(r"docs/unit-native-program/GATE_RESULTS.csv"),
    Path(r"docs/unit-native-program/pack/tracking/GATE_RESULTS.csv"),
]
for path in paths:
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith('"P04","P04-N') and line.endswith(',""'):
            line = line[:-2] + f'"{COMMIT}"'
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"updated {path}")
