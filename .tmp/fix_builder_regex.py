from pathlib import Path
import re
p = Path(r"apps/textbook-agent/frontend/src/routes/builder/[id]/page.test.ts")
t = p.read_text(encoding="utf-8")
t2, n = re.subn(
    r"screen\.queryByText\(/print/generation update delayed/i\)",
    "screen.queryByText(/generation update delayed/i)",
    t,
)
print("replacements", n)
if n:
    p.write_text(t2, encoding="utf-8")
