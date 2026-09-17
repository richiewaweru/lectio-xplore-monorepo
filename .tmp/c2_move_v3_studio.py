from pathlib import Path
import shutil

src = Path("apps/textbook-agent/backend/src/generation/v3_studio")
dst = Path("apps/textbook-agent/backend/src/print/http/v3_studio")
http = Path("apps/textbook-agent/backend/src/print/http")
http.mkdir(parents=True, exist_ok=True)
(http / "__init__.py").write_text(
    '"""Print HTTP surfaces (Unit Print + studio)."""\n', encoding="utf-8"
)
if not dst.exists():
    shutil.copytree(src, dst)
    print("copied", len(list(dst.rglob("*.py"))), "py files")
else:
    print("dst already exists")
