from pathlib import Path
import re

SRC = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\src")
TESTS = Path(r"C:\Projects\lectio\apps\textbook-agent\backend\tests")
REPLACEMENTS = [
    (r"\bgeneration\.page_objects\b", "print.rendering.page_objects"),
    (r"\bgeneration\.pdf_export\b", "print.rendering.pdf"),
    (r"\bgeneration\.v3_studio\b", "print.http.v3_studio"),
    (r"\bgeneration\.path_preparation\b", "application.unit_lesson"),
    (r"\bgeneration\.canonical\b", "learn.generation.canonical"),
    (r"\bgeneration\.contracts\b", "learn.generation.contracts"),
    (r"\bgeneration\.signal_map\b", "print.http.v3_studio.signal_map"),
    (r"\bplanning\.whole_lesson\b", "print.generation.whole_lesson"),
]
n = 0
for root in (SRC, TESTS):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        new = text
        for pat, repl in REPLACEMENTS:
            new = re.sub(pat, repl, new)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            n += 1
            print(path)
print("changed", n)

app = SRC / "app.py"
t = app.read_text(encoding="utf-8")
t2 = t.replace(
    "from generation.routes import router as generation_router",
    "from print.http.v3_studio.router import v3_studio_router",
)
t2 = t2.replace(
    "app.include_router(generation_router)",
    'app.include_router(v3_studio_router, prefix="/api/v1")',
)
app.write_text(t2, encoding="utf-8", newline="\n")
print("app ok", "v3_studio_router" in t2)
