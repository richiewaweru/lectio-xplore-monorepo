#!/usr/bin/env python3
"""Domain-boundary guard for Print (@lectio/page) vs Learn (lectio / @lectio/learn).

Additive Phase 00 check. Does not replace the textbook-agent DDD architecture guard.
The app frontend remains the allowed composition root and may import both packages.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PAGE_PACKAGE = REPO_ROOT / "packages" / "lectio-page"
LEARN_PACKAGE_CANDIDATES = (
    REPO_ROOT / "packages" / "lectio",
    REPO_ROOT / "packages" / "lectio-learn",
)

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".svelte", ".mjs", ".cjs"}

# Imports that Print must never make.
PAGE_FORBIDDEN = re.compile(
    r"""(?:from|import)\s+['"](?:lectio(?:/[^'"]*)?|@lectio/learn(?:/[^'"]*)?)['"]"""
)

# Imports that Learn must never make.
LEARN_FORBIDDEN = re.compile(
    r"""(?:from|import)\s+['"]@lectio/page(?:/[^'"]*)?['"]"""
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
        # Ignore build outputs and dependencies.
        parts = set(path.parts)
        if parts & {"node_modules", "dist", ".svelte-kit", "coverage", ".tmp"}:
            continue
        files.append(path)
    return files


def _scan(
    root: Path,
    pattern: re.Pattern[str],
    rule: str,
    *,
    display_root: Path,
) -> list[Violation]:
    violations: list[Violation] = []
    for path in _iter_source_files(root):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                try:
                    rel = str(path.relative_to(display_root)).replace("\\", "/")
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
    return violations


# Leftover ownership-prefixed residuals that must not reappear in the app frontend.
# Note: `$lib/print/studio` is the legitimate Print owner path; do not ban it.
# Ban wrong nesting (`$lib/components/print/studio`) and retired URL prefixes.
FRONTEND_FORBIDDEN_SUBSTRINGS = (
    "$lib/learn/shared/",
    "$lib/components/print/studio",
    "'/print/studio",
    '"/print/studio',
    "`/print/studio",
    "/learn/shared/authoring",
    "/api/v1/learn/shared/authoring",
    "/api/v1/shared/auth",
)



def _scan_frontend_path_residuals(root: Path) -> list[Violation]:
    frontend = root / "apps" / "textbook-agent" / "frontend" / "src"
    violations: list[Violation] = []
    if not frontend.exists():
        return violations
    for path in _iter_source_files(frontend):
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for needle in FRONTEND_FORBIDDEN_SUBSTRINGS:
                if needle in line:
                    try:
                        rel = str(path.relative_to(root)).replace("\\", "/")
                    except ValueError:
                        rel = str(path)
                    violations.append(
                        Violation(
                            file_path=rel,
                            line=lineno,
                            rule="frontend-must-not-use-ownership-prefixed-paths",
                            snippet=line.strip()[:200],
                        )
                    )
                    break
    return violations


def find_violations(repo_root: Path | None = None) -> list[Violation]:
    root = repo_root or REPO_ROOT
    page = root / "packages" / "lectio-page"
    learn_roots = [
        root / "packages" / "lectio",
        root / "packages" / "lectio-learn",
    ]
    violations: list[Violation] = []
    violations.extend(
        _scan(page, PAGE_FORBIDDEN, "page-must-not-import-learn", display_root=root)
    )
    for learn in learn_roots:
        violations.extend(
            _scan(learn, LEARN_FORBIDDEN, "learn-must-not-import-page", display_root=root)
        )
    violations.extend(_scan_frontend_path_residuals(root))
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
            print("Domain boundary check: PASS (0 violations)")
        else:
            print(f"Domain boundary check: FAIL ({len(violations)} violations)")
            for v in violations:
                print(f"  {v.file_path}:{v.line} [{v.rule}] {v.snippet}")

    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
