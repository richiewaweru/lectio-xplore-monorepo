import sys
from pathlib import Path

import yaml

from tools.agent.validate_repo import build_steps, validate_scope


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
        'validation': {
            'scopes': {
                'smoke': {
                    'steps': [
                        {
                            'name': 'write-proof',
                            'cwd': '.',
                            'command': [
                                sys.executable,
                                '-c',
                                "from pathlib import Path; Path('proof.txt').write_text('ok', encoding='utf-8')",
                            ],
                        }
                    ]
                },
                'all': {'include_scopes': ['smoke']},
            }
        },
        'architecture': {'strategy': {'type': 'none'}},
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


def test_build_steps_expands_nested_scopes(tmp_path: Path):
    context_path = write_context(tmp_path)

    steps = build_steps(context_path=context_path, scope='all', repo_root=tmp_path)

    assert len(steps) == 1
    assert steps[0].name == 'write-proof'


def test_validate_scope_runs_declared_commands(tmp_path: Path):
    context_path = write_context(tmp_path)

    validate_scope(context_path=context_path, scope='smoke', repo_root=tmp_path)

    assert (tmp_path / 'proof.txt').read_text(encoding='utf-8') == 'ok'
