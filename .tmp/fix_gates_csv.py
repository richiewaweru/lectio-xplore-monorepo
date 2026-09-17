import csv
from collections import Counter
from pathlib import Path

p = Path(r"c:\Projects\lectio\docs\unit-native-program\authoring-correction-v2\tracking\GATE_RESULTS.csv")
fixed = []
for line in p.read_text(encoding="utf-8").splitlines():
    if line.startswith("A05-G04,A05,Fallback cannot restore"):
        _, rest = line.split(",yes,PASS,", 1)
        line = (
            'A05-G04,A05,"Fallback cannot restore candidates excluded for assets, '
            'budget, readiness, policy or writer support.",yes,PASS,' + rest
        )
    elif line.startswith("A06-G05,A06,Definition-edit propagation"):
        _, rest = line.split(",yes,PASS,", 1)
        line = (
            'A06-G05,A06,"Definition-edit propagation and defect regressions run through '
            'actual production interfaces, not disconnected helpers.",yes,PASS,' + rest
        )
    fixed.append(line)
p.write_text("\n".join(fixed) + "\n", encoding="utf-8")
rows = list(csv.DictReader(p.open(encoding="utf-8")))
print(len(rows), dict(Counter(r["status"] for r in rows)))
print("non-pass", [(r["gate_id"], r["status"]) for r in rows if r["status"] != "PASS"])
