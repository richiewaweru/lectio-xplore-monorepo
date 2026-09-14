#!/usr/bin/env python3
"""Frontend store boundary guard (P05 / G19).

Unit, Print, and Learn product stores must not import sibling domain internals.
Shared transport ($lib/api, $lib/types, $lib/reliability, $lib/shared) is allowed.
Composition roots (routes/) may import all domains.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "apps" / "textbook-agent" / "frontend" / "src"

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".svelte", ".mjs", ".cjs"}

IMPORT_RE = re.compile(
    r"""(?:from|import)\s+['"](\$lib/[^'"]+)['"]"""
)

# Domain roots that own product state.
PRINT_ROOT = FRONTEND_SRC / "lib" / "print"
LEARN_ROOT = FRONTEND_SRC / "lib" / "learn"
UNIT_ROOT = FRONTEND_SRC / "lib" / "curriculum" / "units"

# Forbidden sibling internals (prefix match on $lib import path).
PRINT_FORBIDDEN = (
    "$lib/learn/",
    "$lib/curriculum/units/unit-workspace",
    "$lib/curriculum/units/edit-protection",
)
LEARN_FORBIDDEN = (
    "$lib/print/",
    "$lib/curriculum/units/unit-workspace",
    "$lib/curriculum/units/edit-protection",
)
UNIT_FORBIDDEN = (
    "$lib/print/stores/",
    "$lib/print/studio/",
    "$lib/print/generation/",
    "$lib/print/components/",
    "$lib/learn/document/",
    "$lib/learn/authoring/",
    "$lib/learn/student/",
    "$lib/learn/shared/",
)


@dataclass(frozen=True)
class Violation:
    file_path: str
    line: int
    rule: str
    snippet: str


def _iter_source_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in SOURCE_SUFFIXES:
            continue
        parts = set(path.parts)
        if parts & {"node_modules", "dist", ".svelte-kit", "coverage", ".tmp"}:
            continue
        # Tests may intentionally assert forbidden patterns via string literals;
        # still scan them — imports in tests should also respect boundaries.
        files.append(path)
    return files


def _scan_forbidden(root: Path, forbidden: tuple[str, ...], rule: str) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = IMPORT_RE.search(line)
            if not match:
                continue
            import_path = match.group(1)
            for needle in forbidden:
                if import_path == needle or import_path.startswith(needle):
                    try:
                        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
                    except ValueError:
                        rel = str(path)
                    violations.append(
                        Violation(
                            file_path=rel,
                            line=lineno,
                            rule=rule,
                            snippet=line.strip()[:200],
                        )
                    )
                    break
    return violations


def find_violations() -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(
        _scan_forbidden(PRINT_ROOT, PRINT_FORBIDDEN, "print-must-not-import-sibling-internals")
    )
    violations.extend(
        _scan_forbidden(LEARN_ROOT, LEARN_FORBIDDEN, "learn-must-not-import-sibling-internals")
    )
    violations.extend(
        _scan_forbidden(UNIT_ROOT, UNIT_FORBIDDEN, "unit-must-not-import-sibling-internals")
    )
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    violations = find_violations()
    if args.format == "json":
        import json

        print(
            json.dumps(
                [
                    {
                        "file_path": v.file_path,
                        "line": v.line,
                        "rule": v.rule,
                        "snippet": v.snippet,
                    }
                    for v in violations
                ],
                indent=2,
            )
        )
    else:
        if not violations:
            print("Frontend store boundary check: PASS (0 violations)")
        else:
            print(f"Frontend store boundary check: FAIL ({len(violations)} violations)")
            for v in violations:
                print(f"  {v.file_path}:{v.line} [{v.rule}] {v.snippet}")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
