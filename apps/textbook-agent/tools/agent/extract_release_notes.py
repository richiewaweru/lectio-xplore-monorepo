from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

if __package__ in {None, ''}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.agent.common import (
    DEFAULT_CONTEXT_PATH,
    REPO_ROOT,
    ContextError,
    load_project_context,
    resolve_repo_path,
)


def extract_release_notes(
    context_path: str | Path = DEFAULT_CONTEXT_PATH,
    version: str = '0.1.0',
    repo_root: Path = REPO_ROOT,
) -> str:
    context = load_project_context(context_path, repo_root=repo_root)
    changelog_path = resolve_repo_path(context['release']['changelog_path'], repo_root=repo_root)
    target_heading = f"## [{version.removeprefix('v')}]"
    lines = changelog_path.read_text(encoding='utf-8').splitlines()

    collecting = False
    collected: list[str] = []
    for line in lines:
        if line.startswith('## ['):
            if line.startswith(target_heading):
                collecting = True
                collected.append(line)
                continue
            if collecting:
                break
        elif collecting:
            collected.append(line)

    if not collected:
        raise ValueError(f'No changelog section found for version {version}')

    return '\n'.join(collected).strip() + '\n'


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Extract a version section from the changelog.')
    parser.add_argument(
        '--context',
        default=str(DEFAULT_CONTEXT_PATH.relative_to(REPO_ROOT)).replace('\\', '/'),
        help='Path to docs/project/context-summary.yaml',
    )
    parser.add_argument('--version', required=True, help='Release tag, e.g. v0.1.0')
    parser.add_argument('--output', help='Optional output file path.')
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        notes = extract_release_notes(context_path=args.context, version=args.version)
    except (ContextError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.output:
        Path(args.output).write_text(notes, encoding='utf-8')
    else:
        print(notes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
