"""Guard: retired legacy packages must not reappear as production imports."""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND_SRC = Path(__file__).resolve().parents[2] / "apps" / "textbook-agent" / "backend" / "src"
FORBIDDEN_TOP = frozenset({"planning", "generation", "builder", "learning", "telemetry"})
# Justified exceptions outside the six canonical roots:
# contracts, resource_specs, media, v3_*, core (platform routes/entities)

def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module.split(".")[0])
    return names

def main() -> int:
    violations: list[str] = []
    # forbidden packages must not exist on disk
    for name in FORBIDDEN_TOP:
        if (BACKEND_SRC / name).exists():
            violations.append(f"retired package still on disk: {name}/")
    for path in BACKEND_SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for top in _imports(path):
            if top in FORBIDDEN_TOP:
                violations.append(f"{path.relative_to(BACKEND_SRC)}: imports {top}")
    if violations:
        print("ZERO_LEGACY_GUARD FAIL")
        for v in violations[:50]:
            print(" ", v)
        print(f"total={len(violations)}")
        return 1
    print("ZERO_LEGACY_GUARD PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
