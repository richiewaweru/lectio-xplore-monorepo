from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parents[2]
BLUEPRINT_ROOT = REPO_ROOT / 'agents' / 'blueprints'
REQUIRED_CONTEXT_SECTIONS = {
    'repo',
    'stack',
    'validation',
    'architecture',
    'github',
    'release',
    'agent_policy',
    'docs',
    'process_packs',
}
FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)
CHECKBOX_PATTERN = re.compile(r'^- \[(?P<done>[ xX])\] (?P<label>.+)$')


class ContextError(RuntimeError):
    """Raised when the project context file is invalid or incomplete."""


def resolve_repo_path(path: str | Path, repo_root: Path = REPO_ROOT) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def load_context(context_path: str | Path, repo_root: Path = REPO_ROOT) -> dict[str, Any]:
    path = resolve_repo_path(context_path, repo_root=repo_root)
    if not path.exists():
        raise ContextError(f'Context summary not found: {path}')

    try:
        payload = yaml.safe_load(path.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as exc:
        raise ContextError(f'Invalid YAML in context summary: {exc}') from exc

    if not isinstance(payload, dict):
        raise ContextError('Context summary must be a YAML mapping.')

    missing = sorted(REQUIRED_CONTEXT_SECTIONS - payload.keys())
    if missing:
        raise ContextError(f'Context summary is missing sections: {", ".join(missing)}')

    payload['_context_path'] = path
    payload['_repo_root'] = repo_root
    return payload


def get_scope_steps(context: dict[str, Any], scope: str) -> list[dict[str, Any]]:
    scopes = context['validation'].get('scopes', {})
    if scope not in scopes:
        raise ContextError(f"Validation scope '{scope}' is not defined in the context summary.")

    scope_payload = scopes[scope]
    if 'include_scopes' in scope_payload:
        expanded: list[dict[str, Any]] = []
        for nested_scope in scope_payload['include_scopes']:
            expanded.extend(get_scope_steps(context, nested_scope))
        return expanded

    steps = scope_payload.get('steps', [])
    if not isinstance(steps, list) or not steps:
        raise ContextError(f"Validation scope '{scope}' must define one or more steps.")
    return steps


def get_architecture_strategy(context: dict[str, Any]) -> dict[str, Any]:
    strategy = context['architecture'].get('strategy')
    if not isinstance(strategy, dict) or not strategy:
        raise ContextError('architecture.strategy must be declared as a mapping.')
    if not strategy.get('type'):
        raise ContextError('architecture.strategy.type must be declared.')
    return strategy


def get_required_pr_sections(context: dict[str, Any]) -> list[str]:
    sections = context['github'].get('pr_required_sections', [])
    if not sections:
        raise ContextError('github.pr_required_sections must not be empty.')
    return sections


def get_allowed_commit_types(context: dict[str, Any]) -> set[str]:
    commit_types = context['agent_policy'].get('allowed_commit_types', [])
    if not commit_types:
        raise ContextError('agent_policy.allowed_commit_types must not be empty.')
    return {item.lower() for item in commit_types}


def get_protected_branches(context: dict[str, Any]) -> set[str]:
    branches = context['repo'].get('protected_branches') or context['agent_policy'].get(
        'protected_branches',
        [],
    )
    if not branches:
        raise ContextError('Protected branches must be declared in repo or agent_policy.')
    return set(branches)


def get_process_pack(context: dict[str, Any], process_name: str) -> dict[str, Any]:
    process_packs = context['process_packs']
    if process_name not in process_packs:
        raise ContextError(f"Unknown process pack '{process_name}'.")
    return process_packs[process_name]


def template_environment(repo_root: Path = REPO_ROOT) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(repo_root / 'agents' / 'blueprints')),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def render_blueprint(template_name: str, render_context: dict[str, Any], repo_root: Path = REPO_ROOT) -> str:
    env = template_environment(repo_root=repo_root)
    return env.get_template(template_name).render(**render_context)


def load_frontmatter(markdown_text: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_PATTERN.match(markdown_text)
    if not match:
        raise ContextError('Runbook is missing YAML frontmatter.')

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ContextError(f'Invalid YAML frontmatter: {exc}') from exc

    if not isinstance(frontmatter, dict):
        raise ContextError('Runbook frontmatter must be a YAML mapping.')

    return frontmatter, markdown_text[match.end() :]


def extract_checklist_items(markdown_body: str) -> list[tuple[bool, str]]:
    items: list[tuple[bool, str]] = []
    for line in markdown_body.splitlines():
        match = CHECKBOX_PATTERN.match(line.strip())
        if match:
            items.append((match.group('done').lower() == 'x', match.group('label').strip()))
    return items
