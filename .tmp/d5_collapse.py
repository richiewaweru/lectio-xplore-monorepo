import re
from pathlib import Path
roots = [
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests"),
]
patterns = [
    (re.compile(r"learn(?:\.learn)+"), "learn"),
    (re.compile(r"print(?:\.print)+"), "print"),
    (re.compile(r"curriculum(?:\.curriculum)+"), "curriculum"),
    (re.compile(r"application(?:\.application)+"), "application"),
    (re.compile(r"infra(?:\.infra)+"), "infra"),
]
n=0
for root in roots:
  for path in root.rglob("*.py"):
    if "__pycache__" in path.parts: continue
    text = path.read_text(encoding="utf-8")
    new = text
    for rx, repl in patterns:
      new = rx.sub(repl, new)
    if new != text:
      path.write_text(new, encoding="utf-8", newline="\n"); n+=1
print("collapsed", n)
