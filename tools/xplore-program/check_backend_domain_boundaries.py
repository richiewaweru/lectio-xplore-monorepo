#!/usr/bin/env python3
"""Backend domain-boundary guard for print / learn / curriculum / infra.

Enforces the domain-refactor dependency direction:

  infra, curriculum
       ^
       |
  print, learn

Forbidden:
  print → learn
  learn → print
  curriculum → print|learn
  infra → print|learn
  final product prompt modules under infra/

Compatibility shim packages (planning.whole_lesson, generation.pdf_export, etc.)
are excluded from scans so temporary re-exports do not fail the guard.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_SRC = REPO_ROOT / "apps" / "textbook-agent" / "backend" / "src"

IMPORT_RE = re.compile(
    r"""^\s*(?:from|import)\s+([a-zA-Z_][\w.]*)"""
)

# Historical shim / leftover roots that still re-export into domains.
SHIM_ROOTS = {
    "planning/whole_lesson",
    "generation/page_objects",
    "generation/pdf_export",
    "generation/component_lectio",
    "generation/units_dispatch.py",
    "resource_specs/candidates.py",
    "resource_specs/component_candidates.py",
    "contracts/lectio.py",
    "contracts/lectio_page.py",
    "contracts/lesson_document.py",
    "generation/v3_studio",
    "learning",
    "builder/service.py",
    "core/auth",
    "core/llm",
    "core/storage",
    "core/middleware",
    "core/health",
    "core/config.py",
    "core/logging.py",
    "core/errors.py",
    "core/rate_limit.py",
    "core/events.py",
    "core/version.py",
    "core/dependencies.py",
    "core/database/session.py",
    "core/pdf_export_runtime.py",
    "telemetry",
    "planning/service.py",
    "planning/routes.py",
    "planning/models.py",
    "planning/schedule.py",
    "planning/outcomes.py",
    "planning/shapes.py",
    "planning/linkage.py",
    "planning/approved_items.py",
    "planning/compatibility.py",
    "planning/page_blocks.py",
    "planning/page_projections.py",
    "planning/catalogue_projections.py",
}


@dataclass(frozen=True)
class Violation:
    file_path: str
    line: int
    rule: str
    snippet: str


def _rel(path: Path) -> str:
    return str(path.relative_to(BACKEND_SRC)).replace("\\", "/")


def _is_shim(path: Path) -> bool:
    rel = _rel(path)
    for root in SHIM_ROOTS:
        if rel == root or rel.startswith(root.rstrip("/") + "/"):
            return True
    return False


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def _scan_domain(
    domain_dir: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
    rule: str,
) -> list[Violation]:
    violations: list[Violation] = []
    if not domain_dir.exists():
        return violations
    for path in domain_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        if _is_shim(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = IMPORT_RE.match(line)
            if not match:
                continue
            mod = match.group(1)
            for prefix in forbidden_prefixes:
                if mod == prefix or mod.startswith(prefix + "."):
                    violations.append(
                        Violation(
                            file_path=_rel(path),
                            line=lineno,
                            rule=rule,
                            snippet=line.strip()[:200],
                        )
                    )
                    break
    return violations


def _scan_infra_product_prompts() -> list[Violation]:
    """Flag final product prompt modules accidentally placed under infra/."""
    violations: list[Violation] = []
    infra = BACKEND_SRC / "infra"
    if not infra.exists():
        return violations
    for path in infra.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".py", ".md", ".txt", ".jinja", ".j2", ".prompt"}:
            continue
        # Allow DB migrations that mention prompts in the filename.
        if "migrations" in path.parts:
            continue
        name = path.name.lower()
        if "prompt" in name and path.suffix == ".py":
            # Loader-only utilities are OK; final prompt bodies are not.
            text = path.read_text(encoding="utf-8", errors="replace")[:2000].lower()
            if "you are a" in text or "system prompt" in text or '"""write' in text:
                violations.append(
                    Violation(
                        file_path=_rel(path),
                        line=1,
                        rule="infra-must-not-own-product-prompts",
                        snippet=path.name,
                    )
                )
    return violations


def find_violations() -> list[Violation]:
    violations: list[Violation] = []
    violations.extend(
        _scan_domain(
            BACKEND_SRC / "print",
            forbidden_prefixes=("learn", "learning"),
            rule="print-must-not-import-learn",
        )
    )
    violations.extend(
        _scan_domain(
            BACKEND_SRC / "learn",
            forbidden_prefixes=("print",),
            rule="learn-must-not-import-print",
        )
    )
    violations.extend(
        _scan_domain(
            BACKEND_SRC / "curriculum",
            forbidden_prefixes=("print", "learn", "learning"),
            rule="curriculum-must-not-import-product",
        )
    )
    violations.extend(
        _scan_domain(
            BACKEND_SRC / "infra",
            forbidden_prefixes=("print", "learn", "learning"),
            rule="infra-must-not-import-product",
        )
    )
    violations.extend(_scan_infra_product_prompts())
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    violations = find_violations()
    if args.format == "json":
        import json

        print(
            json.dumps(
                [
                    {
                        "file": v.file_path,
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
            print("Backend domain boundary check: PASS (0 violations)")
        else:
            print(f"Backend domain boundary check: FAIL ({len(violations)} violations)")
            for v in violations:
                print(f"  [{v.rule}] {v.file_path}:{v.line}: {v.snippet}")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
