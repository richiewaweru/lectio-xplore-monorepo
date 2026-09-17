from pathlib import Path
roots = [
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src"),
    Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests"),
]
old = "v3_blueprint.curriculum.path_models"
new = "v3_blueprint.planning.models"
n = 0
for root in roots:
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if old not in text:
            continue
        path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        n += 1
print("fixed", n)
