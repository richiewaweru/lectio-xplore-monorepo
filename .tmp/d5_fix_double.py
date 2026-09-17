from pathlib import Path
roots = [
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\frontend\src"),
]
fixes = [
    ("learn.learn.generation", "learn.generation"),
    ("print.print.generation", "print.generation"),
    ("print.print.http", "print.http"),
    ("print.print.rendering", "print.rendering"),
    ("curriculum.curriculum.", "curriculum."),
    ("application.application.", "application."),
    ("infra.infra.", "infra."),
    ("v3_blueprint.curriculum.path_models", "v3_blueprint.planning.models"),
]
n=0
for root in roots:
  if not root.exists():
    continue
  for path in root.rglob("*"):
    if path.suffix not in {".py", ".ts", ".svelte"}: continue
    if "__pycache__" in path.parts: continue
    text = path.read_text(encoding="utf-8")
    new = text
    for a,b in fixes:
      new = new.replace(a,b)
    if new != text:
      path.write_text(new, encoding="utf-8", newline="\n"); n+=1
print("fixed_files", n)
