from pathlib import Path
import shutil

base = Path("apps/textbook-agent/backend/src/learn")

def ensure_pkg(name: str, doc: str) -> Path:
    p = base / name
    p.mkdir(parents=True, exist_ok=True)
    init = p / "__init__.py"
    if not init.exists():
        init.write_text(f'"""{doc}"""\n', encoding="utf-8")
    return p

publishing = ensure_pkg("publishing", "Learn publishing (LearnRelease).")
analytics = ensure_pkg("analytics", "Learn analytics / insight.")
runtime = ensure_pkg("runtime", "Learn runtime sessions/instances/classes.")
ensure_pkg("distribution", "Learn distribution (classes/assignments) — placeholder.")
ensure_pkg("evidence", "Learn evidence / scoring homes — placeholder.")

moves = [
    ("release_routes.py", publishing / "release_routes.py", "learn.publishing.release_routes"),
    ("insight_service.py", analytics / "insight_service.py", "learn.analytics.insight_service"),
    ("runtime_routes.py", runtime / "runtime_routes.py", "learn.runtime.runtime_routes"),
    ("runtime_service.py", runtime / "runtime_service.py", "learn.runtime.runtime_service"),
    ("runtime_models.py", runtime / "runtime_models.py", "learn.runtime.runtime_models"),
    ("class_service.py", runtime / "class_service.py", "learn.runtime.class_service"),
]

shim_tpl = '''"""Compatibility shim — use `{target}`.

Temporary (C2). Remove when all call sites import the learn subdomain path (C3).
"""

from __future__ import annotations

from {target} import *  # noqa: F401,F403
'''

for src_name, dst, target in moves:
    src = base / src_name
    if not src.exists():
        print("missing", src)
        continue
    if not dst.exists():
        shutil.move(str(src), str(dst))
        print("moved", src_name, "->", dst.relative_to(base))
    else:
        print("dst exists", dst)
    # write shim at old path
    (base / src_name).write_text(shim_tpl.format(target=target), encoding="utf-8")
    print("shim", src_name)

# update app.py imports to canonical learn subdomain paths later via separate edit
print("done")
