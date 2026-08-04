from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.agent.common import (
    DEFAULT_CONTEXT_PATH,
    REPO_ROOT,
    ContextError,
    get_architecture_strategy,
    load_project_context,
)


@dataclass(frozen=True)
class ArchitectureViolation:
    file_path: str
    line: int
    source_layer: str
    target_layer: str
    import_path: str
    reason: str
    check_name: str | None = None


def module_name_for_file(file_path: Path, package_root: Path, module_prefix: str) -> str:
    relative = file_path.relative_to(package_root).with_suffix('')
    parts = [module_prefix, *relative.parts]
    if parts[-1] == '__init__':
        parts = parts[:-1]
    return '.'.join(parts)


def layer_for_module(module_name: str, module_prefix: str) -> str | None:
    parts = module_name.split('.')
    if len(parts) < 2 or parts[0] != module_prefix:
        return None
    return parts[1]


def resolve_import(current_module: str, module_name: str | None, level: int) -> str | None:
    if level == 0:
        return module_name

    current_package_parts = current_module.split('.')[:-1]
    trim = level - 1
    if trim > len(current_package_parts):
        return None

    base_parts = current_package_parts[: len(current_package_parts) - trim]
    if module_name:
        return '.'.join([*base_parts, *module_name.split('.')])
    return '.'.join(base_parts)


def extract_imports(
    file_path: Path,
    package_root: Path,
    module_prefix: str,
) -> list[tuple[int, str]]:
    # Some Windows editors may write UTF-8 with BOM. `utf-8-sig` strips the BOM
    # so `ast.parse` doesn't choke on a leading U+FEFF.
    tree = ast.parse(file_path.read_text(encoding='utf-8-sig'), filename=str(file_path))
    current_module = module_name_for_file(file_path, package_root, module_prefix)
    imports: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            resolved = resolve_import(current_module, node.module, node.level)
            if resolved:
                imports.append((node.lineno, resolved))

    return imports


def extract_internal_imports(
    file_path: Path,
    package_root: Path,
    module_prefix: str,
) -> list[tuple[int, str]]:
    return [
        (line, import_path)
        for line, import_path in extract_imports(file_path, package_root, module_prefix)
        if import_path == module_prefix or import_path.startswith(f'{module_prefix}.')
    ]


def import_layer_violations(strategy: dict[str, object], repo_root: Path) -> list[ArchitectureViolation]:
    package_root = (repo_root / strategy['package_root']).resolve()
    module_prefix = strategy['module_prefix']
    check_name = strategy.get('name')
    layer_rules = {
        layer: set(rule.get('forbidden', []))
        for layer, rule in strategy['layers'].items()
    }

    violations: list[ArchitectureViolation] = []
    for file_path in sorted(package_root.rglob('*.py')):
        source_layer = layer_for_module(
            module_name_for_file(file_path, package_root, module_prefix),
            module_prefix,
        )
        if source_layer not in layer_rules:
            continue

        for line, import_path in extract_internal_imports(file_path, package_root, module_prefix):
            target_layer = layer_for_module(import_path, module_prefix)
            if target_layer in layer_rules[source_layer]:
                reason = (
                    f'{source_layer} layer must not import {target_layer} layer modules directly.'
                )
                violations.append(
                    ArchitectureViolation(
                        file_path=str(file_path.relative_to(repo_root)).replace('\\', '/'),
                        line=line,
                        source_layer=source_layer,
                        target_layer=target_layer,
                        import_path=import_path,
                        reason=reason,
                        check_name=check_name,
                    )
                )

    return violations


def forbidden_import_prefix_violations(
    strategy: dict[str, object],
    repo_root: Path,
) -> list[ArchitectureViolation]:
    package_root = (repo_root / strategy['package_root']).resolve()
    module_prefix = strategy['module_prefix']
    check_name = strategy.get('name')
    source_label = str(strategy.get('source_label', module_prefix))
    forbidden_prefixes = [str(prefix) for prefix in strategy.get('forbidden_prefixes', [])]

    violations: list[ArchitectureViolation] = []
    for file_path in sorted(package_root.rglob('*.py')):
        for line, import_path in extract_imports(file_path, package_root, module_prefix):
            target_prefix = next(
                (
                    prefix
                    for prefix in forbidden_prefixes
                    if import_path == prefix or import_path.startswith(f'{prefix}.')
                ),
                None,
            )
            if target_prefix is None:
                continue

            reason = f'{source_label} package must not import {target_prefix} modules directly.'
            violations.append(
                ArchitectureViolation(
                    file_path=str(file_path.relative_to(repo_root)).replace('\\', '/'),
                    line=line,
                    source_layer=source_label,
                    target_layer=target_prefix,
                    import_path=import_path,
                    reason=reason,
                    check_name=check_name,
                )
            )

    return violations


def strategy_violations(strategy: dict[str, object], repo_root: Path) -> list[ArchitectureViolation]:
    strategy_type = strategy['type']
    if strategy_type == 'import-layer':
        return import_layer_violations(strategy, repo_root=repo_root)
    if strategy_type == 'forbidden-import-prefix':
        return forbidden_import_prefix_violations(strategy, repo_root=repo_root)
    if strategy_type == 'composite':
        violations: list[ArchitectureViolation] = []
        for check in strategy.get('checks', []):
            violations.extend(strategy_violations(check, repo_root=repo_root))
        return violations
    if strategy_type == 'none':
        return []
    raise ContextError(f'Unsupported architecture strategy type: {strategy_type}')


