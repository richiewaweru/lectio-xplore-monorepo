from pathlib import Path

import yaml

from tools.agent.check_architecture import find_violations


def write_context(repo_root: Path) -> Path:
    docs_root = repo_root / 'docs' / 'project'
    docs_root.mkdir(parents=True)
    context_path = docs_root / 'context-summary.yaml'
    payload = {
        'repo': {
            'name': 'Test Repo',
            'default_branch': 'main',
            'protected_branches': ['main'],
        },
        'stack': {
            'python': {'working_directory': 'backend', 'install_command': 'uv sync --all-extras'},
            'frontend': {'working_directory': 'frontend', 'install_command': 'npm ci'},
        },
        'validation': {'scopes': {'all': {'include_scopes': []}}},
        'architecture': {
            'strategy': {
                'type': 'forbidden-import-prefix',
                'name': 'core-no-app',
                'report_name': 'test-guard',
                'package_root': 'backend/src/core',
                'module_prefix': 'core',
                'source_label': 'core',
                'forbidden_prefixes': ['generation', 'planning', 'pipeline'],
            }
        },
        'github': {'required_checks': ['agent-governance'], 'pr_required_sections': ['Summary']},
        'release': {
            'current_version': '0.1.0',
            'tag_pattern': 'v*',
            'changelog_path': 'CHANGELOG.md',
        },
        'agent_policy': {
            'allowed_commit_types': ['feat'],
            'stage_packs': ['bootstrap'],
        },
        'docs': {'live_root': 'docs/project', 'run_root': 'docs/project/runs', 'local_context_docs': []},
        'process_packs': {
            'bootstrap-setup': {
                'template': 'setup-runbook',
                'variant': 'full',
                'steps': [{'id': 'one', 'title': 'One'}],
            }
        },
    }
    context_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
    return context_path


def write_composite_context(repo_root: Path) -> Path:
    docs_root = repo_root / 'docs' / 'project'
    docs_root.mkdir(parents=True)
    context_path = docs_root / 'context-summary.yaml'
    payload = {
        'repo': {
            'name': 'Test Repo',
            'default_branch': 'main',
            'protected_branches': ['main'],
        },
        'stack': {
            'python': {'working_directory': 'backend', 'install_command': 'uv sync --all-extras'},
            'frontend': {'working_directory': 'frontend', 'install_command': 'npm ci'},
        },
        'validation': {'scopes': {'all': {'include_scopes': []}}},
        'architecture': {
            'strategy': {
                'type': 'composite',
                'name': 'split-app-boundary',
                'report_name': 'test-guard',
                'checks': [
                    {
                        'type': 'forbidden-import-prefix',
                        'name': 'core-no-app',
                        'package_root': 'backend/src/core',
                        'module_prefix': 'core',
                        'source_label': 'core',
                        'forbidden_prefixes': ['generation', 'planning', 'pipeline'],
                    },
                    {
                        'type': 'forbidden-import-prefix',
                        'name': 'generation-no-core',
                        'package_root': 'backend/src/generation',
                        'module_prefix': 'generation',
                        'source_label': 'generation',
                        'forbidden_prefixes': ['core.app'],
                    },
                ],
            }
        },
        'github': {'required_checks': ['agent-governance'], 'pr_required_sections': ['Summary']},
        'release': {
            'current_version': '0.1.0',
            'tag_pattern': 'v*',
            'changelog_path': 'CHANGELOG.md',
        },
        'agent_policy': {
            'allowed_commit_types': ['feat'],
            'stage_packs': ['bootstrap'],
        },
        'docs': {'live_root': 'docs/project', 'run_root': 'docs/project/runs', 'local_context_docs': []},
        'process_packs': {
            'bootstrap-setup': {
                'template': 'setup-runbook',
                'variant': 'full',
                'steps': [{'id': 'one', 'title': 'One'}],
            }
        },
    }
    context_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
    return context_path


def test_architecture_guard_passes_current_repo():
    repo_root = Path(__file__).resolve().parents[3]
    context_path = repo_root / 'docs' / 'project' / 'context-summary.yaml'

    violations = find_violations(context_path=context_path, repo_root=repo_root)

    assert violations == []


def test_architecture_guard_detects_forbidden_domain_import(tmp_path: Path):
    context_path = write_context(tmp_path)
    package_root = tmp_path / 'backend' / 'src' / 'core'
    package_root.mkdir(parents=True)

    (package_root / 'bad.py').write_text(
        'from generation.models import Example\n',
        encoding='utf-8',
    )

    violations = find_violations(context_path=context_path, repo_root=tmp_path)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.source_layer == 'core'
    assert violation.target_layer == 'generation'
    assert violation.line == 1


def test_architecture_guard_detects_generation_importing_forbidden_module(tmp_path: Path):
    context_path = write_composite_context(tmp_path)
    generation_root = tmp_path / 'backend' / 'src' / 'generation'
    generation_root.mkdir(parents=True)

    (generation_root / 'run.py').write_text(
        'from core.app import create_app\n',
        encoding='utf-8',
    )

    violations = find_violations(context_path=context_path, repo_root=tmp_path)

    assert len(violations) == 1
    violation = violations[0]
    assert violation.source_layer == 'generation'
    assert violation.target_layer == 'core.app'
    assert violation.line == 1
