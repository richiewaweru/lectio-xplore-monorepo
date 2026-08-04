from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.agent.common import (
    DEFAULT_CONTEXT_PATH,
    REPO_ROOT,
    ContextError,
    get_scope_steps,
    load_project_context,
)


class ValidationError(RuntimeError):
    """Raised when one or more project validation steps fail."""


@dataclass(frozen=True)
class ValidationStep:
    name: str
    cwd: Path
    command: tuple[str, ...]


@dataclass(frozen=True)
class ValidationResult:
    step: ValidationStep
    returncode: int
    stdout: str
    stderr: str

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0


def build_steps(
    context_path: str | Path = DEFAULT_CONTEXT_PATH,
    scope: str = 'all',
    repo_root: Path = REPO_ROOT,
) -> list[ValidationStep]:
    context = load_project_context(context_path, repo_root=repo_root)
    raw_steps = get_scope_steps(context, scope)
    steps: list[ValidationStep] = []
    for raw_step in raw_steps:
        name = raw_step.get('name')
        cwd = raw_step.get('cwd')
        command = raw_step.get('command')
        if not name or not cwd or not command:
            raise ContextError(f"Validation step is incomplete in scope '{scope}': {raw_step!r}")
        steps.append(
            ValidationStep(
                name=name,
                cwd=(repo_root / cwd).resolve(),
                command=tuple(command),
            )
        )
    return steps


def run_step(step: ValidationStep) -> ValidationResult:
    executable = step.command[0]
    resolved = shutil.which(executable)
    if resolved is None and sys.platform == 'win32':
        for suffix in ('.cmd', '.exe', '.bat'):
            resolved = shutil.which(f'{executable}{suffix}')
            if resolved:
                break

    completed = subprocess.run(
        [resolved or executable, *step.command[1:]],
        cwd=step.cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    return ValidationResult(
        step=step,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def format_result(result: ValidationResult) -> str:
    lines = [f"[{result.step.name}] {'PASS' if result.succeeded else 'FAIL'}"]
    if result.stdout.strip():
        lines.append(result.stdout.strip())
    if result.stderr.strip():
        lines.append(result.stderr.strip())
    return '\n'.join(lines)


def validate_scope(
    context_path: str | Path = DEFAULT_CONTEXT_PATH,
    scope: str = 'all',
    repo_root: Path = REPO_ROOT,
) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    failures: list[ValidationResult] = []

    for step in build_steps(context_path=context_path, scope=scope, repo_root=repo_root):
        print(f"==> Running {step.name}: {' '.join(step.command)}", flush=True)
        result = run_step(step)
        print(format_result(result), flush=True)
        results.append(result)
        if not result.succeeded:
            failures.append(result)

    if failures:
        failure_names = ', '.join(result.step.name for result in failures)
        raise ValidationError(f'Validation failed for: {failure_names}')

    return results


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run project-local validation steps declared in the context summary.',
    )
    parser.add_argument(
        '--context',
        default=str(DEFAULT_CONTEXT_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
        help='Path to docs/project/context-summary.yaml',
    )
    parser.add_argument(
        '--scope',
        default='all',
        help='Validation scope to run as declared in the context summary.',
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_scope(context_path=args.context, scope=args.scope)
    except (ValidationError, ContextError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