def find_violations(
    context_path: str | Path = DEFAULT_CONTEXT_PATH,
    repo_root: Path = REPO_ROOT,
) -> list[ArchitectureViolation]:
    context = load_project_context(context_path, repo_root=repo_root)
    strategy = get_architecture_strategy(context)
    strategy_type = strategy['type']
    if strategy_type == 'none':
        return []
    if strategy_type not in {'import-layer', 'forbidden-import-prefix', 'composite'}:
        raise ContextError(
            'find_violations only supports in-process architecture strategies.'
        )
    return strategy_violations(strategy, repo_root=repo_root)


def render_text(violations: list[ArchitectureViolation], strategy_type: str) -> str:
    if strategy_type == 'none':
        return 'No automated architecture guard configured.'
    if not violations:
        return 'No architecture violations found.'

    lines = ['Architecture violations detected:']
    for violation in violations:
        check_prefix = f'({violation.check_name}) ' if violation.check_name else ''
        lines.append(
            (
                f'- {violation.file_path}:{violation.line} '
                f'[{violation.source_layer}->{violation.target_layer}] '
                f'{check_prefix}{violation.import_path}: {violation.reason}'
            )
        )
    return '\n'.join(lines)


def render_markdown(violations: list[ArchitectureViolation], strategy_type: str) -> str:
    lines = ['## Architecture Guard']
    if strategy_type == 'none':
        lines.extend(['', 'No automated architecture guard configured.'])
        return '\n'.join(lines)
    if not violations:
        lines.extend(['', 'No architecture violations found.'])
        return '\n'.join(lines)

    lines.extend(['', '| File | Line | Violation |', '| --- | ---: | --- |'])
    for violation in violations:
        check_prefix = f'[{violation.check_name}] ' if violation.check_name else ''
        message = (
            f'{check_prefix}`{violation.source_layer}` imported `{violation.target_layer}` via '
            f'`{violation.import_path}`'
        )
        lines.append(f"| `{violation.file_path}` | {violation.line} | {message} |")
    return '\n'.join(lines)


def render_sarif(violations: list[ArchitectureViolation], tool_name: str) -> str:
    results = []
    for violation in violations:
        results.append(
            {
                'level': 'error',
                'message': {'text': violation.reason},
                'locations': [
                    {
                        'physicalLocation': {
                            'artifactLocation': {'uri': violation.file_path},
                            'region': {'startLine': violation.line},
                        }
                    }
                ],
                'properties': asdict(violation),
            }
        )

    payload = {
        'version': '2.1.0',
        'runs': [
            {
                'tool': {
                    'driver': {
                        'name': tool_name,
                        'informationUri': 'https://github.com/',
                        'rules': [
                            {
                                'id': 'layer-boundary',
                                'name': 'layer-boundary',
                                'shortDescription': {
                                    'text': 'Enforce repository layer import rules.',
                                },
                            }
                        ],
                    }
                },
                'results': results,
            }
        ],
    }
    return json.dumps(payload, indent=2)


def run_external_strategy(strategy: dict[str, object], repo_root: Path) -> subprocess.CompletedProcess[str]:
    command = strategy.get('command')
    if not command:
        raise ContextError('architecture.strategy.command must be declared for external-command.')
    cwd = repo_root / strategy.get('cwd', '.')
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Run the project-local architecture guard declared in the context summary.',
    )
    parser.add_argument(
        '--context',
        default=str(DEFAULT_CONTEXT_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
        help='Path to docs/project/context-summary.yaml',
    )
    parser.add_argument(
        '--format',
        choices=['text', 'markdown', 'sarif'],
        default='text',
        help='Output format for import-layer strategies.',
    )
    parser.add_argument('--root', default=str(REPO_ROOT), help='Repository root to scan.')
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = Path(args.root).resolve()
    try:
        context = load_project_context(args.context, repo_root=repo_root)
        strategy = get_architecture_strategy(context)
        strategy_type = strategy['type']
    except ContextError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if strategy_type in {'import-layer', 'forbidden-import-prefix', 'composite'}:
        violations = strategy_violations(strategy, repo_root=repo_root)
        if args.format == 'markdown':
            print(render_markdown(violations, strategy_type))
        elif args.format == 'sarif':
            print(render_sarif(violations, strategy.get('report_name', 'architecture-guard')))
        else:
            print(render_text(violations, strategy_type))
        return 1 if violations else 0

    if strategy_type == 'external-command':
        try:
            completed = run_external_strategy(strategy, repo_root=repo_root)
        except ContextError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if completed.stdout.strip():
            print(completed.stdout.strip())
        if completed.stderr.strip():
            print(completed.stderr.strip(), file=sys.stderr)
        return completed.returncode

    if strategy_type == 'none':
        print(render_text([], strategy_type))
        return 0

    print(f"Unsupported architecture strategy type: {strategy_type}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
