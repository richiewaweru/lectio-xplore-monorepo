from pathlib import Path
import csv
import io

p = Path(r"c:/Projects/lectio/docs/unit-native-program/authoring-correction-v2/tracking/GATE_RESULTS.csv")
sha = "4b6bbc4694bb996e857f500772f6fe773531d63f"
evidence = "docs/unit-native-program/remaining-fixes-v3/evidence/r05/full-offline-gates.txt"
notes = {
    "A02": "PASS via Remaining Fixes R01/R02 + A02 suite on 4b6bbc46; historical REOPENED evidence retained under authoring-correction-v2/evidence/a02/",
    "A04": "PASS via Remaining Fixes R01 envelope + A04/R01 tests; historical REOPENED evidence retained under authoring-correction-v2/evidence/a04/",
    "A05": "PASS via Remaining Fixes R03 model selector; historical REOPENED evidence retained under authoring-correction-v2/evidence/a05/",
    "A06": "PASS via Remaining Fixes R04 real persist/publish/attempt/component gates; historical REOPENED evidence retained under authoring-correction-v2/evidence/a06/",
}

rows = []
with p.open(newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    header = next(reader)
    rows.append(header)
    for row in reader:
        if not row:
            continue
        phase = row[1]
        if phase in notes and row[4] == "REOPENED":
            row[4] = "PASS"
            row[7] = sha
            row[8] = evidence
            row[9] = notes[phase]
        rows.append(row)

with p.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerows(rows)

print("rows", len(rows))
print("reopened left", sum(1 for r in rows[1:] if r[4] == "REOPENED"))
print("a02-a06 pass", sum(1 for r in rows[1:] if r[1] in notes and r[4] == "PASS"))
